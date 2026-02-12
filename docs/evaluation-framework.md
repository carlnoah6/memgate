# Evaluation Framework

## 概述

模型评估框架，支持标准化 benchmark 评估，包括 MMLU、HumanEval、GSM8K。框架采用插件式架构，可灵活扩展新的 benchmark。

## 架构设计

### 核心组件

```
evaluation/
├── __init__.py          # Package init + benchmark registry
├── evaluator.py         # 核心框架：Evaluator, Benchmark base class, scoring
├── benchmarks/
│   ├── __init__.py
│   ├── mmlu.py          # MMLU (57 科目多选题)
│   ├── humaneval.py     # HumanEval (代码生成 pass@k)
│   └── gsm8k.py         # GSM8K (数学推理 CoT)
└── run_eval.py          # CLI 评估入口
```

### 设计原则

- **Plugin-based**: 新增 benchmark 只需继承 `Benchmark` 基类，实现 4 个方法
- **Protocol-based**: 通过 Python Protocol 解耦 model/tokenizer 接口
- **Reproducible**: 固定 seed，确定性 few-shot 选择
- **Testable**: 完整 mock 测试，41 个测试用例全部通过

## Benchmark 详情

### MMLU (Massive Multitask Language Understanding)

| 属性 | 值 |
|------|-----|
| 科目 | 57 个学科 |
| 格式 | 四选一 (A/B/C/D) |
| 评分 | 选项准确率 |
| Few-shot | 支持 0-shot / 5-shot |
| 生成长度 | 5 tokens |

**Prompt 格式:**
```
The following are multiple choice questions about {subject}.

{few-shot examples with answers}

{question}
A. ...  B. ...  C. ...  D. ...
Answer:
```

### HumanEval (Code Generation)

| 属性 | 值 |
|------|-----|
| 题目 | 164 道编程题 |
| 格式 | 函数补全 |
| 评分 | pass@k (执行测试用例) |
| Few-shot | 不适用（prompt 即为函数签名） |
| 生成长度 | 512 tokens |

**安全执行:** 沙盒环境 + 10s 超时，防止恶意/无限循环代码。

### GSM8K (Grade School Math)

| 属性 | 值 |
|------|-----|
| 题目 | 8.5K 小学数学应用题 |
| 格式 | 自由文本 + 数字答案 |
| 评分 | 最终数字精确匹配 |
| Few-shot | 支持 chain-of-thought |
| 生成长度 | 512 tokens |

**数字提取支持:**
- GSM8K 格式: `#### 42`
- LaTeX: `\boxed{42}`
- 自然语言: "The answer is 42"
- Fallback: 文本中最后一个数字

## 评分工具

| 方法 | 用途 |
|------|------|
| `exact_match()` | 大小写不敏感 + 空白规范化的精确匹配 |
| `accuracy_score()` | 计算正确率 |
| `pass_at_k()` | Chen et al., 2021 的无偏 pass@k 估计器 |

## CLI 使用

```bash
# 完整评估
python -m evaluation.run_eval \
    --model_path checkpoints/step-10000 \
    --benchmarks mmlu gsm8k humaneval \
    --num_fewshot 5 \
    --output_dir eval_results/run1

# 快速测试（合成数据）
python -m evaluation.run_eval \
    --benchmarks mmlu \
    --max_samples 10

# 参数
--model_path     模型检查点路径
--benchmarks     要运行的 benchmark 列表
--num_fewshot    few-shot 示例数量 (默认 0)
--output_dir     输出目录 (默认 eval_results)
--max_samples    每个 benchmark 最大样本数
--temperature    采样温度 (默认 0.0 = greedy)
--device         推理设备 (cpu/cuda)
```

## 输出格式

### JSON (`results.json`)
```json
{
  "results": [...],
  "summary": {
    "mmlu": {"accuracy": 0.45, "num_samples": 14042, ...},
    "gsm8k": {"accuracy": 0.32, ...}
  }
}
```

### Markdown (`report.md`)
表格化汇总 + 每个 benchmark 的详细指标。

## 测试

```bash
python3 -m pytest tests/test_evaluation.py -v
# 41 tests passed ✅
```

测试覆盖:
- 评分工具函数 (11 tests)
- MMLU prompt 构建 + 评分 (6 tests)
- HumanEval 代码执行 + 评分 (5 tests)
- GSM8K 数字提取 + 评分 (7 tests)
- Evaluator 集成测试 (7 tests)
- Few-shot prompt 格式验证 (5 tests)

## 路线图集成

本框架属于 Phase 3 "模型评估"，与现有组件的关系：

- **model/** — `Transformer` 模型定义
- **inference/** — `TextGenerator` 推理引擎 (通过 Protocol 解耦)
- **evaluation/** — 本框架 ← **Phase 3 新增**
