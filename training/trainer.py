"""
Distributed Training Loop with FSDP support.

Implements:
  - PyTorch FSDP (Fully Sharded Data Parallel)
  - Core loop: forward → loss → backward → optimizer step
  - LR scheduler: linear warmup + cosine decay
  - Gradient clipping
  - Mixed precision (bf16 / fp16)
  - Checkpoint save / load (model + optimizer + scheduler state)
  - Logging: loss, lr, throughput (tokens/sec), gradient norm
  - Optional WandB integration (via WANDB_DISABLED env)
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import torch
import torch.distributed as dist
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

try:
    from data.dataloader import PretrainDataset, DataPosition, create_dataloader
    _HAS_PRETRAIN_DATASET = True
except ImportError:
    _HAS_PRETRAIN_DATASET = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config dataclass (mirrors YAML; can also be built from OmegaConf DictConfig)
# ---------------------------------------------------------------------------

@dataclass
class TrainConfig:
    # Optimisation
    lr: float = 3e-4
    min_lr: float = 3e-5
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    grad_clip_max_norm: float = 1.0

    # Batch
    micro_batch_size: int = 4
    gradient_accumulation_steps: int = 8

    # Schedule
    max_steps: int = 100_000
    warmup_steps: int = 2000

    # Precision
    dtype: str = "bf16"  # bf16 | fp16 | fp32

    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    checkpoint_interval: int = 1000
    resume_from: Optional[str] = None

    # Evaluation
    eval_interval: int = 500
    eval_steps: int = 50

    # Logging
    log_interval: int = 10
    wandb_project: Optional[str] = None
    wandb_run_name: Optional[str] = None

    # Reproducibility
    seed: int = 42

    # Streaming data loader
    data_dir: Optional[str] = None           # path to tokenized shard directory
    num_data_workers: int = 2                # DataLoader worker count
    eos_token_id: int = 2                    # EOS token ID for sequence packing

    # FSDP
    fsdp_enabled: bool = True
    fsdp_sharding_strategy: str = "FULL_SHARD"
    fsdp_cpu_offload: bool = False
    fsdp_activation_checkpointing: bool = False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrainConfig":
        """Build from a flat or nested dict (e.g. OmegaConf → dict)."""
        flat: Dict[str, Any] = {}
        training = d.get("training", d)
        for k, v in training.items():
            flat[k] = v
        # Pull FSDP flags from distributed section if present
        dist_cfg = d.get("distributed", {})
        fsdp_cfg = dist_cfg.get("fsdp", {})
        if fsdp_cfg:
            flat.setdefault("fsdp_enabled", fsdp_cfg.get("enabled", True))
            flat.setdefault("fsdp_sharding_strategy", fsdp_cfg.get("sharding_strategy", "FULL_SHARD"))
            flat.setdefault("fsdp_cpu_offload", fsdp_cfg.get("cpu_offload", False))
            flat.setdefault("fsdp_activation_checkpointing", fsdp_cfg.get("activation_checkpointing", False))
        # Filter to known fields only
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in flat.items() if k in known})


# ---------------------------------------------------------------------------
# LR Schedule helpers
# ---------------------------------------------------------------------------

def get_lr(step: int, cfg: TrainConfig) -> float:
    """Linear warmup then cosine decay to ``min_lr``."""
    if step < cfg.warmup_steps:
        return cfg.lr * (step + 1) / cfg.warmup_steps
    if step >= cfg.max_steps:
        return cfg.min_lr
    decay_ratio = (step - cfg.warmup_steps) / (cfg.max_steps - cfg.warmup_steps)
    coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))
    return cfg.min_lr + coeff * (cfg.lr - cfg.min_lr)


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------

class Trainer:
    """Distributed trainer with FSDP, mixed precision, checkpointing."""

    def __init__(
        self,
        model: nn.Module,
        train_dataset: Optional[Dataset] = None,
        val_dataset: Optional[Dataset] = None,
        cfg: Optional[TrainConfig] = None,
        collate_fn=None,
        train_loader: Optional[DataLoader] = None,
    ):
        self.cfg = cfg or TrainConfig()
        self.global_step = 0
        self.best_val_loss = float("inf")
        self._wandb = None
        self._pretrain_dataset = None  # streaming dataset reference

        # ---------- Distributed setup ----------
        self.is_distributed = dist.is_initialized()
        self.local_rank = int(os.environ.get("LOCAL_RANK", 0))
        self.world_size = dist.get_world_size() if self.is_distributed else 1
        self.rank = dist.get_rank() if self.is_distributed else 0
        self.is_main = self.rank == 0

        # ---------- Device / dtype ----------
        if torch.cuda.is_available():
            self.device = torch.device(f"cuda:{self.local_rank}")
            torch.cuda.set_device(self.device)
        else:
            self.device = torch.device("cpu")

        self.pt_dtype = {
            "bf16": torch.bfloat16,
            "fp16": torch.float16,
            "fp32": torch.float32,
        }.get(self.cfg.dtype, torch.bfloat16)

        # ---------- Model → FSDP ----------
        self.model = self._wrap_model(model)

        # ---------- Optimizer ----------
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.cfg.lr,
            betas=(self.cfg.beta1, self.cfg.beta2),
            weight_decay=self.cfg.weight_decay,
            fused=torch.cuda.is_available(),
        )

        # ---------- Dataloaders ----------
        if train_loader is not None:
            # Use externally-provided streaming DataLoader
            self.train_loader = train_loader
        elif self.cfg.data_dir and _HAS_PRETRAIN_DATASET:
            # Build streaming DataLoader from config
            from data.dataloader import create_dataloader
            self.train_loader, self._pretrain_dataset = create_dataloader(
                data_dir=self.cfg.data_dir,
                max_seq_len=4096,
                batch_size=self.cfg.micro_batch_size,
                rank=self.rank,
                world_size=self.world_size,
                num_workers=self.cfg.num_data_workers,
                seed=self.cfg.seed,
                eos_token_id=self.cfg.eos_token_id,
                infinite=True,
            )
        elif train_dataset is not None:
            sampler = None
            if self.is_distributed:
                sampler = torch.utils.data.DistributedSampler(
                    train_dataset, num_replicas=self.world_size, rank=self.rank, shuffle=True, seed=self.cfg.seed
                )
            self.train_loader = DataLoader(
                train_dataset,
                batch_size=self.cfg.micro_batch_size,
                sampler=sampler,
                shuffle=(sampler is None),
                num_workers=0,
                pin_memory=torch.cuda.is_available(),
                collate_fn=collate_fn,
            )
        else:
            raise ValueError("Must provide one of: train_dataset, train_loader, or cfg.data_dir")

        self.val_loader: Optional[DataLoader] = None
        if val_dataset is not None:
            self.val_loader = DataLoader(
                val_dataset,
                batch_size=self.cfg.micro_batch_size,
                shuffle=False,
                num_workers=0,
                pin_memory=torch.cuda.is_available(),
                collate_fn=collate_fn,
            )

        # ---------- AMP GradScaler (fp16 only) ----------
        self.scaler: Optional[torch.amp.GradScaler] = None
        if self.cfg.dtype == "fp16" and torch.cuda.is_available():
            self.scaler = torch.amp.GradScaler("cuda")

        # ---------- WandB ----------
        self._init_wandb()

        # ---------- Resume ----------
        if self.cfg.resume_from:
            self.load_checkpoint(self.cfg.resume_from)

    # ------------------------------------------------------------------
    # Model wrapping (FSDP / single-device)
    # ------------------------------------------------------------------
    def _wrap_model(self, model: nn.Module) -> nn.Module:
        model = model.to(self.device)
        if not self.cfg.fsdp_enabled or not self.is_distributed:
            return model

        from torch.distributed.fsdp import FullyShardedDataParallel as FSDP, ShardingStrategy, MixedPrecision, CPUOffload

        sharding_map = {
            "FULL_SHARD": ShardingStrategy.FULL_SHARD,
            "SHARD_GRAD_OP": ShardingStrategy.SHARD_GRAD_OP,
            "NO_SHARD": ShardingStrategy.NO_SHARD,
        }
        mp_policy = None
        if self.pt_dtype != torch.float32:
            mp_policy = MixedPrecision(
                param_dtype=self.pt_dtype,
                reduce_dtype=torch.float32,
                buffer_dtype=self.pt_dtype,
            )
        cpu_offload = CPUOffload(offload_params=True) if self.cfg.fsdp_cpu_offload else None

        model = FSDP(
            model,
            sharding_strategy=sharding_map.get(self.cfg.fsdp_sharding_strategy, ShardingStrategy.FULL_SHARD),
            mixed_precision=mp_policy,
            cpu_offload=cpu_offload,
            device_id=self.local_rank,
            use_orig_params=True,
        )

        if self.cfg.fsdp_activation_checkpointing:
            from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import (
                apply_activation_checkpointing,
                checkpoint_wrapper,
                CheckpointImpl,
            )
            # Import the block class for wrapping
            try:
                from model.modeling import TransformerBlock
                apply_activation_checkpointing(
                    model,
                    checkpoint_wrapper_fn=checkpoint_wrapper,
                    check_fn=lambda m: isinstance(m, TransformerBlock),
                )
            except ImportError:
                logger.warning("Could not apply activation checkpointing – TransformerBlock not found.")

        return model

    # ------------------------------------------------------------------
    # WandB
    # ------------------------------------------------------------------
    def _init_wandb(self):
        if not self.is_main:
            return
        if os.environ.get("WANDB_DISABLED", "").lower() in ("1", "true"):
            return
        if self.cfg.wandb_project is None:
            return
        try:
            import wandb
            wandb.init(
                project=self.cfg.wandb_project,
                name=self.cfg.wandb_run_name,
                config=self.cfg.__dict__,
            )
            self._wandb = wandb
        except ImportError:
            logger.info("wandb not installed – skipping W&B logging.")

    # ------------------------------------------------------------------
    # Core training loop
    # ------------------------------------------------------------------
    def train(self):
        """Main training entry-point."""
        logger.info(
            f"[rank {self.rank}] Starting training — "
            f"max_steps={self.cfg.max_steps}, micro_bs={self.cfg.micro_batch_size}, "
            f"grad_accum={self.cfg.gradient_accumulation_steps}, dtype={self.cfg.dtype}"
        )

        self.model.train()
        train_iter = iter(self.train_loader)
        accum_loss = 0.0
        accum_tokens = 0
        t0 = time.perf_counter()

        while self.global_step < self.cfg.max_steps:
            # --- Gradient accumulation micro-steps ---
            self.optimizer.zero_grad(set_to_none=True)

            for micro_step in range(self.cfg.gradient_accumulation_steps):
                try:
                    batch = next(train_iter)
                except StopIteration:
                    if hasattr(self.train_loader, "sampler") and hasattr(self.train_loader.sampler, "set_epoch"):
                        self.train_loader.sampler.set_epoch(self.global_step)
                    train_iter = iter(self.train_loader)
                    batch = next(train_iter)

                loss, n_tokens = self._forward_backward(batch, micro_step)
                accum_loss += loss
                accum_tokens += n_tokens

            # --- Gradient clipping ---
            grad_norm = self._clip_gradients()

            # --- LR schedule ---
            lr = get_lr(self.global_step, self.cfg)
            for pg in self.optimizer.param_groups:
                pg["lr"] = lr

            # --- Optimizer step ---
            if self.scaler is not None:
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                self.optimizer.step()

            self.global_step += 1

            # --- Logging ---
            if self.global_step % self.cfg.log_interval == 0:
                dt = time.perf_counter() - t0
                tokens_per_sec = accum_tokens / dt if dt > 0 else 0
                avg_loss = accum_loss / self.cfg.gradient_accumulation_steps
                if self.is_main:
                    logger.info(
                        f"step {self.global_step:>7d} | "
                        f"loss {avg_loss:.4f} | lr {lr:.2e} | "
                        f"grad_norm {grad_norm:.3f} | "
                        f"tok/s {tokens_per_sec:.0f}"
                    )
                    if self._wandb:
                        self._wandb.log({
                            "train/loss": avg_loss,
                            "train/lr": lr,
                            "train/grad_norm": grad_norm,
                            "train/tokens_per_sec": tokens_per_sec,
                            "train/step": self.global_step,
                        }, step=self.global_step)
                accum_loss = 0.0
                accum_tokens = 0
                t0 = time.perf_counter()

            # --- Evaluation ---
            if self.val_loader is not None and self.global_step % self.cfg.eval_interval == 0:
                val_loss = self.evaluate()
                if self.is_main:
                    logger.info(f"step {self.global_step:>7d} | val_loss {val_loss:.4f}")
                    if self._wandb:
                        self._wandb.log({"val/loss": val_loss}, step=self.global_step)
                self.model.train()

            # --- Checkpoint ---
            if self.global_step % self.cfg.checkpoint_interval == 0:
                self.save_checkpoint()

        # Final checkpoint
        self.save_checkpoint(tag="final")
        if self.is_main:
            logger.info("Training finished.")

    # ------------------------------------------------------------------
    # Forward + backward (single micro-step)
    # ------------------------------------------------------------------
    def _forward_backward(self, batch, micro_step: int):
        """Run one micro-batch forward + backward.

        Returns (loss_scalar, num_tokens).
        """
        input_ids = batch["input_ids"].to(self.device, non_blocking=True)
        labels = batch.get("labels", input_ids[:, 1:]).to(self.device, non_blocking=True)

        # Shift for causal LM: predict next token
        if labels.shape[-1] == input_ids.shape[-1]:
            input_ids = input_ids[:, :-1]
            labels = labels[:, 1:]

        n_tokens = labels.numel()

        # Context manager for mixed precision
        amp_ctx = torch.amp.autocast(
            device_type=self.device.type,
            dtype=self.pt_dtype,
            enabled=(self.cfg.dtype != "fp32"),
        )

        # Sync gradients only on the last micro-step (FSDP handles this internally
        # when use_orig_params=True and we accumulate manually).
        with amp_ctx:
            logits = self.model(input_ids)
            loss = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                labels.reshape(-1),
                ignore_index=-100,
            )
            loss = loss / self.cfg.gradient_accumulation_steps

        if self.scaler is not None:
            self.scaler.scale(loss).backward()
        else:
            loss.backward()

        return loss.detach().item() * self.cfg.gradient_accumulation_steps, n_tokens

    # ------------------------------------------------------------------
    # Gradient clipping
    # ------------------------------------------------------------------
    def _clip_gradients(self) -> float:
        if self.scaler is not None:
            self.scaler.unscale_(self.optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(
            self.model.parameters(), self.cfg.grad_clip_max_norm
        )
        return grad_norm.item() if isinstance(grad_norm, torch.Tensor) else float(grad_norm)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    @torch.no_grad()
    def evaluate(self) -> float:
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        amp_ctx = torch.amp.autocast(
            device_type=self.device.type,
            dtype=self.pt_dtype,
            enabled=(self.cfg.dtype != "fp32"),
        )

        for i, batch in enumerate(self.val_loader):
            if i >= self.cfg.eval_steps:
                break
            input_ids = batch["input_ids"].to(self.device, non_blocking=True)
            labels = batch.get("labels", input_ids[:, 1:]).to(self.device, non_blocking=True)
            if labels.shape[-1] == input_ids.shape[-1]:
                input_ids = input_ids[:, :-1]
                labels = labels[:, 1:]

            with amp_ctx:
                logits = self.model(input_ids)
                loss = torch.nn.functional.cross_entropy(
                    logits.reshape(-1, logits.size(-1)),
                    labels.reshape(-1),
                    ignore_index=-100,
                )
            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)

        # Average across ranks
        if self.is_distributed:
            loss_t = torch.tensor([avg_loss, n_batches], device=self.device)
            dist.all_reduce(loss_t, op=dist.ReduceOp.SUM)
            avg_loss = (loss_t[0] / loss_t[1]).item()

        return avg_loss

    # ------------------------------------------------------------------
    # Checkpoint save / load
    # ------------------------------------------------------------------
    def save_checkpoint(self, tag: Optional[str] = None):
        if not self.is_main:
            return
        ckpt_dir = Path(self.cfg.checkpoint_dir)
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        name = tag or f"step_{self.global_step}"
        path = ckpt_dir / f"{name}.pt"

        # For FSDP we use state_dict which consolidates shards on rank 0
        state = {
            "global_step": self.global_step,
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "config": self.cfg.__dict__,
        }
        if self.scaler is not None:
            state["scaler"] = self.scaler.state_dict()
        # Save data position for streaming dataloader resumability
        if self._pretrain_dataset is not None:
            state["data_position"] = self._pretrain_dataset.get_position().to_dict()
        torch.save(state, path)
        logger.info(f"Checkpoint saved → {path}")

    def load_checkpoint(self, path: str):
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(ckpt["model"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.global_step = ckpt.get("global_step", 0)
        if self.scaler is not None and "scaler" in ckpt:
            self.scaler.load_state_dict(ckpt["scaler"])
        # Restore data position for streaming dataloader
        if self._pretrain_dataset is not None and "data_position" in ckpt:
            from data.dataloader import DataPosition
            self._pretrain_dataset.set_position(DataPosition.from_dict(ckpt["data_position"]))
            logger.info(f"Restored data position: {ckpt['data_position']}")
        logger.info(f"Resumed from {path} at step {self.global_step}")
