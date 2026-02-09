# 端到端路线图：从零到可用模型的完整 Step-by-Step 计划

> 研究日期：2026-02-08
> 系列：从零训练 LLM + 视觉模型 (13/13) — 终章
> 前置研究：本文综合前 12 篇研究的所有发现，将其整合为一份可执行的端到端路线图

---

## 一、项目总览与目标设定

### 1.1 我们要做什么？

**最终目标**：从零开始训练一个具备文本理解与生成、视觉理解能力的多模态大语言模型，并完成对齐（Alignment）使其可用于实际任务。

**具体产出**：
- 一个 7B 参数的基座语言模型（Base LLM）
- 一个集成视觉能力的多模态版本（VLM）
- 经过 SFT + DPO 对齐的可用 Instruct 版本
- 完整的训练代码、数据流水线和评估框架

### 1.2 为什么选择 7B 规模？

基于前序 Scaling Laws 研究（第 6 篇）和硬件成本分析（第 5 篇）的结论：

- **性价比最优**：7B 是个人/小团队能在合理预算内完成从头训练的最大规模
- **生态成熟**：Llama 3.1 8B、Qwen 2.5 7B、OLMo 2 7B 等提供了充分的参考实现
- **硬件可达**：8×H100 或 16×A100 可在 2-4 周内完成预训练
- **Chinchilla-optimal 训练**：7B 模型需要约 140B-200B tokens（传统比例），但当前趋势（over-training）推荐 2T-5T tokens
- **推理友好**：可在单张消费级 GPU（RTX 4090/5090）上运行推理

### 1.3 时间线与里程碑概览

| 阶段 | 时间 | 主要产出 |
|------|------|---------|
| Phase 0: 规划与基建 | 第 1-2 周 | 基础设施、代码框架、数据流水线 |
| Phase 1: 数据准备 | 第 2-4 周 | 清洗后的训练语料、Tokenizer |
| Phase 2: 预训练 | 第 5-8 周 | 7B Base 模型 |
| Phase 3: 中间训练（Midtraining） | 第 9-10 周 | 增强版 Base 模型 |
| Phase 4: 视觉扩展 | 第 11-13 周 | 多模态 VLM |
| Phase 5: 后训练对齐 | 第 14-16 周 | Instruct/Chat 版本 |
| Phase 6: 评估与迭代 | 第 17-18 周 | 最终发布版本 |

**总预估时间：4-5 个月**（假设全职投入，硬件资源充足）

---

## 二、Phase 0：规划与基础设施搭建（第 1-2 周）

### 2.1 硬件选型与采购

基于硬件成本分析（第 5 篇）的推荐方案：

**推荐方案 A — 云端租用（灵活但长期成本高）**：
- 8×H100 SXM 节点（Lambda Cloud / Vast.ai / RunPod）
- 按需价格：约 $24-80/hr
- 预训练估算：~500 GPU-hours → $12,000-40,000
- 优势：零前期投入，弹性伸缩

**推荐方案 B — 自建集群（前期投入大但长期划算）**：
- 8×RTX 4090 工作站，约 $13,000-16,000
- 训练时间更长（约 4-6 周预训练），但总成本更低
- 需解决散热、NVLink 缺失（用 NCCL over PCIe）

**推荐方案 C — 云端 TPU（Google Cloud）**：
- TPU v5e pod slice（64-128 chips）
- 价格：~$0.48-1.20/chip/hr（承诺价更低）
- 优势：高互联带宽，适合大规模并行
- 劣势：需要 JAX/TPU 生态，调试不如 PyTorch 方便

**本路线图以方案 A（8×H100 云端）为基线**，其他方案等比调整。

### 2.2 软件环境搭建

```bash
# 基础环境
Python 3.11+
PyTorch 2.5+ (with CUDA 12.4)
transformers >= 4.45
flash-attn >= 2.6  # Flash Attention 2
deepspeed >= 0.15  # 或用 torchtitan/FSDP2
wandb              # 实验追踪
lm-eval-harness    # 评估框架

# 数据处理
datasets (HuggingFace)
datatrove           # 大规模数据处理
sentencepiece       # Tokenizer 训练
fasttext            # 语言识别
```

