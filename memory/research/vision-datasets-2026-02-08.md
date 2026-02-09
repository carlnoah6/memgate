# 视觉数据集：图文配对数据、清洗流程与合成数据生成

> 研究日期：2026-02-08
> 任务来源：backlog P1 - 从零训练 LLM + 视觉模型 #11

---

## 一、总览：视觉数据在多模态大模型中的核心地位

多模态大语言模型（MLLM）的训练本质上是一个"数据驱动"的过程。相比纯文本 LLM 只需处理语料库，视觉-语言模型需要同时处理**图像**和**文本**两种模态的数据，且两者之间需要建立有意义的关联。数据质量直接决定了模型的视觉理解能力上限。

从数据视角，多模态训练可以分为以下几个层次：

```
层次 1：视觉编码器预训练数据 → 大规模图文配对（亿级）→ 学习视觉-文本对齐
层次 2：视觉-语言对齐数据   → 中等规模图文对（百万级）→ 桥接视觉与 LLM
层次 3：指令微调数据         → 精选高质量数据（十万级）→ 教会模型跟随指令
层次 4：对齐数据             → 偏好/安全数据（万级）  → 价值对齐与安全过滤
```

本文将系统梳理每个层次涉及的数据集、数据质量保障流程、合成数据生成方法以及实践中的配比策略。

---

## 二、大规模图文配对数据集全景

### 2.1 从 CC3M 到 LAION-5B：规模的飞跃

大规模图文配对数据集是训练 CLIP、SigLIP 等对比学习视觉编码器的基础。以下是主要数据集的演进：

**Conceptual Captions 3M（CC3M，Google，2018）**

CC3M 是早期高质量图文数据集的代表。从 ~35 亿候选网页图文对中，通过严格过滤（图像质量、文本-图像匹配度、去除人名/专有名词等）筛选出约 330 万对。数据质量高但规模有限，主要用作小模型或微调阶段的补充数据。其 alt-text 经过规则清洗（将人名替换为通用词、标准化格式），文本长度通常在 10-20 词左右。

**Conceptual 12M（CC12M，Google，2021）**

CC12M 是 CC3M 的扩展版，放松了过滤条件以获得更大规模（约 1240 万对）。与 CC3M 相比，CC12M 保留了更多多样性但也引入了更多噪声。研究表明，CC12M 在训练 CLIP 等模型时可以作为中等规模的高质量数据源。

**SBU Captions（Stony Brook，2011）**

SBU 是较早的自然图文数据集，包含约 100 万对 Flickr 图文对。虽然规模小，但因其人工撰写的描述质量较高，常被用作 LLaVA 等模型的预训练对齐数据。

**YFCC100M（Yahoo/Flickr，2016）**

Yahoo Flickr Creative Commons 100M 包含 ~1 亿张 Flickr 图片及元数据。是早期最大的公开图像数据集之一，但其"描述"主要来自用户标签和标题，图文匹配质量参差不齐。

**LAION-400M（LAION，2021）**

LAION-400M 标志着社区驱动的大规模数据集的开端。从 CommonCrawl 中提取网页图片及其 alt-text，使用 OpenAI CLIP ViT-B/32 计算图文相似度分数，保留 cosine similarity > 0.28 的样本，得到约 4 亿对。这是首个开源的亿级图文数据集，证明了"用 CLIP 过滤 CLIP 训练数据"的可行性。

**LAION-5B（LAION，2022，NeurIPS 2022）**

LAION-5B 是当时最大的开源图文数据集，包含 **58.5 亿**对 CLIP 过滤后的图文样本：
- **LAION-2B-en**：23.2 亿英文对
- **LAION-2B-multi**：22.6 亿多语言对
- **LAION-1B-nolang**：12.7 亿语言无法确定的对

