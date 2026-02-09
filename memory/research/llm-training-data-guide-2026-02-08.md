# LLM 预训练数据：公开数据集全景、清洗流程与配比策略

> 研究日期：2026-02-08
> 任务来源：backlog P1 - 从零训练 LLM + 视觉模型 #2

---

## 一、数据是新的石油：2024-2025 的数据优先思维

**核心洞察**："高质量数据比昂贵的硬件升级和更好的算法更有效地加速训练"（PyTorch 2024 大会共识）

2024-2025 年的 LLM 研发呈现一个明显趋势：从"规模优先"转向"质量优先"。关键发现：
- **DataComp-LM 基准实验**：用 40% 更少但高质量筛选的数据训练的 7B 模型，性能超越未经筛选数据的模型
- **FineWeb-Edu 案例**：仅 38B（原数据的 10%）的教育质量数据，训练的模型性能与 350B 未筛选数据相当
- **Chinchilla 定律**：数据量应与参数量同比例增长，但 2024 年发现数据质量比原始数量更重要

---

## 二、主流公开预训练数据集全景

### 2.1 Web 数据（CommonCrawl 衍生）

| 数据集 | 规模 | 来源 | 特色 | 发布机构 |
|--------|------|------|------|----------|
| **CommonCrawl** | 原始 1000+ TB/年 | 互联网爬取 | 原始、未筛选、噪声大 | CommonCrawl.org |
| **FineWeb** | 18.5T tokens (更新版) | CommonCrawl | 优化清洗流程，LLM 性能验证 | HuggingFace 2024 |
| **FineWeb-Edu** | 1.3T tokens | FineWeb 子集 | 教育内容筛选，质量极高 | HuggingFace 2024 |
| **FineWeb-2** | 3T tokens (多语言) | CommonCrawl | 覆盖 500+ 语言 | HuggingFace 2024 |
| **RefinedWeb** | ~600B tokens (原始 2.8TB) | CommonCrawl | Falcon 模型训练用，仅 CommonCrawl | TII 2023 |
| **RedPajama v2** | 30T tokens | 84 CC snapshots | 多源混合 (CC+Wiki+Code+Book) | Together AI 2023 |
| **C4** | ~175B tokens | CommonCrawl | 早期高质量基准，简单启发式筛选 | Google 2019 |
| **DCLM-Pool** | 240T tokens | CommonCrawl | 标准化基准池 | Apple/多机构 2024 |
| **DCLM-Baseline** | 4T tokens | DCLM-Pool 子集 | 强基线数据集，模型筛选 | Apple 2024 |

### 2.2 多源混合数据集

| 数据集 | 规模 | 组成 | 特色 |
|--------|------|------|------|
| **Dolma** | 3T tokens | Web 82% + peS2o 科学论文 8% + Code 5% + Wiki 3% + Books 2% | 完全开源，可重现 |
| **The Pile** | ~800B tokens | 22 个领域数据集 | 早期经典数据集，质量高但规模小 |
| **GneissWeb** | ~10T tokens | CommonCrawl 衍生 | IBM 2024，高质量筛选 |
| **TxT360** | 2T tokens | 99 CC snapshots + 14 个非 web 源 | 全球去重，首次大规模混合 |
| **DAIT** | ~500B tokens | 多源 | DatologyAI，目前质量最优，超越 DCLM 4.4pp |

### 2.3 领域专用数据集

| 数据集 | 领域 | 规模 | 用途 |
|--------|------|------|------|
| **GitHub Code** | 代码 | 数百 TB | StarCoder、Code Llama 等 |
| **Stack Exchange** | 问答 | ~10B tokens | 对话、推理训练 |
| **arXiv / peS2o** | 学术论文 | 38M 论文 | 科学推理训练 |
| **Project Gutenberg** | 书籍 | ~50K 本书 | 文学、叙事能力 |
| **Wikipedia** | 百科 | ~20B tokens | 知识密集、事实准确 |

---

## 三、数据清洗流水线详解

### 3.1 标准处理流程