### 2.3 代码仓库结构

```
project/
├── configs/          # 模型、训练、数据配置
│   ├── model_7b.yaml
│   ├── training.yaml
│   └── data_mix.yaml
├── data/             # 数据处理流水线
│   ├── download/     # 数据下载脚本
│   ├── clean/        # 清洗与过滤
│   ├── dedup/        # 去重
│   └── tokenize/     # Tokenization
├── model/            # 模型定义
│   ├── transformer.py
│   ├── attention.py  # GQA, RoPE
│   └── vision/       # 视觉模块
├── training/         # 训练逻辑
│   ├── pretrain.py
│   ├── sft.py
│   ├── dpo.py
│   └── utils/        # lr schedule, checkpointing
├── eval/             # 评估
│   ├── benchmarks/
│   └── analysis/
└── scripts/          # 启动脚本
```

### 2.4 实验管理

- **Weights & Biases**（或 MLflow）追踪所有训练指标
- **Git + DVC** 管理代码和数据版本
- **Checkpoint 策略**：每 1000 步保存，保留最近 5 个 + 每 10,000 步的永久存档
- **训练日志**：loss、learning rate、gradient norm、throughput (tokens/sec)

---

## 三、Phase 1：数据准备（第 2-4 周）

### 3.1 训练语料收集

基于训练数据研究（第 2 篇），推荐以下数据配方：

| 数据源 | 占比 | 规模 | 说明 |
|--------|------|------|------|
| FineWeb-Edu 2 | 45% | ~2.25T tokens | 经教育质量过滤的网页文本 |
| StarCoder data / The Stack v2 | 15% | ~750B tokens | 编程代码 |
| 中文网页（CCI 3.0 / WuDaoCorpora） | 15% | ~750B tokens | 中文语料 |
| 学术论文（peS2o / arXiv） | 8% | ~400B tokens | 学术文献 |
| 书籍（Gutenberg / Open Library） | 7% | ~350B tokens | 长文本理解 |
| 维基百科（多语言） | 3% | ~150B tokens | 事实性知识 |
| 数学（OpenWebMath / Proof-Pile） | 5% | ~250B tokens | 数学推理 |
| 对话数据（Reddit / StackExchange） | 2% | ~100B tokens | 对话能力 |

**总训练量目标：5T tokens**（over-training 策略，参考 Llama 3 的 15T tokens / 8B params）

### 3.2 数据处理流水线

```
原始数据 → 语言识别 → 质量过滤 → PII 清洗 → 去重 → 分词 → 打包
```

**Step 1: 下载与抽取**
- 使用 `datatrove` 或自定义脚本批量下载
- CommonCrawl 用 `warcio` 解析 WARC 文件
- 代码用 Git 仓库 clone + 解析

**Step 2: 语言识别**
- fastText `lid.176.bin` 模型
- 保留中文（zh）和英文（en）作为主要语言
- 阈值：置信度 > 0.65

**Step 3: 质量过滤**
- 基于规则的过滤（参考 Gopher 质量过滤规则）：
  - 行平均长度、特殊字符比例、停用词频率
  - 重复 n-gram 比例 < 30%
  - 色情/暴力内容分类器过滤
- 基于模型的过滤（可选，参考 FineWeb-Edu）：
  - 训练一个质量分类器评估文本教育价值
  - 保留得分 > 3/5 的文本

**Step 4: 去重**
- **Exact dedup**：SHA-256 hash 去除完全相同的文档
- **Near-dedup**：MinHash LSH（签名 128 位，相似度阈值 0.8）
- **预期效果**：去重后数据量缩减 30-50%

**Step 5: PII 清洗**
- 正则表达式移除邮箱、电话、身份证号等
- NER 模型检测人名（可选替换为占位符）

