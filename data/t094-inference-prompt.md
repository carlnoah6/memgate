# Research Task: Inference Script (t094)

## 目标
基于已完成的模型架构，实现文本生成推理脚本。

## 任务清单
1. **实现推理引擎 (`inference/generate.py`)**:
   - 加载训练好的 checkpoint
   - 实现 autoregressive generation loop
   - 支持采样策略: greedy, top-k, top-p (nucleus), temperature scaling
   - KV-cache 加速推理
   - 支持 batch inference
   - 流式输出 (yield tokens)

2. **实现 CLI (`inference/cli.py`)**:
   - 命令行交互模式 (REPL)
   - 支持参数: `--model_path`, `--max_tokens`, `--temperature`, `--top_k`, `--top_p`
   - 可选: 简单的 HTTP API server

3. **编写测试 (`tests/test_inference.py`)**:
   - 用小模型验证 generation 输出 shape 正确
   - 验证 KV-cache 与非 cache 输出一致
   - 验证 temperature=0 等同 greedy

4. **同步到 Wiki**:
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Inference Script"

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`
- **已有代码**: `model/configuration.py`, `model/modeling.py`

## 任务管理
- 任务 ID: t094
- 完成后运行: `python3 scripts/task-manager.py complete t094 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t094 "错误原因"`
