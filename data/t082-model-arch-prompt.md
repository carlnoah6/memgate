# Research Task: Model Architecture Implementation (t082)

## 目标
基于 "从零训练模型" 路线图 (Phase 2)，实现 7B 参数量的 Llama-style 模型架构。

## 任务清单
1. **创建模型配置 (`model/configuration.py`)**:
   - 定义 `ModelArgs` dataclass。
   - 默认参数 (7B):
     - `dim = 4096`
     - `n_layers = 32`
     - `n_heads = 32`
     - `n_kv_heads = 8` (GQA)
     - `vocab_size = 100000`
     - `multiple_of = 256` (SwiGLU hidden dim)
     - `norm_eps = 1e-5`
     - `max_seq_len = 4096`
     - `rope_theta = 500000`

2. **实现模型结构 (`model/modeling.py`)**:
   - 使用 PyTorch (`torch.nn`).
   - 核心组件:
     - `RMSNorm`: Pre-normalization.
     - `RoPE` (Rotary Positional Embeddings): 使用 `complex64` 极坐标实现或预计算 cache。
     - `Attention`: 支持 GQA (Grouped Query Attention) 和 Flash Attention (调用 `torch.nn.functional.scaled_dot_product_attention`).
     - `FeedForward`: SwiGLU 激活 (w1, w2, w3 gates).
     - `TransformerBlock`: 组合 Attn + FFN + Norm.
     - `Transformer`: 主模型类。

3. **简单验证 (`tests/test_model_init.py`)**:
   - 编写脚本实例化模型，打印参数量（应约为 7.2B）。
   - 运行一次 forward pass (使用随机 dummy input) 验证无报错。

4. **同步到 Wiki**:
   - 将代码和架构说明写入 Wiki。
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Model Architecture (7B Llama-style)"

5. **更新 Backlog**:
   - 在 `data/backlog.md` 中新增 "Phase 2: Pre-training" 章节（如果尚未存在），并标记 "模型架构实现" 为完成。

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`

## 任务管理
- 任务 ID: t082
- 完成后运行: `python3 scripts/task-manager.py complete t082 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t082 "错误原因"`