### 3.3 Tokenizer 训练

基于 Tokenizer 研究（第 3 篇）：

**选型**：BPE（Byte-level BPE），使用 SentencePiece 实现

**关键参数**：
- 词表大小：64,000-128,000（推荐 100,000，兼顾中英文覆盖）
- 训练语料：从清洗后数据中采样 50GB 文本（中英各 50%）
- 特殊 token：`<|begin_of_text|>`, `<|end_of_text|>`, `<|pad|>`, `<|image|>`（为视觉模态预留）
- 字节回退（byte-fallback）：确保任何输入都可编码

**训练命令示例**：
```python
import sentencepiece as spm
spm.SentencePieceTrainer.train(
    input='corpus_sample.txt',
    model_prefix='tokenizer',
    vocab_size=100000,
    model_type='bpe',
    byte_fallback=True,
    character_coverage=0.9999,
    split_by_whitespace=True,
    add_dummy_prefix=True,
    num_threads=64
)
```

**验证**：
- 中文 token/字符 比率应在 0.6-0.8 之间
- 英文 token/word 比率应在 1.2-1.5 之间
- 检查常用词、代码、数学公式的分词质量

### 3.4 数据序列化

- 将 tokenized 数据打包为等长序列（context length = 4096，后续扩展到 8192/32768）
- 使用 `numpy.memmap` 或 Arrow 格式存储
- 预计磁盘占用：~10TB（tokenized 后）

---

## 四、Phase 2：预训练（第 5-8 周）

### 4.1 模型架构

基于架构综述（第 1 篇），采用当前主流的 "Modern LLM Recipe"：

```yaml
# 7B Model Config
hidden_size: 4096
num_layers: 32
num_attention_heads: 32
num_kv_heads: 8          # GQA (4:1 ratio)
intermediate_size: 11008  # FFN with SwiGLU
max_position_embeddings: 4096  # 初始，后续扩展
vocab_size: 100000
rope_theta: 500000        # 支持长上下文扩展
rms_norm_eps: 1e-5
tie_word_embeddings: false

# Components
position_encoding: RoPE
attention: GQA
activation: SwiGLU
normalization: RMSNorm (Pre-Norm)
```

**参数量计算**：
- Embedding: 100,000 × 4,096 = 0.41B
- Per layer: ~0.20B × 32 layers = 6.4B
- Output head: 4,096 × 100,000 = 0.41B（如果不 tie）
- **总计: ~7.2B 参数**

### 4.2 训练超参数

基于训练技巧研究（第 7 篇）和 Scaling Laws（第 6 篇）：

```yaml
# Optimizer
optimizer: AdamW
lr: 3e-4             # 峰值学习率
beta1: 0.9
beta2: 0.95
weight_decay: 0.1
eps: 1e-8
grad_clip: 1.0

# LR Schedule
schedule: warmup_cosine_decay
warmup_steps: 2000
total_tokens: 5T     # ~1.2M steps at batch_size 4M
min_lr_ratio: 0.1    # 最终 lr = 3e-5

# Batch Size
global_batch_size: 4M tokens  # 1024 sequences × 4096 tokens
micro_batch_size: 8           # per GPU
gradient_accumulation: 每GPU 16步

# Precision
dtype: bfloat16
```

### 4.3 分布式训练策略

基于训练框架对比（第 4 篇）：

**推荐：PyTorch FSDP2 或 DeepSpeed ZeRO Stage 3**

```
8×H100 SXM 单节点配置:
- FSDP (Full Shard): 参数 + 梯度 + 优化器状态全分片
- Flash Attention 2: 减少注意力计算显存
- Activation Checkpointing: 每 2 层 checkpoint 一次
- BF16 混合精度训练
- 预估吞吐量: ~35,000-45,000 tokens/sec
```

**内存估算（per GPU）**：
- 模型参数（BF16）：14GB
- 优化器状态（FP32 Adam）：~56GB → FSDP 分片后 ~7GB/GPU
- 梯度（BF16）：14GB → 分片后 ~1.75GB/GPU
- 激活值（with checkpointing）：~10-20GB
- **总计：~33-43GB/GPU** → H100 80GB 充裕

