#!/usr/bin/env python3
"""
Tests for the training loop.

1. Small model (2 layers, dim=128) trains for 10 steps → verify loss decreases.
2. Checkpoint save / load round-trip.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

import torch

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.configuration import ModelArgs
from model.modeling import Transformer
from training.trainer import TrainConfig, Trainer, get_lr


# ---------------------------------------------------------------------------
# Tiny dataset
# ---------------------------------------------------------------------------

class TinyDataset(torch.utils.data.Dataset):
    """Deterministic mini-dataset for reproducible tests."""

    def __init__(self, vocab_size: int, seq_len: int, size: int = 200):
        self.data = torch.randint(0, vocab_size, (size, seq_len))

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        tokens = self.data[idx]
        return {"input_ids": tokens, "labels": tokens}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_small_model(vocab_size: int = 512, dim: int = 128, n_layers: int = 2) -> Transformer:
    args = ModelArgs(
        dim=dim,
        n_layers=n_layers,
        n_heads=4,
        n_kv_heads=2,
        vocab_size=vocab_size,
        multiple_of=32,
        norm_eps=1e-5,
        max_seq_len=64,
        rope_theta=10000.0,
        use_bias=False,
    )
    return Transformer(args)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLRSchedule(unittest.TestCase):
    def test_warmup(self):
        cfg = TrainConfig(lr=1e-3, min_lr=1e-4, warmup_steps=100, max_steps=1000)
        # At step 0 → lr * 1/100
        lr0 = get_lr(0, cfg)
        self.assertAlmostEqual(lr0, 1e-3 * 1 / 100, places=8)
        # At step 99 (end of warmup) → lr * 100/100 = lr
        lr99 = get_lr(99, cfg)
        self.assertAlmostEqual(lr99, 1e-3, places=8)

    def test_cosine_decay(self):
        cfg = TrainConfig(lr=1e-3, min_lr=1e-4, warmup_steps=100, max_steps=1000)
        # At max_steps it should be min_lr
        lr_end = get_lr(1000, cfg)
        self.assertAlmostEqual(lr_end, 1e-4, places=8)
        # Mid-point should be between lr and min_lr
        lr_mid = get_lr(550, cfg)
        self.assertGreater(lr_mid, 1e-4)
        self.assertLess(lr_mid, 1e-3)


class TestTrainingLoop(unittest.TestCase):
    """Verify loss decreases over 10 steps with a tiny model."""

    def setUp(self):
        torch.manual_seed(42)
        self.vocab_size = 512
        self.seq_len = 64
        self.model = _make_small_model(vocab_size=self.vocab_size)
        self.train_ds = TinyDataset(self.vocab_size, self.seq_len, size=200)
        self.val_ds = TinyDataset(self.vocab_size, self.seq_len, size=50)
        self.tmpdir = tempfile.mkdtemp()

    def _make_trainer(self, max_steps: int = 10, **overrides) -> Trainer:
        cfg = TrainConfig(
            lr=1e-3,
            min_lr=1e-4,
            weight_decay=0.01,
            micro_batch_size=8,
            gradient_accumulation_steps=1,
            max_steps=max_steps,
            warmup_steps=2,
            dtype="fp32",  # CPU-friendly
            checkpoint_dir=self.tmpdir,
            checkpoint_interval=5,
            eval_interval=5,
            eval_steps=2,
            log_interval=1,
            fsdp_enabled=False,
            seed=42,
            **overrides,
        )
        return Trainer(
            model=self.model,
            train_dataset=self.train_ds,
            val_dataset=self.val_ds,
            cfg=cfg,
        )

    def test_loss_decreases(self):
        """Train 10 steps, collect loss at step 1 and step 10 — expect decrease."""
        trainer = self._make_trainer(max_steps=10)

        # Manually run the loop and record losses
        losses = []
        trainer.model.train()
        train_iter = iter(trainer.train_loader)

        for step in range(10):
            trainer.optimizer.zero_grad(set_to_none=True)
            try:
                batch = next(train_iter)
            except StopIteration:
                train_iter = iter(trainer.train_loader)
                batch = next(train_iter)

            input_ids = batch["input_ids"].to(trainer.device)
            labels = input_ids[:, 1:]
            input_ids = input_ids[:, :-1]

            logits = trainer.model(input_ids)
            loss = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                labels.reshape(-1),
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainer.model.parameters(), 1.0)

            lr = get_lr(step, trainer.cfg)
            for pg in trainer.optimizer.param_groups:
                pg["lr"] = lr
            trainer.optimizer.step()

            losses.append(loss.item())

        # Loss at end should be lower than at start (with reasonable probability
        # for a random-token dataset + tiny model)
        self.assertLess(losses[-1], losses[0],
                        f"Expected loss to decrease: {losses[0]:.4f} → {losses[-1]:.4f}")

    def test_trainer_train_method(self):
        """Smoke test: the full Trainer.train() runs without error."""
        trainer = self._make_trainer(max_steps=3)
        trainer.train()
        self.assertEqual(trainer.global_step, 3)


class TestCheckpointing(unittest.TestCase):
    """Verify checkpoint round-trip: save → load → same weights & step."""

    def setUp(self):
        torch.manual_seed(42)
        self.tmpdir = tempfile.mkdtemp()
        self.vocab_size = 512
        self.seq_len = 64

    def test_save_load_roundtrip(self):
        model = _make_small_model(vocab_size=self.vocab_size)
        ds = TinyDataset(self.vocab_size, self.seq_len, size=100)

        cfg = TrainConfig(
            lr=1e-3,
            min_lr=1e-4,
            micro_batch_size=8,
            gradient_accumulation_steps=1,
            max_steps=5,
            warmup_steps=1,
            dtype="fp32",
            checkpoint_dir=self.tmpdir,
            checkpoint_interval=5,
            eval_interval=100,
            log_interval=1,
            fsdp_enabled=False,
            seed=42,
        )
        trainer = Trainer(model=model, train_dataset=ds, cfg=cfg)
        trainer.train()

        # Save
        ckpt_path = os.path.join(self.tmpdir, "test_ckpt.pt")
        trainer.global_step = 5
        trainer.save_checkpoint(tag="test_ckpt")

        # Record weights
        original_params = {k: v.clone() for k, v in trainer.model.state_dict().items()}
        original_step = trainer.global_step

        # Create fresh model + trainer and load
        model2 = _make_small_model(vocab_size=self.vocab_size)
        trainer2 = Trainer(model=model2, train_dataset=ds, cfg=cfg)
        trainer2.load_checkpoint(ckpt_path)

        self.assertEqual(trainer2.global_step, original_step)

        for name, param in trainer2.model.state_dict().items():
            self.assertTrue(
                torch.allclose(param, original_params[name], atol=1e-6),
                f"Parameter {name} mismatch after checkpoint reload",
            )


if __name__ == "__main__":
    unittest.main()
