# Inference Script

## 概述

基于已完成的 Transformer 模型架构（GQA + RoPE + SwiGLU），实现了完整的文本生成推理引擎，支持 KV-cache 加速、多种采样策略、批量推理和流式输出。

## 文件结构

- `inference/generate.py` — 推理引擎核心，包含 `TextGenerator` 类
- `inference/cli.py` — 命令行交互工具（REPL + HTTP API）
- `model/modeling.py` — 模型已扩展 KV-cache 支持（向后兼容）
- `tests/test_inference.py` — 12 个测试用例，全部通过

## 推理引擎 (inference/generate.py)

### TextGenerator 类

**加载模型：**
- `TextGenerator.from_checkpoint(path)` — 从 checkpoint 目录或 .pt 文件加载
- `TextGenerator.from_model(model)` — 包装已有模型实例

**生成方法：**
- `generate(prompt_tokens, ...)` — 返回完整序列 (prompt + generated)
- `generate_stream(prompt_tokens, ...)` — 逐 token yield，适合流式输出
- `generate_batch(prompts, ...)` — 变长 prompt 列表批量推理

### 采样策略

- **Greedy**: `greedy=True` 或 `temperature=0`
- **Temperature scaling**: 控制分布锐度
- **Top-k filtering**: 只保留概率最高的 k 个 token
- **Top-p (nucleus)**: 只保留累计概率达到 p 的最小 token 集合
- 以上策略可自由组合

### KV-Cache 加速

- 模型 `Attention` 层新增 `KVCache` 类
- Prefill 阶段一次性处理全部 prompt token
- Decode 阶段每步只计算 1 个 token 的 QKV，复用缓存的 K/V
- 生成完成后自动清理缓存
- 测试验证: cache 模式与 no-cache 模式输出完全一致

## CLI 工具 (inference/cli.py)

### 用法

```
python -m inference.cli --model_path checkpoints/step-10000
```

### 参数

- `--model_path` — checkpoint 路径（必需）
- `--max_tokens` — 最大生成 token 数（默认 128）
- `--temperature` — 采样温度（默认 1.0，0 = greedy）
- `--top_k` — Top-k 过滤（默认 0 = 不启用）
- `--top_p` — Nucleus 过滤（默认 1.0 = 不启用）
- `--device` — 推理设备（cpu / cuda / mps）
- `--prompt` — 单次生成（不进入 REPL）
- `--serve` — 启动 HTTP API 服务器
- `--port` — API 端口（默认 8000）

### REPL 模式

不传 `--prompt` 时自动进入交互式 REPL，支持多轮对话式生成。

### HTTP API

`--serve` 模式启动简易 JSON API：

```
POST / {"prompt": "Hello", "max_tokens": 64, "temperature": 0.8}
→ {"text": "Hello ..."}
```

## 测试 (tests/test_inference.py)

12 个测试，全部通过：

- **TestGenerationShape** (4 tests) — 验证输出 shape、batch、流式 yield 数量、EOS 停止
- **TestKVCache** (2 tests) — 验证 cache/no-cache 输出一致性、缓存自动清理
- **TestSampling** (4 tests) — 验证 temperature=0 ≡ greedy、top-k/top-p 约束
- **TestBatchInference** (1 test) — 验证变长 prompt 批量推理

## 模型改动 (model/modeling.py)

为支持 KV-cache，对模型做了最小化向后兼容改动：

- 新增 `KVCache` 类（管理每层 K/V 缓存）
- `Attention.forward()` 新增可选 `use_cache` 参数
- `Transformer.forward()` 新增可选 `start_pos` 和 `use_cache` 参数
- `Transformer.init_cache()` / `clear_cache()` 方法
- **所有改动向后兼容**，不传新参数时行为与原版一致