### 4.4 训练流程

**阶段一：General Pretraining（主训练）**

1. **随机初始化模型**（Xavier/He 初始化）
2. **小规模验证运行**：先在 100M tokens 上跑 1000 步，验证：
   - Loss 正常下降（初始 loss ≈ ln(vocab_size) ≈ 11.5）
   - 梯度范数稳定
   - 吞吐量符合预期
3. **正式训练**：5T tokens，持续监控：
   - Loss 曲线（应平滑下降）
   - Gradient norm（应稳定在 0.5-2.0 范围）
   - Learning rate schedule
   - 硬件利用率（MFU > 40%）

**关键检查点**：
- 100B tokens：第一次全面评估，验证学习正常
- 500B tokens：检查与同规模开源模型的差距
- 2T tokens：中期评估，决定是否调整数据配比
- 5T tokens：预训练完成

**故障恢复**：
- Loss spike 处理：回退到最近稳定 checkpoint，降低学习率重启
- 硬件故障：FSDP checkpoint 支持弹性恢复
- 预期训练时间：~3-4 周（8×H100）

**阶段二：Learning Rate Cooldown（退火）**

在预训练最后阶段（最后 5-10%），切换到高质量数据子集进行退火：

- 数据：FineWeb-Edu 顶层 + 维基百科 + 教科书 + 精选代码
- 学习率：从当前值线性衰减到接近 0
- 这一步在 OLMo 2/3 中被证明能显著提升最终性能
- 持续约 100B-200B tokens

---

## 五、Phase 3：中间训练 Midtraining（第 9-10 周）

参考 OLMo 3 的三阶段预训练流程，在 general pretraining 之后增加 midtraining 阶段：

### 5.1 目标

增强模型在特定能力维度上的表现，包括：
- 推理能力（数学、逻辑）
- 代码生成
- 长上下文理解
- 多语言能力（尤其中文）

### 5.2 数据配方

| 数据类型 | 占比 | 来源 |
|---------|------|------|
| 高质量数学 | 25% | OpenWebMath, GSM8K-style synthetic |
| 精选代码 | 25% | The Stack v2 去重 + 高星 GitHub repo |
| 教科书风格文本 | 20% | Phi-style textbook synthesis |
| 中文精选 | 15% | WuDao 精选 + 中文维基 |
| 学术论文 | 15% | arXiv + peS2o |

### 5.3 训练配置

- 训练量：200B-500B tokens
- 学习率：从预训练最终 lr 的 2x 开始（~6e-5），cosine decay
- Batch size：保持 4M tokens
- 预计时间：1-2 周

---

## 六、Phase 4：视觉扩展 — 构建多模态 VLM（第 11-13 周）

基于视觉模型架构（第 10 篇）、视觉数据集（第 11 篇）和多模态融合（第 12 篇）的研究成果。

### 6.1 架构选型

采用 **LLaVA-style 架构**（视觉 encoder + MLP projector + LLM）：

```
Input Image → Vision Encoder (SigLIP-SO400M) → MLP Projector (2-layer) → LLM (our 7B)
                                                                           ↕
Input Text → Tokenizer → Token Embeddings ─────────────────────────────→ LLM (our 7B)
```

**关键组件**：
- **Vision Encoder**: SigLIP-SO400M/14@384（预训练冻结，后续解冻微调）
- **Projector**: 2 层 MLP（4096 → 4096 → 4096），GELU 激活
- **分辨率处理**: AnyRes 策略（将高分辨率图像分割为多个 384×384 patches + 全局低分辨率 thumbnail）

### 6.2 训练阶段（三阶段方案，参考 LLaVA-OneVision 1.5）

**Stage 1: 视觉-语言对齐（Alignment）**

