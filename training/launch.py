#!/usr/bin/env python3
"""
Launch script for distributed training via ``torchrun``.

Usage (single GPU):
    python training/launch.py --config configs/train_config.yaml

Usage (multi-GPU, e.g. 4 GPUs):
    torchrun --nproc_per_node=4 training/launch.py --config configs/train_config.yaml

Usage (multi-node):
    torchrun --nnodes=2 --nproc_per_node=4 --rdzv_backend=c10d \\
        --rdzv_endpoint=MASTER:29500 training/launch.py --config configs/train_config.yaml
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import torch
import torch.distributed as dist
import yaml

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.configuration import ModelArgs
from model.modeling import Transformer
from training.trainer import TrainConfig, Trainer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simple synthetic dataset (placeholder until real data pipeline is wired)
# ---------------------------------------------------------------------------

class SyntheticDataset(torch.utils.data.Dataset):
    """Random-token dataset for smoke-testing the training loop."""

    def __init__(self, vocab_size: int, seq_len: int, length: int = 10000):
        self.vocab_size = vocab_size
        self.seq_len = seq_len
        self.length = length

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        tokens = torch.randint(0, self.vocab_size, (self.seq_len,))
        return {"input_ids": tokens, "labels": tokens}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Launch distributed training")
    parser.add_argument("--config", type=str, default="configs/train_config.yaml", help="Path to YAML config")
    args = parser.parse_args()

    # Load YAML config
    with open(args.config) as f:
        raw_cfg = yaml.safe_load(f)

    train_cfg = TrainConfig.from_dict(raw_cfg)

    # Distributed init (torchrun sets these env vars automatically)
    if "RANK" in os.environ:
        dist.init_process_group(backend="nccl")
        rank = dist.get_rank()
    else:
        rank = 0

    # Seed
    torch.manual_seed(train_cfg.seed + rank)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(train_cfg.seed + rank)

    # Build model
    model_cfg = raw_cfg.get("model", {})
    model_args = ModelArgs(**{k: v for k, v in model_cfg.items() if k in ModelArgs.__dataclass_fields__})
    model = Transformer(model_args)

    n_params = sum(p.numel() for p in model.parameters())
    if rank == 0:
        logger.info(f"Model parameters: {n_params:,}")

    # Datasets
    data_cfg = raw_cfg.get("data", {})
    train_path = data_cfg.get("train_path")
    val_path = data_cfg.get("val_path")
    seq_len = data_cfg.get("seq_len", model_args.max_seq_len)

    if train_path:
        from data.dataset import PretokenizedDataset
        logger.info(f"Loading real dataset from {train_path}")
        train_ds = PretokenizedDataset(train_path, seq_len, split="train")
        val_ds = PretokenizedDataset(val_path or train_path, seq_len, split="val")
    else:
        logger.info("Using synthetic dataset")
        train_ds = SyntheticDataset(model_args.vocab_size, seq_len, length=50000)
        val_ds = SyntheticDataset(model_args.vocab_size, seq_len, length=1000)

    # Trainer
    trainer = Trainer(
        model=model,
        train_dataset=train_ds,
        val_dataset=val_ds,
        cfg=train_cfg,
    )
    trainer.train()

    # Cleanup
    if dist.is_initialized():
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