数据来源同样是 CommonCrawl，但覆盖了 2014-2021 年的多个快照。关键元数据包括：CLIP ViT-B/32 和 ViT-L/14 的相似度分数、NSFW 概率分数、图像尺寸等。LAION-5B 还提供了子集：
- **LAION-Aesthetics**：按美学评分过滤的高质量子集（用于训练 Stable Diffusion）
- **LAION-High-Resolution**：分辨率 ≥ 1024×1024 的子集

> ⚠️ **重要提醒**：2023 年底，LAION-5B 因发现包含 CSAM（儿童性虐待材料）内容被临时下线。2024 年初，LAION 发布了重新清洗后的版本（Re-LAION-5B），使用更严格的安全过滤器移除了有问题的内容。这提醒我们，大规模网络爬取数据集的安全清洗是一个持续性挑战。

**COYO-700M（Kakao Brain，2022）**

COYO（Colossal Clean Web Dataset YO）包含约 **7.47 亿**图文对，由韩国 Kakao Brain 团队构建。与 LAION 的主要区别在于：
- 提供更丰富的元数据（图像宽高、alt-text 长度、美学分数、watermark 概率等）
- 独立于 LAION 的数据管线，可作为交叉验证
- 被用于训练 Karlo（文生图模型）等

**Wukong（华为，2022）**

悟空数据集包含约 **1 亿**中文图文对，是专门面向中文多模态模型的大规模数据集。从网络爬取中文网页图文数据，使用 CLIP 模型过滤。对于训练中文多模态模型非常有价值。

### 2.2 DataComp：数据集构建的标准化竞赛

**DataComp（多机构联合，NeurIPS 2023）** 不仅是一个数据集，更是一个**数据集构建方法论的 benchmark**。其核心思想是：固定模型架构和训练流程，让参与者只竞争"数据选择策略"。

**候选池**：从 CommonCrawl 中提取 **128 亿**图文候选对（比 LAION-5B 的源数据更大）

**过滤策略**（从简单到复杂）：
1. **No filtering**：直接使用全部候选数据
2. **Basic filtering**：文本长度 ≥ 5 词，移除英文以外的内容
3. **CLIP score filtering**：保留 CLIP L/14 cosine similarity 前 30% 的样本
4. **Image-based filtering**：使用 ImageNet 作为参考集，保留特征空间中靠近 ImageNet 分布的样本
5. **CLIP + Image-based**：组合以上两种策略

**关键发现**：
- 最佳基线 DataComp-1B（约 14 亿对，从 128 亿候选中筛选）训练 CLIP ViT-L/14 达到 ImageNet 零样本准确率 **79.2%**，超过 OpenAI 原版 CLIP 3.7 个百分点
- 数据质量 > 数据数量：从 128 亿筛选到 14 亿（保留约 11%）性能反而大幅提升
- 简单的 CLIP score 过滤就已经非常有效

**DataComp-1B 的实际意义**：证明了在固定计算预算下，精心策划的 1.4B 数据可以超过粗放的 5B+ 数据。这对资源有限的团队是重大利好——你不需要最大的数据集，你需要最好的数据集。

### 2.3 数据集对比总结

| 数据集 | 规模 | 来源 | 语言 | 关键特点 |
|-------|------|------|------|---------|
| CC3M | 3.3M | Google 清洗 | 英文 | 高质量，规则清洗 |
| CC12M | 12.4M | Google 清洗 | 英文 | CC3M 放松版 |
| SBU | 1M | Flickr | 英文 | 人工描述 |
| LAION-400M | 400M | CommonCrawl | 英文 | 首个开源亿级 |
| LAION-5B | 5.85B | CommonCrawl | 多语言 | 最大开源，有安全争议 |
| COYO-700M | 747M | 网络爬取 | 英文 | 丰富元数据 |
| DataComp-1B | 1.4B | CommonCrawl | 英文 | 精选高质，benchmark 附带 |
| Wukong | 100M | 网络爬取 | 中文 | 中文最大级 |

---

## 三、数据清洗与质量过滤