- 目标：训练 MLP projector，对齐视觉特征空间和语言嵌入空间
- 冻结：Vision Encoder ❄️ + LLM ❄️
- 只训练：MLP Projector 🔥
- 数据：558K 图文描述对（LLaVA-Pretrain / ShareGPT4V-PT）
- 训练量：~1 epoch
- 学习率：1e-3
- 预计时间：数小时（8×H100）

**Stage 1.5: 高质量知识学习（可选但推荐）**

- 目标：用高质量图文数据强化知识理解
- 冻结：Vision Encoder ❄️
- 训练：MLP Projector 🔥 + LLM 🔥
- 数据：~2M 高质量图文对（详细描述、OCR、图表理解）
- 训练量：1 epoch
- 学习率：2e-5

**Stage 2: 视觉指令微调（Visual Instruction Tuning）**

- 目标：让模型能够理解视觉指令并生成有用回答
- 训练：Vision Encoder 🔥 + MLP Projector 🔥 + LLM 🔥（全参数微调）
- 数据：~1M 混合数据
  - 通用视觉 QA（VQAv2, GQA, OK-VQA）
  - OCR 理解（TextVQA, DocVQA, ChartQA）
  - 视觉推理（CLEVR, Visual7W）
  - GPT-4V 生成的多模态对话
  - 纯文本指令数据（保持语言能力不退化）
- 训练量：1 epoch
- 学习率：2e-5，cosine decay
- 预计时间：1-2 周

### 6.3 关键技巧

- **保留纯文本 SFT 数据**：防止加入视觉后语言能力退化（catastrophic forgetting）
- **动态分辨率**：AnyRes 策略让模型处理不同尺寸的图像
- **视觉 token 压缩**：使用 pixel shuffle 或 pooling 减少视觉 token 数量（如 729 → 256）

---

## 七、Phase 5：后训练对齐（第 14-16 周）

基于对齐与后训练研究（第 8 篇），采用三阶段对齐流程。

### 7.1 Stage 1: 监督微调（SFT）

**数据准备**（目标 100K-500K 高质量样本）：

| 数据类型 | 数量 | 来源 |
|---------|------|------|
| 通用对话 | 100K | OpenHermes 2.5, Ultrachat |
| 代码指令 | 50K | Code Alpaca, Evol-CodeAlpaca |
| 数学推理 | 50K | MetaMathQA, Orca-Math |
| 中文对话 | 50K | BELLE, Firefly |
| 安全对齐 | 20K | PKU-SafeRLHF |
| 多模态指令 | 50K | LLaVA-Instruct |
| 工具使用 | 20K | Function calling, API 调用 |

**训练配置**：
```yaml
epochs: 2-3
lr: 2e-5
schedule: cosine with warmup (100 steps)
batch_size: 128
max_seq_length: 8192
```

### 7.2 Stage 2: 偏好优化（DPO）

**推荐使用 DPO**（而非 RLHF/PPO），原因：
- 实现简单，无需训练单独的 Reward Model
- 训练稳定性好
- 效果在 7B 规模上与 RLHF 相当

**数据**：
- UltraFeedback（60K preference pairs）
- 自生成偏好对：用 SFT 模型生成多个回答，人工或 GPT-4 排序

**训练配置**：
```yaml
beta: 0.1           # DPO temperature
epochs: 1
lr: 5e-7
batch_size: 64
max_length: 2048
```

### 7.3 Stage 3: 强化学习（可选，用于推理增强）

参考 DeepSeek-R1 和 OLMo 3 Think：

- 使用 **GRPO**（Group Relative Policy Optimization）
- 在数学和代码任务上使用可验证奖励（RLVR）
- 训练模型输出思维链（Chain-of-Thought）
- 仅在需要推理能力时进行此步

---

## 八、Phase 6：评估与迭代（第 17-18 周）

### 8.1 评估体系

基于评估体系研究（第 9 篇），建立全面的评估 benchmark 矩阵：

**语言能力**：