```
原始数据 (Raw Crawl)
    ↓
[1] 文本提取 (Trafilatura / Resiliparse)
    ↓
[2] 语言检测 (FastText LangID)
    ↓
[3] 质量筛选 (Heuristics + Model-based)
    ↓
[4] 去重 (Exact + Fuzzy)
    ↓
[5] PII 移除 (Regex + NER)
    ↓
[6] 毒性过滤 (Toxicity Classifier)
    ↓
[7] 数据混合 (Domain re-weighting)
    ↓
高质量语料 (Clean Corpus)
```

### 3.2 各环节技术细节

#### 1. 文本提取
- **工具**：Trafilatura、Resiliparse、boilerpy3
- **目标**：从 HTML 中提取主要内容，去除导航、广告、页脚
- **技巧**：使用 HTML 标签结构和文本密度特征

#### 2. 语言检测
- **工具**：FastText LangID（lid.176.bin）
- **阈值**：置信度 > 0.8
- **输出**：按语言分桶，便于后续多语言配比

#### 3. 质量筛选（最关键环节）

**启发式规则 (Heuristic Filtering)**：
```python
# 典型规则示例
filters = {
    "min_length": 100,           # 至少 100 字符
    "max_length": 100000,        # 最多 10 万字符
    "mean_word_length": (3, 10), # 平均词长度
    "symbol_to_word_ratio": 0.1, # 符号比例
    "sentence_count": 3,         # 至少 3 个句子
    "stopword_ratio": 0.1,       # 停用词比例
}
```

**困惑度过滤 (Perplexity Filtering)**：
- 使用预训练小模型（如 GPT-2）计算文档困惑度
- 过高困惑度 = 随机/垃圾内容
- 过低困惑度 = 可能是模板/重复内容

**模型质量分类器 (Model-based Quality Filter)** —— 2024 最佳实践：
- **FineWeb 方法**：用 LLaMA-70B 对文档打分，训练 fastText 分类器
- **FineWeb-Edu 方法**：训练专门的教育内容评分器（Llama-3.1-70B-Instruct 标注），区分 0-5 分
- **成本**：分类 15T tokens 约需 6000 H100 GPU hours
- **效果**：fastText 分类器在保持 82% F1 的同时实现实时过滤

#### 4. 去重技术

**精确去重 (Exact Deduplication)**：
- **方法**：文档级 MD5/SHA256 哈希
- **效果**：通常去除 10-30% 数据
- **工具**：Spark、Datatrove

**模糊去重 (Fuzzy Deduplication)**：
- **方法**：MinHash + LSH (Locality Sensitive Hashing)
- **参数**：n-gram=5, Jaccard 阈值=0.8-0.9
- **效果**：捕捉近似重复（如同一文章的不同版本）
- **开销**：O(n) 复杂度，可扩展至万亿级

**子串去重 (Substring Deduplication)**：
- **方法**：Suffix Array / ExactSubstr
- **目标**：去除 13-gram 以上的重复子串
- **重要性**：防止训练数据污染下游评测基准

**SoftDedup (2024 新研究)**：
- 不是删除重复，而是降权
- 高频率段落采样概率降低
- **效果**：减少 26% 训练步数，同时提升 1.8% 下游准确率

#### 5. PII (个人身份信息) 移除
- **目标**：姓名、邮箱、电话、地址、身份证号
- **方法**：
  - Regex 匹配（电话号码、邮箱模式）
  - NER 模型识别实体
  - 特定工具：Microsoft Presidio、IBM Granite HAP Filter
- **IBM Granite HAP**：38M 参数，CPU 实时运行，开源

#### 6. 毒性/有害内容过滤
- **方法**：多分类器（毒性、仇恨、歧视、暴力分级）
- **工具**：
  - Perspective API
  - IBM Granite HAP Filter
  - Toxicity of the Commons (2024) 分类器
- **注意**：简单关键词过滤会误伤医学/法律内容，需要细粒度分类

---

## 四、数据配比策略

### 4.1 Llama 3 官方配比（经典参考）

| 数据类型 | 比例 | 备注 |
|----------|------|------|
| **通用知识 (General Knowledge)** | 50% | Web、百科、新闻等 |
| **数学与推理** | 25% | 数学题、逻辑推理文本 |
| **代码** | 17% | Python、多种编程语言 |
| **多语言** | 8% | 非英语，30+ 语言 |

**训练规模**：15.6T tokens（Llama 3 70B）

