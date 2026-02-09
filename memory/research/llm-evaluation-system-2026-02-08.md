# LLM 评估体系：Benchmark 选择与评估框架搭建

> 研究日期：2026-02-08
> 系列：从零训练 LLM + 视觉模型（第 9 篇）
> 关键词：Benchmark、MMLU、HumanEval、GSM8K、lm-evaluation-harness、OpenCompass、Chatbot Arena

---

## 一、为什么需要评估体系

训练一个 LLM 不仅是把 loss 降下来那么简单。loss 下降只能说明模型在学习分布，但无法回答"它到底学会了什么"、"在哪些任务上表现好"、"还有哪些明显短板"。评估体系就是回答这些问题的工具。

评估体系在训练全流程中扮演多重角色：

1. **训练监控**：在预训练过程中定期在验证集和 benchmark 上跑分，追踪能力增长曲线，及时发现问题（如某一类能力突然退化）。
2. **模型选型与比较**：不同架构、不同数据配比、不同超参的模型需要一个公平的比较标准。
3. **对齐验证**：SFT、RLHF/DPO 后模型是否变得更好用、更安全、更少幻觉，都需要评估来量化。
4. **发布决策**：何时模型"够好了"可以上线？需要在关键指标上设定阈值。
5. **领域适配**：如果要做特定领域的模型（如法律、金融），还需要领域特定的评估集。

好的评估体系应该是**多维度**的——不依赖单一指标，而是覆盖知识、推理、代码、安全等多个方面；同时应该是**可复现**的——使用标准化框架和公开数据集，确保结果可对比。

---

## 二、主流 Benchmark 全景

### 2.1 知识与语言理解

#### MMLU（Massive Multitask Language Understanding）

MMLU 是最经典也是引用最多的 LLM 评估基准之一。由 Hendrycks 等人于 2020 年提出，包含 57 个学科的 15,000+ 多选题，涵盖数学、历史、计算机科学、法律等领域，难度从高中到专家级别不等。