"Garbage in, garbage out"在视觉数据集领域体现得尤为明显。网络爬取的图文数据中充斥着噪声、不安全内容和低质量样本。一个完善的数据清洗管线是训练高质量模型的前提。

### 3.1 基础过滤：规则驱动

**图像侧过滤**：
- **尺寸过滤**：移除过小（如 < 200×200）或过大（如 > 10000×10000）的图像
- **宽高比过滤**：移除极端宽高比（如 > 3:1）的图像，这类图像通常是 banner、广告等
- **格式验证**：移除损坏、无法解码的图像文件
- **灰度/纯色过滤**：移除纯色或接近纯色的"空白"图像

**文本侧过滤**：
- **长度过滤**：移除过短（< 5 词）或过长（> 200 词）的 alt-text
- **语言检测**：使用 fasttext 等工具识别语言，按需保留
- **模板文本移除**：过滤 "Click here"、"Image not found"、"Untitled" 等常见模板
- **URL/代码过滤**：移除 alt-text 中包含大量 URL 或代码片段的样本
- **有害词过滤**：基于关键词黑名单移除明显有害的文本

### 3.2 NSFW 与安全过滤

NSFW 过滤是大规模数据集构建中最敏感的环节之一。主要方法：

**基于 CLIP 的 NSFW 分类器**：
- 训练一个轻量级 MLP 分类器（如 2-3 层），以 CLIP ViT-L/14 的图像 embedding 为输入
- 输出 NSFW 概率分数（0-1），设置阈值（如 > 0.5）移除
- LAION-5B 和 DataComp 都采用了这种方法
- NVIDIA 的 NeMo-Curator 提供了开箱即用的 NSFW 过滤 pipeline

**多层级安全过滤**：
- **图像级**：NSFW 分类器、暴力内容检测器
- **文本级**：有害内容分类器、PII（个人信息）检测器
- **跨模态级**：检测图文组合是否构成有害内容（如本身无害的图片配上有害文字）

**MetaCLIP 的方法**（Meta，ICLR 2024）：
- 使用内部系统将不当图像分类为 96 种危险内容类型
- 同时应用基于文本的毒性分类器
- 最后用 PCA hash 进行图像去重

### 3.3 文本-图像相关性过滤：CLIP Score

CLIP Score 过滤是目前最广泛使用的图文匹配质量指标：

**工作原理**：
1. 使用预训练 CLIP 模型分别编码图像和文本
2. 计算两者 embedding 的余弦相似度
3. 设置阈值，保留高相似度的样本

**阈值选择的学问**：
- LAION-5B 使用 CLIP ViT-B/32，阈值 0.28（较宽松）
- DataComp 最佳策略使用 CLIP ViT-L/14，保留前 30%（约 0.25-0.30 之间）
- 阈值过高会损失多样性，过低会引入噪声——需要根据下游任务权衡

**CLIP 过滤的局限性**：
- **自举偏差**：用 CLIP 过滤数据来训练 CLIP，可能放大 CLIP 自身的偏见
- **对长文本不友好**：CLIP 的文本编码器上限为 77 token，无法评估长描述的质量
- **概念覆盖不均**：研究表明 CLIP 过滤倾向于保留"典型"内容，可能系统性地移除某些少数群体或文化特定的内容

**Data Filtering Networks（DFN，ICLR 2024）**：
一种超越简单 CLIP score 的方法。训练专门的过滤网络，在一个小的高质量数据集上学习"什么是好数据"，然后用这个网络对大规模候选池进行打分。DFN 在 DataComp benchmark 上显著优于纯 CLIP score 过滤。

### 3.4 去重策略

去重对于防止模型过拟合和确保数据多样性至关重要：

**精确去重**：
- **URL 去重**：移除相同 URL 的重复条目
- **Hash 去重**：计算图像的 perceptual hash（如 pHash、dHash），移除哈希值完全相同的图像
- **文本去重**：移除 alt-text 完全相同的条目