| 维度 | Benchmark | 目标分数（7B） |
|------|-----------|---------------|
| 通识知识 | MMLU | > 60% |
| 推理 | ARC-Challenge | > 55% |
| 常识 | HellaSwag | > 75% |
| 数学 | GSM8K | > 50% |
| 代码 | HumanEval | > 35% |
| 中文 | C-Eval | > 55% |
| 指令遵循 | IFEval | > 50% |

**视觉能力**：

| 维度 | Benchmark | 目标分数 |
|------|-----------|---------|
| 通用 VQA | VQAv2 | > 75% |
| OCR | TextVQA | > 55% |
| 图表 | ChartQA | > 60% |
| 多模态推理 | MMBench | > 65% |
| 综合 | MMMU | > 35% |

### 8.2 迭代优化策略

1. **失败分析**：对每个 benchmark 的错误案例进行分类分析
2. **数据补充**：针对弱项增加相关训练数据
3. **消融实验**：系统测试不同数据配比、学习率、训练步数的影响
4. **持续预训练**：如果某些能力严重不足，考虑在相关数据上继续预训练

### 8.3 模型发布清单

- [ ] 模型权重（Base + Instruct + VLM 三个版本）
- [ ] Tokenizer 文件
- [ ] 训练代码和配置
- [ ] 数据处理流水线代码
- [ ] 评估脚本和结果
- [ ] 技术报告 / Model Card
- [ ] 推理代码（支持 vLLM / llama.cpp 部署）
- [ ] 许可证选择（Apache 2.0 / MIT）

---

## 九、预算总估算

### 9.1 计算成本

| 阶段 | GPU-Hours | 成本（8×H100, ~$24/hr） |
|------|-----------|------------------------|
| 数据处理 | 200 | $600 |
| 预训练（5T tokens） | 3,500-5,000 | $10,500-15,000 |
| Cooldown/Midtraining | 500-1,000 | $1,500-3,000 |
| VLM 训练（三阶段） | 500-800 | $1,500-2,400 |
| SFT + DPO | 200-400 | $600-1,200 |
| 评估与迭代 | 200-500 | $600-1,500 |
| **总计** | **5,100-8,000** | **$15,300-24,000** |

### 9.2 其他成本

- 存储（数据 + checkpoints）：~$500-1,000/月 × 5 个月 = $2,500-5,000
- 工具和 API（Wandb Pro、评估 API 等）：~$500
- 人力：个人项目不计；如果雇佣标注员，SFT 数据标注约 $2,000-5,000

### 9.3 总预算

**最低可行预算：~$20,000**
**推荐预算：~$30,000-35,000**（含足够的迭代空间）

如果使用 RTX 4090 自建集群（方案 B），计算成本可降至约 $5,000-8,000（仅电费），但需要 $13,000-16,000 的硬件前期投入，且训练时间延长 2-3 倍。

---

## 十、风险与缓解策略

### 10.1 常见风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Loss spike / 训练发散 | 浪费算力，需回退 | 频繁 checkpoint + gradient clipping + 监控告警 |
| 数据质量问题 | 模型学到有害/低质内容 | 多轮数据清洗 + 小规模验证 |
| 硬件故障 | 训练中断 | 弹性 checkpoint + 多节点冗余 |
| 灾难性遗忘 | VLM 阶段丢失语言能力 | 混合纯文本数据 + 评估监控 |
| 预算超支 | 无法完成训练 | 小规模实验优先 + 阶段性评估决策 |
| 中英文能力不均衡 | 某种语言表现差 | 调整数据配比 + 语言特定评估 |

### 10.2 关键经验法则

1. **小模型先验证**：所有超参数和数据配方先在 150M-500M 模型上验证
2. **数据质量 > 数据数量**：一份高质量的 2T tokens 胜过低质的 10T tokens
3. **频繁评估**：不要等训练完才发现问题，每 100B tokens 做一次 checkpoint 评估
4. **留出迭代余量**：预算的 30% 留给迭代和修正
5. **参考开源实现**：OLMo 3、Llama 3 的训练细节是最好的参考

