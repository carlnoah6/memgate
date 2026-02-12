# Cloud Training Test Run Plan

## Overview
**Date:** 2026-02-10
**Task:** t109 - Cloud Training Test Run: Plan & Scripts
**Status:** 🚧 Planned

## Objective
To prepare and test a configuration for a cloud-based training run. This includes:
1.  Defining a realistic model configuration (larger than the dry run, but still manageable for a test).
2.  Enabling distributed training features (FSDP, mixed precision).
3.  Creating the necessary configuration and launch scripts.
4.  Performing a test run to verify the setup.

## Configuration
**Config File:** `configs/cloud_test_config.yaml`

```yaml
# =============================================================================
# Cloud Training Test Run Configuration
# =============================================================================

# --- Model (Small for test run) ---
model:
  dim: 512
  n_layers: 4
  n_heads: 8
  n_kv_heads: 4
  vocab_size: 2048
  multiple_of: 64
  ffn_dim_multiplier: null
  norm_eps: 1e-5
  max_seq_len: 256
  rope_theta: 10000.0
  use_bias: false

# --- Training (Short duration) ---
training:
  # Optimization
  lr: 3e-4
  min_lr: 3e-5
  weight_decay: 0.1
  beta1: 0.9
  beta2: 0.95
  grad_clip_max_norm: 1.0

  # Batch sizing
  micro_batch_size: 4
  gradient_accumulation_steps: 1

  # Schedule
  max_steps: 50
  warmup_steps: 5

  # Mixed precision
  dtype: fp16

  # Checkpointing
  checkpoint_dir: checkpoints/cloud_test
  checkpoint_interval: 10
  resume_from: null

  # Evaluation
  eval_interval: 10
  eval_steps: 1

  # Logging
  log_interval: 1
  wandb_project: null

  # Reproducibility
  seed: 42

# --- Data ---
data:
  train_path: null # Uses synthetic data in launch.py
  val_path: null
  seq_len: 256
  num_workers: 0

# --- Distributed ---
distributed:
  backend: nccl
  fsdp:
    enabled: true
    sharding_strategy: FULL_SHARD
    mixed_precision: true
    activation_checkpointing: false
    cpu_offload: false
```

## Launch Script
**Script:** `launch_cloud_test.py`

```python
from launch import launch_training

if __name__ == "__main__":
    # Launch the training with the cloud test configuration
    launch_training("configs/cloud_test_config.yaml")
```

## Execution Plan
1.  Run `python3 launch_cloud_test.py`.
2.  Monitor the logs for any errors.
3.  Verify that checkpoints are created in `checkpoints/cloud_test/`.
4.  Update this wiki page with the execution summary.