**近似去重**：
- **Embedding 聚类去重**：使用 CLIP embedding 计算图像间的余弦距离，移除距离小于阈值的近似重复
- **PCA Hash**：对 CLIP embedding 做 PCA 降维后取 sign 作为二进制 hash，快速进行大规模近似去重
- **SemDeDup**（Meta，2023）：语义级去重，在 embedding 空间中做聚类，每个簇只保留一个代表样本

**去重效果**：通常可以将数据集缩减 15-30%，同时提升模型训练效率和泛化能力。

### 3.5 完整的数据清洗 Pipeline 示例

以 DataComp 的最佳实践为例，一个完整的清洗流程如下：

```
CommonCrawl 原始数据（数百亿 URL）
    ↓ Step 1: 基础清洗
    提取 img + alt-text 对
    移除损坏图像、过小图像、空白 alt-text
    语言检测，保留目标语言
    ↓ Step 2: 安全过滤
    NSFW 分类器过滤
    毒性文本分类器过滤
    PII 检测与移除
    ↓ Step 3: URL 与 hash 去重
    精确 URL 去重
    图像 perceptual hash 去重
    ↓ Step 4: CLIP Score 过滤
    计算 CLIP ViT-L/14 图文相似度
    保留 top 30%
    ↓ Step 5: 分布对齐过滤（可选）
    基于目标分布（如 ImageNet 类别）进行平衡采样
    ↓ Step 6: 语义去重
    CLIP embedding 聚类
    每簇保留代表性样本
    ↓
最终高质量数据集（原始数据的 ~5-15%）
```

---

## 四、合成数据生成

当网络爬取数据的质量瓶颈难以逾越时，合成数据提供了一条突破路径。2023-2025 年间，合成数据在多模态训练中的地位急剧上升。

### 4.1 用 LLM/MLLM 生成高质量 Caption

网络爬取的 alt-text 通常简短、信息匮乏（如"beautiful sunset"、"product image"），无法为模型提供丰富的视觉描述。利用强大的多模态模型重新生成详细描述成为了关键技术。

**ShareGPT4V（ECCV 2024）**

ShareGPT4V 是该领域的标志性工作：
1. **种子数据**：使用 GPT-4V 对约 100K 张高质量图像生成详细描述（每张 100-300 词）
2. **训练 Captioner**：用这 100K 种子数据微调一个开源多模态模型（ShareCaptioner），使其具备类似 GPT-4V 的描述能力
3. **大规模生成**：用 ShareCaptioner 对 120 万张图像生成高质量描述
4. **效果验证**：使用 ShareGPT4V 数据替换 LLaVA-1.5 的预训练 caption，在多个 benchmark 上显著提升

关键创新在于"**教师蒸馏**"——用少量昂贵的 GPT-4V 标注训练一个便宜的开源 Captioner，然后用 Captioner 大规模生产高质量描述。

ShareGPT4V 的描述涵盖：世界知识、物体属性、空间关系、美学评价等多个维度，远超传统 alt-text 的信息密度。

**ALLaVA（2024）**

ALLaVA 更直接地利用 GPT-4V 生成合成数据：
- 直接用 GPT-4V 对图像生成详细的描述和问答对
- 生成数据涵盖 Caption（详细描述）和 VQA（视觉问答）两种格式
- 目标是为轻量级视觉语言模型（如 Phi-2 大小的模型）提供高质量训练数据
- 证明了即使模型参数少，高质量合成数据也能带来显著提升

**DenseFusion-1M（2024）**

DenseFusion-1M 更进一步，融合多个视觉专家模型的输出：
- 使用 OCR、目标检测、分割等多个专家模型提取图像信息
- 将多源信息输入 LLM 生成融合后的密集描述
- 每张图像的描述可达 300-500 词
- 包含 100 万张图像的密集描述

**Recaption 范式的推广**

