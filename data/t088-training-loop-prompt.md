# Research Task: Training Loop Implementation (t088)

## 目标
基于 "从零训练模型" 路线图 Phase 2，实现分布式训练循环。

## 任务清单
1. **创建训练配置 (`configs/train_config.yaml`)**:
   - 学习率: 3e-4 (warmup + cosine decay)
   - Batch size: micro_batch=4, gradient_accumulation=8
   - 混合精度: bf16
   - Max steps: 100000
   - Checkpoint interval: 1000 steps
   - Eval interval: 500 steps
   - Warmup steps: 2000

2. **实现训练脚本 (`training/trainer.py`)**:
   - 支持 PyTorch FSDP (Fully Sharded Data Parallel)
   - 实现核心训练循环: forward → loss → backward → optimizer step
   - Learning rate scheduler: linear warmup + cosine decay
   - Gradient clipping (max_norm=1.0)
   - Mixed precision (torch.cuda.amp / bf16)
   - Checkpoint saving/loading (model + optimizer + scheduler state)
   - Logging: loss, lr, throughput (tokens/sec), gradient norm
   - WandB integration (optional, 用环境变量控制)

3. **实现启动脚本 (`training/launch.py`)**:
   - `torchrun` compatible 启动方式
   - 支持单卡和多卡训练

4. **编写验证脚本 (`tests/test_training_loop.py`)**:
   - 用小模型 (2 layers, dim=128) 跑 10 步验证 loss 下降
   - 验证 checkpoint save/load 正确性

5. **同步到 Wiki**:
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Training Loop Implementation"

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`
- **模型代码**: 已完成的 `model/configuration.py` 和 `model/modeling.py`

## 任务管理
- 任务 ID: t088
- 完成后运行: `python3 scripts/task-manager.py complete t088 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t088 "错误原因"`