- **评估方式**：每个学科计算正确率，最终取 57 个学科的平均分
- **评测设置**：通常使用 5-shot 设置
- **数据集**：[HuggingFace](https://huggingface.co/datasets/cais/mmlu)
- **现状**：截至 2025 年中，主流模型（Claude 3.5、GPT-4o、Llama 3.1 405B）均稳定在 88% 以上，MMLU 已部分被更难的替代品取代

#### MMLU-Pro

MMLU 的增强版本，由 TIGER-AI-Lab 于 2024 年提出（NeurIPS 2024）。主要改进：

- 选项从 4 个扩展到 **10 个**，显著降低猜测正确的概率
- 剔除了简单的"记忆型"问题，增加更多需要推理的题目
- 包含 12,000+ 题，覆盖 14 个领域（生物、商业、化学、计算机科学、经济学、工程、健康、历史、法律、数学、哲学、物理、心理学等）
- **区分度更强**：在原版 MMLU 上得分接近的模型，在 MMLU-Pro 上会拉开明显差距

这是 Hugging Face Open LLM Leaderboard v2 采用的核心 benchmark 之一。

#### GPQA（Google-Proof QA）

面向研究生级别的科学问答基准，包含约 200 道专家编写的物理、生物、化学题目。题目被设计为"Google-proof"——即使搜索互联网也很难找到答案，必须依靠深层推理。GPQA-Diamond 是其精选高难度子集。

#### SuperGLUE

自然语言理解的经典基准，继承自 GLUE，包含 8 个子任务（如 BoolQ、WiC、MultiRC 等），测试语言推理、消歧、阅读理解等能力。虽然现代大模型已接近或超越人类水平，但仍常作为基础能力的 sanity check。

### 2.2 推理能力

#### GSM8K（Grade School Math 8K）

由 OpenAI 提出的小学数学应用题数据集，包含 8,500 道需要 2-8 步推理的数学应用题。虽然看起来简单，但它有效地测试了模型的多步推理和算术能力。

- **评估方式**：精确匹配最终数值答案
- **关键技巧**：Chain-of-Thought（CoT）提示显著提升表现
- **现状**：顶级模型已接近饱和（95%+），但中小模型仍有明显差距

#### MATH

更高难度的数学推理基准，包含竞赛级别的数学问题（AMC、AIME 等），分为 5 个难度级别。Level 5 子集常被单独使用。Open LLM Leaderboard v2 使用的就是 MATH Level 5。

- **评估方式**：需要生成特定格式的答案（如 LaTeX 表达式），只有精确匹配才算正确
- **区分度高**：即使是最强的模型，在 Level 5 上也很难达到 50% 以上

#### AIME 2025

美国数学邀请赛（American Invitational Mathematics Examination）2025 年的 30 道题，用于测试顶级模型的高级数学推理。优势在于题目完全是新的，不存在数据污染问题。

#### BBH（Big-Bench Hard）

从 BIG-Bench 的 204 个任务中选出 23 个最具挑战性的任务组成，这些任务是早期模型（如 GPT-3）无法解决的。涵盖组合推理、因果推断、逻辑推理等。虽然部分已被认为"接近饱和"，但仍是评估综合推理能力的重要基准。

#### MuSR（Multistep Soft Reasoning）

测试多步推理和长程上下文解析的基准，很少有模型能超过随机水平，难度极高。是 Open LLM Leaderboard v2 的组成部分之一。

#### DROP（Discrete Reasoning Over Paragraphs）

阅读理解 + 离散推理的混合基准，包含 96,000 个问题，需要模型在阅读文本的基础上进行算术、排序、计数等操作。

### 2.3 代码生成

#### HumanEval

由 OpenAI 提出的代码生成基准，包含 164 道手写 Python 编程题，类似简单的软件面试题。

- **评估指标**：pass@k——模型生成 k 个代码样本，至少有一个通过所有单元测试的概率
- **常用设置**：pass@1（只生成一次就通过的概率）
- **局限**：题目规模小（仅 164 题）、仅限 Python、存在明显的数据泄漏问题

#### HumanEval+

修复了原版 HumanEval 中测试不充分和题目描述模糊的问题，增加了更多测试用例，评估更可靠。

#### MBPP（Mostly Basic Python Programming）

另一个 Python 编程基准，包含 974 个简单编程任务，与 HumanEval 互为补充。

#### LiveCodeBench

为解决代码 benchmark 的数据污染问题而设计的"活"基准——持续从编程竞赛平台收集新题目，确保测试数据不可能出现在训练集中。分为 Easy、Medium、Hard 三个难度。

- **核心优势**：无数据污染、持续更新
- **发现**：在 HumanEval 上表现好的模型不一定在 LiveCodeBench 上表现好，暗示部分模型可能过拟合了 HumanEval

#### SWE-bench

由普林斯顿和 OpenAI 合作提出，包含 2,294 个真实 GitHub Issue。模型需要阅读代码库，编写补丁来修复 issue，并通过所有测试。这是最接近真实开发工作流的代码评估基准。

- **SWE-bench Verified**：经过人工验证的高质量子集
- **评估方式**：修复成功率（通过所有相关测试的 issue 比例）

#### BigCodeBench

1,140 个多样化的真实编程任务，超越简单算法题，测试模型在复杂函数调用和规范理解方面的能力。

### 2.4 指令遵循

#### IFEval（Instruction Following Evaluation）

专注于模型指令遵循能力的基准，测试模型能否准确执行各种格式化指令（如"用JSON格式回答"、"不超过100字"、"包含关键词X"等）。这不是测内容质量，而是测模型能否精确按照指令行事。

是 Open LLM Leaderboard v2 的六个核心 benchmark 之一。

### 2.5 安全与真实性

#### TruthfulQA

测试模型是否会复制人类的常见错误认知，包含 817 个问题覆盖 38 个主题（健康、法律、金融、政治等）。

- **评估方式**：使用微调后的 "GPT-Judge" 模型评判回答的真实性
- **注意**：近年已出现饱和迹象，因为该数据集可能已进入部分模型的训练数据

#### DecodingTrust

全面评估 LLM 可信度的框架，从 8 个维度评估：毒性、刻板印象、隐私、机器伦理、公平性、对抗鲁棒性、分布外鲁棒性、对抗演示鲁棒性。

#### HalluLens

2025 年提出的幻觉评估基准，建立了清晰的幻觉分类法（外在幻觉 vs 内在幻觉 vs 事实性挑战），并提供可动态再生的测试数据以防止饱和。

### 2.6 中文评估

#### C-Eval

中文大模型综合能力评估基准，包含 13,948 道多选题，覆盖 52 个学科，分为 4 个难度级别。是评估中文模型的首选基准之一。

#### CMMLU

中文大规模多任务语言理解基准，类似 MMLU 的中文版本，涵盖自然科学、社会科学、工程、人文等领域。

#### GAOKAO-BENCH

以中国高考题为基础的评估基准，覆盖语文、数学、英语、理综、文综等科目，具有很好的区分度和实用价值。

### 2.7 人类偏好评估

#### Chatbot Arena（LMArena）

由 LMSYS 推出的众包评估平台。核心机制：

- 用户同时与两个匿名模型对话
- 投票选择更好的回答
- 使用 Bradley-Terry 模型计算 Elo 分数
- 已收集超过 100 万用户投票

**为什么重要**：Chatbot Arena 的 Elo 分数已成为业界引用最多的 LLM 排名标准，甚至超过了学术 benchmark。它反映的是真实用户的偏好，而非人工设计的任务。

#### MT-bench

多轮对话评估基准，包含 80 个高质量多轮问题，使用 GPT-4 作为评判者（LLM-as-a-judge），自动评估回答质量。

### 2.8 新兴与前沿 Benchmark

#### Humanity's Last Exam（HLE）

由领域专家策划的超高难度基准，涵盖数学、科学等领域，当前顶级模型得分低于 10%。被设计为"最后的考试"——当模型能通过时，意味着接近 AGI 水平。

#### ARC-AGI

François Chollet 提出的抽象推理基准，测试模式识别和类比推理能力，被认为是衡量通向 AGI 进展的标尺。

#### PaperBench

OpenAI 推出的基准，测试 AI 能否从零复现最新 ML 论文（如 ICML 2024 论文），需要规划、编码、实验全流程能力。

#### MLE-Bench

75 个真实 ML 任务（如 Kaggle 竞赛），评估端到端的机器学习工程能力。

---

## 三、主流评估框架

### 3.1 lm-evaluation-harness（EleutherAI）

**这是最重要的评估框架**，是 Hugging Face Open LLM Leaderboard 的后端，被 NVIDIA、Cohere、BigScience、Mosaic ML 等数十个组织内部使用。

#### 核心特性

- 支持 200+ 预配置 benchmark
- 支持多种模型后端：HuggingFace Transformers（含 GPTQ 量化）、vLLM、GPT-NeoX、OpenAI API 等
- 基于 YAML 配置文件定义评估任务，完全可复现
- 支持 few-shot 评估和 chain-of-thought
- 活跃的社区和持续更新

#### 安装与使用

```bash
# 安装
git clone --depth 1 https://github.com/EleutherAI/lm-evaluation-harness
cd lm-evaluation-harness
pip install -e ".[math,ifeval,sentencepiece]"

# 基础评估（以 HuggingFace 模型为例）
lm_eval --model hf \
  --model_args pretrained=meta-llama/Llama-2-7b-hf \
  --tasks mmlu,gsm8k,hellaswag \
  --batch_size 8 \
  --num_fewshot 5

# 使用 OpenAI API 评估
lm_eval --model openai-chat-completions \
  --model_args model=gpt-4 \
  --tasks mmlu \
  --num_fewshot 5

# 运行 Open LLM Leaderboard v2 的完整评估
lm_eval --model hf \
  --model_args pretrained=your-model \
  --tasks leaderboard \
  --batch_size auto
```

#### Open LLM Leaderboard v2 的 6 个 Benchmark

| Benchmark | Shots | 测试内容 |
|-----------|-------|---------|
| IFEval | 0 | 指令遵循 |
| BBH | 3 | 复杂推理 |
| MATH Lv5 | 4 | 竞赛数学 |
| GPQA | 0 | 研究生级科学 |
| MuSR | 0 | 多步推理 |
| MMLU-Pro | 5 | 知识广度 |

#### 自定义评估任务

lm-eval 支持通过 YAML 文件定义自定义任务：

```yaml
task: my_custom_task
dataset_path: my_dataset
dataset_name: default
output_type: multiple_choice
training_split: train
test_split: test
doc_to_text: "Question: {{question}}\nAnswer:"
doc_to_target: "{{answer}}"
metric_list:
  - metric: acc
    aggregation: mean
    higher_is_better: true
```

### 3.2 OpenCompass

**最适合中文模型评估的框架**，由上海 AI 实验室开发，支持 100+ 数据集。

#### 核心特性

- 支持五大维度评估：学科、语言、知识、理解、推理
- 原生支持中文基准：C-Eval、CMMLU、GAOKAO-BENCH 等
- 支持多种模型接入（Llama、Qwen、GLM、GPT-4 等）
- 支持从 ModelScope 按需加载数据集
- OpenMMLab 风格的 Python 配置文件

#### 安装与使用

```bash
# 安装
git clone https://github.com/open-compass/opencompass
cd opencompass
pip install -e .

# 运行评估
python run.py --models hf_llama_7b --datasets ceval_gen mmlu_gen gsm8k_gen

# 使用配置文件
python run.py configs/eval_demo.py
```

#### 支持的数据集（部分）

- **通用**：MMLU、ARC、HellaSwag、TruthfulQA
- **中文**：C-Eval、CMMLU、GAOKAO-BENCH、OCNLI、CMNLI
- **推理**：GSM8K、MATH、BBH、AGIEval
- **代码**：HumanEval、MBPP
- **长文本**：支持长上下文评估

### 3.3 EvalScope（阿里巴巴 ModelScope）

阿里开发的评估框架，特点是轻量、易定制，与 ms-swift 微调框架无缝集成。

- 预配置支持 MMLU、CMMLU、C-Eval、GSM8K、ARC、HellaSwag、TruthfulQA、MATH、HumanEval 等
- 可通过 OpenCompass 插件扩展评估能力
- 适合在 ModelScope 生态中使用

### 3.4 DeepEval

专注于 LLM 应用评估的框架（而非纯模型评估），支持运行标准 benchmark，同时提供 RAG、对话质量等应用级评估指标。

### 3.5 框架对比

| 特性 | lm-eval-harness | OpenCompass | EvalScope |
|------|----------------|-------------|-----------|
| 维护方 | EleutherAI | 上海 AI 实验室 | 阿里 ModelScope |
| Benchmark 数量 | 200+ | 100+ | 30+ |
| 中文支持 | 有限 | 原生强 | 原生强 |
| 社区活跃度 | 极高 | 高 | 中 |
| HF 集成 | 原生 | 支持 | 支持 |
| 自定义任务 | YAML | Python Config | Python |
| 推荐场景 | 英文模型、开源排行榜 | 中文/中英双语模型 | ModelScope 生态 |

---

## 四、评估体系搭建实践

### 4.1 评估维度设计

一个完整的评估体系应覆盖以下维度：

```
评估体系
├── 基础能力
│   ├── 语言理解：MMLU-Pro / SuperGLUE
│   ├── 常识推理：HellaSwag / ARC
│   └── 知识广度：TriviaQA / NaturalQuestions
├── 高级推理
│   ├── 数学推理：GSM8K / MATH
│   ├── 逻辑推理：BBH / MuSR
│   └── 科学推理：GPQA
├── 代码能力
│   ├── 函数生成：HumanEval+ / MBPP
│   ├── 真实工程：SWE-bench / BigCodeBench
│   └── 持续评估：LiveCodeBench
├── 指令遵循
│   └── IFEval
├── 安全与对齐
│   ├── 真实性：TruthfulQA
│   ├── 安全性：DecodingTrust
│   └── 幻觉：HalluLens
├── 中文能力（如需）
│   ├── C-Eval
│   ├── CMMLU
│   └── GAOKAO-BENCH
└── 人类偏好
    └── MT-bench / Chatbot Arena（如有条件）
```

### 4.2 不同阶段的评估策略

#### 预训练阶段

- **高频评估**（每 1000-5000 步）：PPL（Perplexity）在验证集上的变化
- **中频评估**（每 1-5% 训练进度）：MMLU、HellaSwag、ARC 等轻量 benchmark
- **低频评估**（每个 checkpoint）：完整 benchmark suite

建议在预训练过程中绘制"能力涌现曲线"——追踪各个 benchmark 分数随训练步数的变化。你会看到有些能力在特定训练量后突然涌现。

#### SFT 阶段

- 重点关注 IFEval（指令遵循是否提升）
- MT-bench（对话质量）
- 确认基础能力不退化（MMLU、GSM8K 不应显著下降）

#### RLHF/DPO 阶段

- MT-bench 和人类偏好评估
- TruthfulQA（是否减少了幻觉）
- 安全基准（是否更好地拒绝有害请求）
- 确认"对齐税"不过高——基础能力不应大幅下降

### 4.3 避免常见陷阱

#### 数据污染（Data Contamination）

这是 LLM 评估中最严重的问题。如果训练数据中包含了 benchmark 的测试题，评估结果就毫无意义。

**应对策略**：
- 使用"活"基准（如 LiveCodeBench），持续更新测试数据
- 进行污染检测：检查 benchmark 题目在训练数据中的出现频率
- 在多个基准上交叉验证——如果某个模型在一个 benchmark 上异常高分但其他类似任务表现一般，可能存在污染
- AIME 2025 这样使用全新竞赛题目的基准特别有价值

#### Benchmark 饱和

当主流模型在某个 benchmark 上普遍达到 90%+ 时，该 benchmark 就失去了区分度。

- MMLU → 已饱和 → 迁移到 MMLU-Pro
- GSM8K → 接近饱和 → 迁移到 MATH
- TruthfulQA → 出现饱和迹象 → 考虑 HalluLens
- BBH → 部分饱和 → MuSR 补充

#### 评估方式的影响

同一个 benchmark，不同的评估设置可能产生截然不同的结果：

- **few-shot 数量**：0-shot vs 5-shot 可能差 10-20 个百分点
- **提示模板**：不同的 prompt 模板会显著影响结果
- **生成参数**：temperature、top_p 等会影响代码生成类任务
- **评估格式**：多选题 vs 生成式回答

**建议**：严格使用标准框架（如 lm-eval-harness）的默认配置，确保结果可比。

### 4.4 实用评估流程

```python
# 建议的评估脚本结构
#!/bin/bash
MODEL_PATH="path/to/your/model"
OUTPUT_DIR="eval_results/$(date +%Y%m%d)"

# 第一层：快速 sanity check（~30 分钟）
lm_eval --model hf \
  --model_args pretrained=$MODEL_PATH \
  --tasks mmlu,gsm8k,hellaswag \
  --batch_size auto \
  --output_path $OUTPUT_DIR/quick

# 第二层：Open LLM Leaderboard 标准评估（~2-4 小时）
lm_eval --model hf \
  --model_args pretrained=$MODEL_PATH \
  --tasks leaderboard \
  --batch_size auto \
  --output_path $OUTPUT_DIR/leaderboard

# 第三层：代码能力（~1 小时）
lm_eval --model hf \
  --model_args pretrained=$MODEL_PATH \
  --tasks humaneval,mbpp \
  --batch_size auto \
  --output_path $OUTPUT_DIR/code

# 第四层：中文能力（如适用）
# 使用 OpenCompass
python run.py \
  --models hf_your_model \
  --datasets ceval_gen cmmlu_gen \
  --output $OUTPUT_DIR/chinese

# 汇总结果
python summarize_results.py $OUTPUT_DIR
```

---

## 五、排行榜与社区资源

### 5.1 重要排行榜

| 排行榜 | 维护方 | 特点 | 网址 |
|--------|--------|------|------|
| Open LLM Leaderboard v2 | Hugging Face | 开源模型标准排名 | huggingface.co/spaces/open-llm-leaderboard |
| Chatbot Arena | LMSYS/OpenLM | 众包人类偏好 | lmarena.ai |
| LiveBench | 独立 | 每月更新、无污染 | livebench.ai |
| OpenCompass | 上海 AI 实验室 | 100+ 数据集 | opencompass.org.cn |
| Artificial Analysis | 独立 | 性能+价格+速度 | artificialanalysis.ai |

### 5.2 重要论文

1. **Measuring Massive Multitask Language Understanding** (Hendrycks et al., 2020) — MMLU
2. **MMLU-Pro: A More Robust and Challenging Benchmark** (TIGER-Lab, 2024) — MMLU-Pro
3. **Training Verifiers to Solve Math Word Problems** (Cobbe et al., 2021) — GSM8K
4. **Evaluating Large Language Models Trained on Code** (Chen et al., 2021) — HumanEval
5. **Chatbot Arena: An Open Platform for Evaluating LLMs** (Zheng et al., 2024) — Chatbot Arena
6. **LiveCodeBench: Holistic and Contamination Free Evaluation** (2024) — LiveCodeBench
7. **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?** (Jimenez et al., 2023) — SWE-bench

---

## 六、推荐评估方案

### 6.1 小规模团队 / 个人（1B-7B 模型）

**核心 benchmark**（必测）：
- MMLU-Pro（知识广度）
- GSM8K（基础数学推理）
- HumanEval+（代码能力）
- IFEval（指令遵循）

**补充 benchmark**（建议测）：
- HellaSwag（常识推理）
- TruthfulQA（真实性）
- C-Eval / CMMLU（如涉及中文）

**工具**：lm-evaluation-harness + OpenCompass（中文）
**预算**：4× A100 约 4-6 小时完成完整评估

### 6.2 中大规模团队（13B-70B 模型）

在小规模方案基础上增加：
- MATH Level 5（高难度数学）
- GPQA-Diamond（研究生科学）
- BBH（复杂推理）
- MuSR（多步推理）
- SWE-bench Verified（工程代码）
- LiveCodeBench（防污染代码）
- MT-bench（对话质量）
- DecodingTrust（安全多维度）

**推荐完整运行 Open LLM Leaderboard v2 的 6 个标准 benchmark**，确保与社区结果可比。

### 6.3 预训练过程中的监控

建议追踪的指标时间线：

```
训练进度 → 评估内容
0-5%    → PPL, HellaSwag, ARC（基础语言能力涌现）
5-20%   → + MMLU（知识积累）
20-50%  → + GSM8K, BBH（推理能力涌现）
50-80%  → + HumanEval, MATH（高级能力）
80-100% → 完整 benchmark suite
```

---

## 七、总结与展望

LLM 评估体系正在快速演进。几个关键趋势：

1. **从静态到动态**：LiveBench、LiveCodeBench 等"活"基准正在取代容易被污染的静态数据集
2. **从单一到多维**：不再只看 MMLU 分数，而是综合多个维度评判
3. **从学术到实用**：SWE-bench、SWE-Lancer 等基准更贴近真实工作场景
4. **从客观到主观**：Chatbot Arena 的众包偏好已成为最受信任的排名
5. **难度持续升级**：HLE（得分 < 10%）等超高难度基准为未来发展留出空间
6. **Agent 评估兴起**：SWE-bench、PaperBench、MLE-Bench 等测试端到端的 agent 能力

对于从零训练的模型，建议从一开始就建立系统化的评估流程，使用 lm-evaluation-harness 作为主力框架，配合 OpenCompass 覆盖中文能力，并随着社区发展持续更新评估基准。

**核心建议**：不要只追求单一 benchmark 的高分。真正有用的模型是在**所有维度都均衡表现良好**的模型。