"Recaption"（重新生成描述）已成为一种标准范式。主要方法包括：
- **CogVLM-Recaption**：用 CogVLM 重写 LAION 数据的 caption
- **LLaVA-Recaption**：用 LLaVA-1.5 重写各种数据集的描述
- **InternLM-XComposer-Recaption**：使用 InternLM-XComposer 生成多层次描述

核心思路一致：用强模型替换弱标注，quality over quantity。

### 4.2 用扩散模型生成合成图像

除了改善文本描述，直接用扩散模型生成合成图像也是重要方向：

**训练数据增强**：
- 使用 Stable Diffusion / SDXL / FLUX 等模型，根据文本 prompt 生成新的训练图像
- 可以生成现实中稀缺的场景（如特定工业缺陷、罕见动物姿态等）
- StableRep（Google，2023）证明纯合成图像可以训练出与真实数据竞争力相当的视觉编码器

**合成数据的优势**：
- **可控性**：可以精确控制图像内容、风格、分辨率
- **无版权问题**：生成的图像不受原始数据版权限制
- **标注精确**：生成时就自带精确的文本描述，无需人工标注
- **长尾补充**：可以专门生成训练集中缺失的类别或场景

**合成数据的局限**：
- **分布偏移**：合成图像的分布与真实图像存在差异
- **细节失真**：细微的物理规律违反（如手指数量、文字拼写）可能误导模型
- **多样性局限**：扩散模型倾向于生成"平均"风格的图像
- **成本**：大规模生成仍需要可观的 GPU 时间

**最佳实践**：将合成数据与真实数据混合使用，通常合成数据占比 10-30% 效果最佳。

### 4.3 自动化数据构建管线

2024-2025 年涌现了多个自动化的多模态数据构建工具：

**Cambrian-1 Data Engine**：
- 自动从网络收集图像，用多个视觉专家模型提取信息
- 用 GPT-4 综合多源信息生成训练数据
- 支持多种数据格式：caption、VQA、对话等

**LVIS-Instruct4V**：
- 基于 LVIS 数据集的细粒度类别标注
- 用 GPT-4V 对每个类别生成多样化的指令数据
- 覆盖 1000+ 物体类别

---

## 五、指令微调数据：教会模型"看图说话"

### 5.1 LLaVA 系列的指令数据

**LLaVA-Instruct-150K（LLaVA v1，NeurIPS 2023）**

这是多模态指令微调数据的开山之作：
- 基于 COCO 数据集的图像，使用 GPT-4 生成多模态指令跟随数据
- 包含 **158K** 条数据，分三种类型：
  - **Conversation**（58K）：多轮对话
  - **Detailed Description**（23K）：详细图像描述
  - **Complex Reasoning**（77K）：复杂推理问题
- 生成方法：将图像的 COCO 标注（bounding box、caption）输入 GPT-4，让其基于这些"提示"生成问答对

**LLaVA-1.5 数据（2023）**

LLaVA-1.5 扩大了指令微调数据的规模和多样性：
- **预训练阶段**：558K 图文对（CC3M 的子集），用于视觉-语言对齐
- **微调阶段**：665K 条指令数据，包括：
  - LLaVA-Instruct-150K（GPT-4 生成）
  - ShareGPT（纯文本对话数据，约 40K）
  - VQA 学术数据集：VQAv2、GQA、OKVQA、OCR-VQA、TextVQA 等
  - 参考理解数据：RefCOCO 系列

**LLaVA-NeXT / LLaVA-OneVision（2024）**

LLaVA 的后续版本进一步扩展数据策略：
- 支持多图像、视频等新模态
- 数据规模扩大到数百万条
- 引入更多数据来源：文档理解（DocVQA）、图表理解（ChartQA）、数学推理（MathVista）等
- 强调**数据效率**：不是越多越好，而是多样性和质量的平衡

### 5.2 InternVL-Chat 系列的数据策略

InternVL-Chat（OpenGVLab，CVPR 2024 Oral）采用了精细化的数据策略：

