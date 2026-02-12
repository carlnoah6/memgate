# Training Loop Implementation

Phase 2 of the "从零训练模型" (Train from Scratch) roadmap: a production-ready distributed training loop built on PyTorch FSDP.

## Overview

The training loop supports single-GPU and multi-node distributed training with:
- **PyTorch FSDP** (Fully Sharded Data Parallel)
- **Mixed precision** (bf16 / fp16 / fp32)
- **Linear warmup + cosine decay** LR schedule
- **Gradient clipping** (max_norm=1.0)
- **Checkpoint save/load** (model + optimizer + scheduler state)
- **WandB integration** (optional, via `WANDB_DISABLED` env var)
- **Throughput logging** (tokens/sec, loss, lr, grad norm)

## File Structure

```
configs/train_config.yaml     # Training hyperparameters
training/trainer.py            # Core Trainer class + TrainConfig
training/launch.py             # torchrun-compatible launch script
tests/test_training_loop.py    # Validation tests (5 tests, all passing)
```

## Key Hyperparameters

| Parameter | Value |
|---|---|
| Learning rate | 3e-4 (warmup) → 3e-5 (cosine floor) |
| Warmup steps | 2,000 |
| Max steps | 100,000 |
| Micro batch size | 4 |
| Gradient accumulation | 8 |
| Mixed precision | bf16 |
| Gradient clip | 1.0 |
| Checkpoint interval | Every 1,000 steps |
| Eval interval | Every 500 steps |
| Optimizer | AdamW (β1=0.9, β2=0.95, wd=0.1) |

## Usage

**Single GPU:**
```bash
python training/launch.py --config configs/train_config.yaml
```

**Multi-GPU (4 GPUs):**
```bash
torchrun --nproc_per_node=4 training/launch.py --config configs/train_config.yaml
```

**Multi-node (2 nodes × 4 GPUs):**
```bash
torchrun --nnodes=2 --nproc_per_node=4 \
    --rdzv_backend=c10d --rdzv_endpoint=MASTER:29500 \
    training/launch.py --config configs/train_config.yaml
```

## Tests

All 5 unit tests pass:

- `TestLRSchedule.test_warmup` — verifies linear warmup ramp
- `TestLRSchedule.test_cosine_decay` — verifies cosine decay to min_lr
- `TestTrainingLoop.test_loss_decreases` — trains tiny model (2 layers, dim=128) for 10 steps; confirms loss drops
- `TestTrainingLoop.test_trainer_train_method` — smoke test for full `Trainer.train()` method
- `TestCheckpointing.test_save_load_roundtrip` — saves checkpoint, loads into fresh model, verifies weights match

## Architecture Decisions

1. **FSDP over DDP**: We use FSDP to shard model parameters, gradients, and optimizer states across GPUs. This is essential for training 1B+ parameter models that don't fit in single-GPU memory.

2. **`use_orig_params=True`**: Enables parameter-level optimizer states and is compatible with `torch.compile`.

3. **Manual LR scheduling**: Instead of `torch.optim.lr_scheduler`, we compute LR directly at each step for full control over warmup + cosine decay.

4. **Gradient accumulation**: Loss is divided by `gradient_accumulation_steps` before backward, and gradients are clipped after all micro-steps complete.

5. **TrainConfig dataclass**: The config is a pure Python dataclass that can be built from YAML (via `from_dict`) or constructed directly in code/tests.