### 4.2 Dolma 数据集原始配比

| 来源 | 占比 | tokens |
|------|------|--------|
| CommonCrawl (Web) | 82% | ~2.5T |
| peS2o (科学论文) | 8% | ~240B |
| Code | 5% | ~150B |
| Wiki + Encyclopedia | 3% | ~90B |
| Books | 2% | ~60B |

### 4.3 数据配比最佳实践

**通用配比原则**：
1. **Web 数据占比 60-85%**：提供语言基础和广泛知识
2. **代码占比 10-20%**：显著提升推理和工具使用能力
3. **学术/科学数据占比 5-15%**：提升推理和事实准确性
4. **百科/书籍占比 2-10%**：高质量知识密集内容

**多语言配比**：
- **英语优先模型**：英文 80-90%，其他语言 10-20%
- **真正多语言模型**：英语 50-60%，其他语言 40-50%
- 每种语言至少 10B tokens 才能有基本能力

**领域专用模型配比调整**：
- **代码模型**：代码比例提升至 50-80%
- **科学模型**：学术论文比例提升至 30-50%
- **医疗模型**：医疗文本 + 通用预训练微调

### 4.4 Data Mixing Laws (2024 研究)

**关键发现**：数据混合比例与模型性能存在可预测的数学关系。

**优化策略**：
- 使用小规模模型（100M-1B）快速验证不同配比
- 建立 "数据混合 → 模型性能" 的映射函数
- 外推到大规模训练

**工具**：AutoScale (NeurIPS 2024)、DataComp 框架

---

## 五、各数据集性能对比

### 5.1 质量排名（基于下游任务准确率）

| 排名 | 数据集 | 相对性能 | 特点 |
|------|--------|----------|------|
| 1 | **DAIT** | +6.1% vs FineWeb-Edu | DatologyAI，目前质量最高 |
| 2 | **FineWeb-Edu** | 基准 | 教育内容筛选，1.3T tokens |
| 3 | **DCLM-Baseline** | -4.4% | Apple，模型筛选，4T tokens |
| 4 | **FineWeb** | -6.1% | 15-18T tokens，通用高质量 |
| 5 | **Dolma** | -8% | 3T tokens，完全开源可复现 |
| 6 | **RefinedWeb** | -10% | 仅 CommonCrawl |
| 7 | **C4** | -15% | 早期基准，简单启发式筛选 |

### 5.2 规模与效率权衡

| 数据集 | 原始规模 | 清洗后 | 压缩比 | 质量提升 |
|--------|----------|--------|--------|----------|
| FineWeb | 100+ TB | 44 TB | ~70% | 基准 |
| FineWeb-Edu | 44 TB | ~3 TB | ~93% | +6.1% |
| DCLM-Pool | 240T tokens | 4T baseline | ~98% | -4.4% |

**关键洞察**：
- 激进的过滤（丢弃 90%+ 数据）通常能提升模型性能
- 质量 >> 数量（在万亿级以下）

---

## 六、开源数据处理工具链

### 6.1 端到端框架

| 工具 | 机构 | 功能 | 链接 |
|------|------|------|------|
| **Datatrove** | HuggingFace | 数据提取、清洗、去重、分词 | github.com/huggingface/datatrove |
| **Dolma Toolkit** | AllenAI | 万亿级数据集构建 | github.com/allenai/dolma |
| **DataComp (DCLM)** | Apple/多机构 | 标准化数据实验框架 | github.com/mlfoundations/dclm |
| **RedPajama** | Together AI | 数据收集和处理 | github.com/togethercomputer/RedPajama-Data |

### 6.2 专项工具

| 工具 | 用途 | 性能 |
|------|------|------|
| **Trafilatura** | HTML 文本提取 | 高质量，可处理多种格式 |
| **MinHash** | 模糊去重 | 万亿级规模 |
| **dedupe.io** | 精确去重 | 并行化 |
| **presidio** | PII 检测 | 微软开源 |
| **fastText** | 语言检测、文本分类 | 实时，CPU 友好 |

---

## 七、从零构建训练数据的实操建议

### 7.1 数据策略路线图

**阶段 1：MVP 验证（< $1K 预算）**
- 使用现成数据集：FineWeb-Edu (1.3T) 或 DCLM-Baseline (4T)
- 训练 100M-1B 参数模型验证数据和代码
- 目标：验证训练流程和数据质量