**InternVL-Chat-V1.2 SFT 数据**（约 120 万条）：
全部开源，包括：
- ShareGPT4V（高质量合成 caption）
- LLaVA-Instruct 数据
- 学术 VQA 数据集（VQAv2、GQA、TextVQA 等）
- OCR 和文档数据
- 中文多模态数据

**InternVL 2.0/2.5 的数据升级**：
- 预训练数据扩展到数千万级别
- 引入更多垂直领域数据：医学影像、遥感、工业检测等
- 多语言支持增强
- 视频理解数据增加

**InternVL 3.0（2025）**：
统一训练方案，同时学习语言和多模态能力，无需额外的桥接模块。

### 5.3 多模态 SFT 数据构建方法论

构建高质量的多模态 SFT 数据，核心方法论包括：

**1. GPT-4V/GPT-4o 标注法**
- 直接用 GPT-4V 对图像生成问答对
- 成本高（约 $0.01-0.05/图），但质量最高
- 适用于种子数据集（10K-100K 规模）

**2. 学术数据集转换法**
- 将已有的 VQA、Caption、Grounding 等学术数据集统一为对话格式
- 成本低、规模大，但格式单一
- 常用数据集：VQAv2（83K 训练图像）、GQA（113K 图像）、TextVQA（28K 图像）等

**3. 开源模型蒸馏法**
- 用强的开源多模态模型（如 InternVL-2-76B、LLaVA-OneVision-72B）标注新图像
- 成本低，可大规模生产
- 质量依赖于教师模型的能力上限

**4. 自我迭代法（Self-play / Self-improve）**
- 模型生成数据 → 过滤高质量样本 → 用于训练下一代模型
- 需要可靠的质量评估机制，否则会退化

### 5.4 多任务数据混合的关键数据源

训练一个全面的多模态模型，通常需要混合以下类型的数据：

| 任务类型 | 代表数据集 | 典型规模 |
|---------|-----------|---------|
| 一般 VQA | VQAv2, GQA, OKVQA | 100K-500K |
| 文字识别 | TextVQA, OCR-VQA, DocVQA | 50K-200K |
| 图表理解 | ChartQA, PlotQA, FigureQA | 20K-100K |
| 数学推理 | MathVista, Geometry3K | 10K-50K |
| 详细描述 | ShareGPT4V, ALLaVA | 100K-1M |
| 多轮对话 | LLaVA-Instruct, ShareGPT | 50K-150K |
| 空间理解 | RefCOCO, Visual Genome | 50K-200K |
| 视频理解 | VideoChat, VATEX | 50K-200K |

---

## 六、数据配比策略

### 6.1 预训练阶段：追求规模与覆盖

**视觉编码器预训练**（CLIP/SigLIP 训练）：
- 数据规模：通常需要 **4 亿 - 20 亿** 图文对
- 训练 token 数：ViT-L 通常看 130 亿样本（12.8B seen），ViT-G 级别需要 300 亿+
- 数据源：LAION-2B、DataComp-1B 或定制的高质量数据集
- 关键指标：数据多样性和覆盖面 > 单条数据质量

**视觉-语言对齐预训练**（MLP Projector 训练）：
- 数据规模：通常 **50 万 - 200 万** 图文对
- LLaVA-1.5 使用 558K（CC3M 子集）
- ShareGPT4V 使用 1.2M（合成高质量 caption）
- 此阶段的数据质量比规模更重要——描述需要足够详细，让 projector 学会对齐

### 6.2 微调阶段：追求质量与多样性

**指令微调**（SFT 阶段）：
- 数据规模：通常 **50 万 - 300 万** 条
- LLaVA-1.5：665K
- InternVL-Chat-V1.2：1.2M
- LLaVA-OneVision：>3M（包含多图和视频数据）

**数据配比的经验规则**：
- 通用 VQA 数据占 30-40%
- 专业领域数据（OCR、图表、数学等）占 20-30%
- 高质量合成 caption/对话占 20-30%
- 纯文本对话数据占 5-10%（保持语言能力）
- 安全/对齐数据占 2-5%

