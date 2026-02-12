# Research Task: Evaluation Framework (t097)

## 目标
基于 "从零训练模型" 路线图 Phase 3，实现模型评估框架。

## 任务清单
1. **实现评估框架 (`evaluation/evaluator.py`)**:
   - 通用评估基类，支持插件式 benchmark
   - 支持 few-shot prompting (0-shot, 5-shot)
   - 自动化评分（accuracy, pass@k, exact match）

2. **实现核心 Benchmark (`evaluation/benchmarks/`)**:
   - `mmlu.py` — MMLU (多领域知识，57 科目)
   - `humaneval.py` — HumanEval (代码生成，pass@1)
   - `gsm8k.py` — GSM8K (数学推理)
   - 每个 benchmark：数据加载 + prompt 构建 + 评分

3. **实现评估脚本 (`evaluation/run_eval.py`)**:
   - CLI: `--model_path`, `--benchmarks`, `--num_fewshot`, `--output_dir`
   - 输出 JSON 结果 + Markdown 报告

4. **编写测试 (`tests/test_evaluation.py`)**:
   - 用 mock model 验证评估流程
   - 验证 prompt 格式正确
   - 验证评分逻辑

5. **同步到 Wiki**:
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Evaluation Framework"

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`

## 任务管理
- 任务 ID: t097
- 完成后运行: `python3 scripts/task-manager.py complete t097 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t097 "错误原因"`