**阶段 2：中等规模（$10K-$100K 预算）**
- 基于 FineWeb (15T) 或 Dolma (3T)
- 自定义过滤：添加领域特定数据
- 训练 1B-7B 参数模型
- 目标：获得可用的小模型

**阶段 3：大规模（$100K+ 预算）**
- 从 CommonCrawl 原始数据开始
- 构建自定义清洗流水线
- 训练 7B+ 参数模型
- 目标：训练 SOTA 级模型

### 7.2 推荐数据组合

**英文通用模型（7B-13B）**：
```
FineWeb: 60% (9T tokens)
GitHub Code: 20% (3T tokens)
arXiv/peS2o: 10% (1.5T tokens)
Wikipedia: 5% (750B tokens)
Books (Gutenberg): 5% (750B tokens)
总计: 15T tokens
```

**多语言模型**：
```
FineWeb-2: 70% (多语言 Web)
英文 FineWeb-Edu: 15%
Code: 10%
Wiki: 5%
```

**代码优先模型**：
```
GitHub (star>50): 60%
Stack Exchange: 20%
Web (技术文档): 15%
其他: 5%
```

### 7.3 常见陷阱与避免

| 陷阱 | 后果 | 解决方案 |
|------|------|----------|
| 数据泄露到测试集 | 虚假高性能 | 子串去重 + 下游任务文本匹配检查 |
| 重复数据过多 | 过拟合，浪费训练预算 | MinHash 模糊去重 |
| 低质量 Web 数据 | 幻觉、有害输出 | 模型质量分类器筛选 |
| PII 残留 | 隐私泄露、法律风险 | 多层 PII 检测 |
| 语言不平衡 | 小语言能力差 | 显式语言配比控制 |
| 领域不平衡 | 某些任务表现差 | Domain mixing + 上采样低资源领域 |

### 7.4 数据质量验证清单

- [ ] 训练前：检查下游任务基准是否被污染（去重验证）
- [ ] 训练前：采样 10K 文档人工检查质量
- [ ] 训练前：验证语言分布符合预期
- [ ] 训练前：检查 PII 残留率（采样 + 自动检测）
- [ ] 训练中：监控 loss curve，异常 spike 可能表示数据问题
- [ ] 训练后：对比不同数据源子集的性能

---

## 八、2025-2026 数据趋势预测

1. **合成数据崛起**：DeepSeek、OpenAI 大量使用模型生成的高质量合成数据，用于数学、代码、推理任务
2. **多模态数据融合**：文本 + 图像交错数据（如网页截图 + HTML）成为新前沿
3. **实时数据流**：动态更新的数据管道（而非静态快照）
4. **细粒度质量评分**：每个 token/段落级别的质量权重，而非文档级别
5. **隐私保护训练**：联邦学习、差分隐私在数据收集阶段的应用
6. **数据溯源**：每个训练样本的可追溯性（Data Provenance）成为监管要求

---

## 参考资料

1. Penedo et al., "The FineWeb Datasets: Decanting the Web for the Finest Text Data at Scale", NeurIPS 2024
2. Li et al., "DataComp-LM: In search of the next generation of training sets for language models", NeurIPS 2024
3. Soldaini et al., "Dolma: an Open Corpus of Three Trillion Tokens for Language Model Pretraining Research", ACL 2024
4. Together AI, "RedPajama-Data-v2", 2023
5. Meta, "The Llama 3 Herd of Models", 2024
6. Penedo et al., "FineWeb-Edu", 2024
7. IBM, "GneissWeb: Preparing High Quality Data for LLMs at Scale", 2024
8. Xie et al., "Data Mixing Laws: Optimizing Data Mixtures by Predicting Language Modeling Performance", 2024
9. Yu et al., "SoftDedup: an Efficient Data Reweighting Method for Speeding Up Language Model Pre-training", 2024
10. Rohan Paul, "Curating Public Datasets for LLM Pretraining", 2025
11. Rohan Paul, "Selecting and Preparing Training Data for LLMs (2024–2025)", 2025
12. Mozilla Foundation, "Best Practices for Open Datasets for LLM Training", 2024