### 6.3 不同规模模型的数据需求

| 模型规模 | 视觉编码器训练数据 | 对齐预训练数据 | SFT 数据 | 总计 GPU 时间估算 |
|---------|-----------------|-------------|---------|----------------|
| 1-3B（轻量） | 使用现成 CLIP | 500K-1M | 500K-1M | 100-500 H100 小时 |
| 7-13B（中等） | 使用现成 CLIP | 1M-5M | 1M-3M | 500-2000 H100 小时 |
| 30B+（大型） | 可能需要自训 | 5M-20M | 3M-10M | 5000+ H100 小时 |

### 6.4 数据配比的高级策略

**课程学习（Curriculum Learning）**：
- 先用大量低质量数据做"粗训"，再用少量高质量数据做"精炼"
- 例如：先在 LAION 子集上预训练，再用 ShareGPT4V 做第二阶段

**动态采样**：
- 根据训练进度动态调整不同数据源的采样概率
- 训练初期偏重通用数据，后期偏重困难数据和专业数据

**数据去重与上采样的平衡**：
- 稀缺类型的数据可以适度上采样（如 OCR 数据），但上采样倍数一般不超过 3-5 倍
- 过度上采样会导致过拟合

---

## 七、实践建议：从零开始

### 7.1 如果你只想训练一个多模态聊天模型

**推荐路线（资源友好型）**：

1. **视觉编码器**：直接使用开源的预训练 CLIP/SigLIP
   - 推荐：`openai/clip-vit-large-patch14-336` 或 `google/siglip-so400m-patch14-384`
   - 不需要自己训练，节省大量资源

2. **对齐预训练数据**（约 1-2M）：
   - ShareGPT4V-PT（1.2M 高质量合成 caption）— HuggingFace 直接下载
   - 或 LLaVA-CC3M-558K — 同样公开可用
   - 此阶段只训练 projector，1-2 天可完成（8×A100）

3. **指令微调数据**（约 500K-1.5M）：
   - LLaVA-Instruct-665K（公开可用）
   - ShareGPT4V 数据的 SFT 部分
   - InternVL-Chat-V1.2-SFT-Data（1.2M，全部开源）
   - 补充学术 VQA 数据集（VQAv2、TextVQA、DocVQA 等）

4. **纯文本数据**（约 40K-100K）：
   - ShareGPT / OpenChat 等高质量对话数据
   - 用于保持 LLM 的文本能力不退化

### 7.2 如果你想训练自己的视觉编码器

**数据获取方案**：

1. **使用 DataComp 候选池**：
   - 公开提供 12.8B 候选的元数据（URL + alt-text）
   - 使用 `img2dataset` 工具批量下载
   - 自行实施过滤策略

2. **使用 LAION 数据**：
   - Re-LAION-5B（清洗后版本）提供元数据
   - 需要自行下载图片（URL 过期率约 20-30%）

3. **自建爬虫**：
   - 从 CommonCrawl 快照提取 img+alt-text
   - 实施完整的清洗管线（参见第三节）
   - 成本最高但可控性最强

**实用工具**：
- **img2dataset**：批量下载和预处理图像（支持 CC3M、LAION、COYO 等格式）
- **NVIDIA NeMo-Curator**：企业级数据清洗管线（支持 NSFW 过滤、去重等）
- **clip-retrieval**：基于 CLIP embedding 的大规模数据检索工具

### 7.3 成本估算

| 步骤 | 数据量 | 存储需求 | 处理时间 | 备注 |
|------|-------|---------|---------|------|
| 下载 1B 图文对 | 1B URL | ~50TB 原始 | 1-3 天（100 CPU） | URL 过期率 ~25% |
| CLIP 计算 embedding | ~750M 有效 | ~3TB embedding | 2-3 天（8×A100） | 用于过滤 |
| 过滤筛选 | 750M → 200M | ~15TB 最终 | 数小时（CPU） | 保留 ~25% |
| Recaption（可选） | 1M 图像 | ~5GB JSON | 3-5 天（8×A100） | 用 ShareCaptioner |