---

## 十一、参考开源项目与工具

### 11.1 可复现的训练流水线

| 项目 | 特点 | 链接 |
|------|------|------|
| **OLMo 3** (AI2) | 完全开源（数据+代码+权重+checkpoints），7B/32B | github.com/allenai/OLMo |
| **LLM360** | 完全透明的 LLM 训练（Amber, Crystal） | github.com/LLM360 |
| **OpenLM** | 简洁的预训练代码库 | github.com/mlfoundations/open_lm |
| **litgpt** | Lightning AI 的轻量 LLM 训练框架 | github.com/Lightning-AI/litgpt |
| **torchtitan** | Meta 官方 PyTorch 原生训练框架（FSDP2） | github.com/pytorch/torchtitan |
| **LLaVA-OneVision 1.5** | 完全开源的多模态训练（数据+代码+模型） | github.com/EvolvingLMMs-Lab |

### 11.2 数据工具

| 工具 | 用途 |
|------|------|
| **datatrove** (HuggingFace) | 大规模数据处理流水线 |
| **dolma** (AI2) | 数据集构建工具 |
| **RedPajama-Data** | CommonCrawl 处理参考实现 |
| **lm-eval-harness** (EleutherAI) | 标准化评估框架 |

---

## 十二、路线图总结 — 关键决策速查表

以下是整个项目中需要做出的关键决策，以及本路线图的推荐选择：

| 决策点 | 推荐选择 | 备选方案 |
|--------|---------|---------|
| 模型规模 | 7B Dense | 3B（更便宜）、7B MoE（更复杂） |
| 架构 | Llama-style Decoder-only | Mamba-hybrid（实验性） |
| 注意力 | GQA (4:1) | MHA（更贵）、MQA（更快但可能略差） |
| 位置编码 | RoPE (θ=500K) | ALiBi |
| Tokenizer | BPE 100K, SentencePiece | tiktoken (OpenAI) |
| 训练框架 | PyTorch + FSDP2 | DeepSpeed ZeRO-3、Megatron-LM |
| 硬件 | 8×H100 云端 | TPU v5e、8×RTX 4090 |
| 训练数据量 | 5T tokens | 2T（最低可行）、10T+（充裕预算） |
| 视觉 Encoder | SigLIP-SO400M | InternViT-6B（更大更强） |
| VLM Connector | 2-layer MLP | Cross-attention（更复杂） |
| 对齐方法 | SFT + DPO | SFT + RLHF/PPO |
| 推理增强 | GRPO + RLVR（可选） | 不做（简化流程） |

---

## 十三、结语

本路线图基于 2024-2026 年的最新研究进展和开源实践，提供了一条从零到可用模型的完整路径。整个项目的核心原则是：

1. **从小到大**：先在小模型上验证，再扩展到目标规模
2. **数据为王**：投入足够的精力在数据清洗和质量控制上
3. **站在巨人肩上**：充分利用开源项目（OLMo、LLaVA）的经验和代码
4. **持续评估**：让评估驱动训练决策，而非盲目训练
5. **保留余量**：时间和预算都要留出 30% 的迭代空间

这份路线图不是终点，而是起点。随着你的训练经验积累，很多决策会需要根据实际数据调整。但有了这 13 篇研究的知识储备和这份执行计划，你已经具备了从零训练一个有竞争力模型的全部知识基础。

**祝训练顺利！🚀**

---

> 本文是「从零训练 LLM + 视觉模型」系列的第 13 篇，也是最终的综合路线图。
> 完整系列文档列表：
> 1. LLM 架构综述
> 2. 训练数据全景
> 3. Tokenizer 设计
> 4. 训练框架对比
> 5. 硬件与成本分析
> 6. Scaling Laws 研究
> 7. 训练技巧
> 8. 对齐与后训练
> 9. 评估体系
> 10. 视觉模型架构
> 11. 视觉数据集
> 12. 多模态融合
> 13. 端到端路线图（本文）