### 7.4 常见陷阱

1. **不做去重就训练**：会导致模型对高频图像过拟合，泛化能力下降
2. **忽视 NSFW 过滤**：不仅有伦理风险，也会污染模型的输出
3. **过度依赖 CLIP score**：会丧失数据多样性，应结合多种过滤策略
4. **忽视文本质量**：即使图像高质量，如果 alt-text 是"IMG_20230501"这种垃圾文本，训练效果也会很差
5. **中英文数据不均衡**：如果需要中文能力，确保中文数据占比至少 10-20%
6. **忽视版权问题**：商用时需特别注意数据集的许可协议

### 7.5 推荐的最小可行数据配置

对于一个 7B 级别的多模态模型，**最小可行数据配置**如下：

```
视觉编码器：使用现成的 SigLIP-SO400M（不需要数据）
对齐预训练：ShareGPT4V-PT 1.2M（~20GB 下载）
指令微调：
  - LLaVA-Instruct 150K
  - ShareGPT4V SFT 100K
  - VQAv2 + TextVQA + DocVQA ~300K
  - ShareGPT 纯文本 40K
  总计约 ~600K 条

预计总训练时间：3-5 天（8×A100）
预计存储需求：~500GB（图像 + 标注）
预计效果：接近 LLaVA-1.5-7B 水平
```

---

## 八、未来趋势

### 8.1 合成数据的地位将持续上升

随着 GPT-4o、Claude 3.5 等模型能力的提升，合成数据的质量上限也在不断抬高。预计未来的多模态训练数据中，合成数据的占比将从当前的 10-30% 上升到 40-60%。

### 8.2 数据管线自动化

端到端的数据管线工具（如 NVIDIA NeMo-Curator、DataComp 工具链）将使得数据清洗和过滤的门槛大幅降低。

### 8.3 数据安全与治理

LAION-5B 的 CSAM 事件敲响了警钟。未来的大规模数据集将需要更严格的安全审计流程，可能包括第三方安全认证。

### 8.4 多模态数据的 Scaling Laws

类似文本领域的 Chinchilla 定律，多模态领域也在探索最优的数据-计算配比。初步研究表明，图文数据的最优比例可能与纯文本数据有显著不同。

---

## 参考资源

### 核心论文
1. LAION-5B (Schuhmann et al., 2022) - NeurIPS 2022
2. DataComp (Gadre et al., 2023) - NeurIPS 2023
3. ShareGPT4V (Chen et al., 2023) - ECCV 2024
4. ALLaVA (Chen et al., 2024) - arXiv 2402.11684
5. LLaVA (Liu et al., 2023) - NeurIPS 2023
6. LLaVA-1.5 (Liu et al., 2023) - arXiv 2310.03744
7. InternVL (Chen et al., 2024) - CVPR 2024
8. MetaCLIP / Demystifying CLIP Data (Xu et al., 2024) - ICLR 2024
9. Data Filtering Networks (Fang et al., 2024) - ICLR 2024
10. DenseFusion-1M (Li et al., 2024)

### 数据集获取
- LAION: https://laion.ai/
- DataComp: https://github.com/mlfoundations/datacomp
- ShareGPT4V: https://github.com/ShareGPT4Omni/ShareGPT4V
- InternVL SFT Data: https://huggingface.co/datasets/OpenGVLab/InternVL-Chat-V1-2-SFT-Data
- img2dataset: https://github.com/rom1504/img2dataset

### 工具
- img2dataset: 批量图像下载与预处理
- NVIDIA NeMo-Curator: 企业级数据清洗
- clip-retrieval: CLIP-based 数据检索
- LAION-Aesthetics Predictor: 美学评分工具
