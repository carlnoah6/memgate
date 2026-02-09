# 视觉模型架构：ViT、SigLIP、InternVL 与视觉-语言对齐方案

> 研究日期：2026-02-08
> 任务来源：backlog P1 - 从零训练 LLM + 视觉模型 #10

---

## 一、总览：多模态大模型的视觉侧架构演进

多模态大语言模型（MLLM）的核心挑战在于：**如何让语言模型"看见"图像？** 这个问题可以分解为三个层次：

1. **视觉编码**：如何将图像转换为高质量的特征表示？
2. **视觉-语言对齐**：如何将视觉特征映射到语言模型能理解的空间？
3. **多模态融合**：如何在模型内部融合视觉与语言信息？

```
图像 → [视觉编码器] → 视觉特征 → [对齐模块] → 语言模型能理解的 token → [LLM] → 文本输出
```

从 2022 年到 2025 年，这三个层次都经历了重大演进。本文将系统梳理视觉编码器（ViT 家族）、对齐方案（LLaVA 路线 vs Flamingo 路线）、以及主流 SOTA 多模态模型的架构选型。

---

## 二、ViT 架构及其变体

### 2.1 Vision Transformer（ViT）基础

ViT（Dosovitskiy et al., 2020）将图像处理带入了 Transformer 时代。其核心思想极其简洁：

**将图像视为一种"外语"**——把图像切分成固定大小的 patch（通常为 16×16 或 14×14 像素），将每个 patch 线性投影为一个 embedding，加上位置编码后送入标准 Transformer Encoder 处理。

```
输入图像 (224×224) → 切分为 14×14 个 16×16 的 patch
→ 线性投影为 196 个 token → 加 [CLS] token + 位置编码
→ L 层 Transformer Encoder → 输出特征
```

**关键设计参数：**
- **Patch size**：14×14 或 16×16，更小的 patch 意味着更多 token、更高分辨率但计算量更大
- **模型规模**：ViT-B（86M）、ViT-L（303M）、ViT-H（632M）、ViT-g（1B）、ViT-G（2B）、ViT-e（4B）
- **输入分辨率**：通常 224×224 或 336×336 或 384×384，更高分辨率提升细粒度理解但增加计算量

### 2.2 CLIP ViT：视觉-语言预训练的奠基者

**CLIP**（Radford et al., 2021）是多模态模型最重要的基础设施之一。它通过**对比学习**在 4 亿图文对上联合训练视觉编码器和文本编码器：

- **训练方式**：对比损失（InfoNCE），让匹配的图文对在共享空间中靠近，不匹配的远离
- **关键优势**：ViT 学到的特征天然与文本语义对齐，为后续多模态模型提供了现成的视觉编码器
- **局限性**：(1) 全局对比学习可能丢失细粒度空间信息；(2) Softmax 归一化要求全局同步，分布式训练效率受限

**CLIP ViT-L/14@336px** 是最经典的视觉编码器选择，被 LLaVA、LLaVA-1.5、Yi-VL 等广泛采用。

### 2.3 SigLIP：更高效的对比学习

**SigLIP**（Zhai et al., 2023）对 CLIP 的训练方式做了关键改进：

- 用 **Sigmoid 损失** 替代 Softmax 对比损失，将每个图文对视为独立的二分类问题
- 不再需要全局归一化因子，天然支持高效分布式训练
- 引入可学习的 bias 项来处理正负样本不均衡问题

$$\mathcal{L}_{\text{SigLIP}} = -\frac{1}{N} \sum_{i=1}^{N} \sum_{j=1}^{N} \log \frac{1}{1 + e^{z_{ij}(-\tau \cdot I_e^{(i)} \cdot T_e^{(j)} + b)}}$$

**SigLIP 的优势：**
- 更好的并行化——每个设备独立计算损失，无需跨设备同步
- 在相同计算预算下通常优于 CLIP
- **SigLIP-So400m-patch14-384** 成为 2024-2025 年最受欢迎的视觉编码器选择

**SigLIP 2**（Tschannen et al., 2025）进一步改进：
- 提供四种规模：ViT-B (86M)、ViT-L (303M)、ViT-So400m (400M)、ViT-g (1B)
- 增强了多语言支持、空间定位能力和密集特征提取
- 在零样本分类、图文检索和作为 VLM 视觉编码器时全面超越 SigLIP 1

### 2.4 EVA / EVA-CLIP：大规模高效视觉编码器

**EVA**（Fang et al., 2023）和 **EVA-CLIP** 系列的核心贡献：

- **EVA-02**：通过 MIM（Masked Image Modeling）预训练 + CLIP 微调的两阶段训练方案
- **EVA-CLIP-E**：达到 4.4B 参数的超大规模视觉编码器
- 在 ImageNet 等基准上实现顶尖性能
- 被 CogVLM 等模型采用作为视觉骨干

### 2.5 DINOv2：自监督视觉特征的王者

**DINOv2**（Oquab et al., 2024）走了一条不同于 CLIP 的路线——**纯视觉自监督学习**：

- **训练方式**：自蒸馏（self-distillation）+ 掩码图像建模，不使用任何文本标注
- **核心优势**：
  - 提取极其丰富的**细粒度局部特征**，在语义分割、深度估计等密集预测任务上表现卓越
  - 特征具有很强的空间结构感知能力
- **与 CLIP 的互补性**：CLIP 学习全局语义对齐特征，DINOv2 学习细粒度视觉结构特征

**实际应用中的融合策略：**
- **Additive-MoF（A-MoF）**：线性混合 CLIP 和 DINOv2 特征后送入 adapter
- **Interleaved-MoF（I-MoF）**：空间交错 CLIP 和 DINOv2 的 visual tokens
- 多个研究（如 MMVP、VIRAL 等）表明，DINOv2 + CLIP 的混合方案能显著提升多模态模型在视觉感知密集型任务上的表现

### 2.6 CoCa 与 CapPa：融合对比学习与生成

除了纯对比学习（CLIP/SigLIP）和纯自监督（DINOv2），还有融合路线：

**CoCa**（Contrastive Captioner, Yu et al., 2022）：
- 同时使用对比损失和图像描述生成损失
- 文本解码器分为单模态和多模态两部分
- 训练信号更丰富，兼顾全局对齐和细粒度理解

**CapPa**（Tschannen et al., 2023）：
- 用图像描述任务替代对比学习来预训练视觉编码器
- 结合自回归解码和并行解码两种模式
- 更接近视觉编码器在 VLM 中的实际使用方式

**当前趋势**：Qwen2.5-VL 和 Kimi-VL 的视觉编码器都采用了类似 CoCa 的混合训练策略（SigLIP loss + captioning loss），这一融合方案正成为最新主流。

---

## 三、视觉-语言对齐的两大路线

多模态模型的核心架构问题是：**如何将视觉编码器的输出与 LLM 连接起来？** 目前有两大主流路线。

### 3.1 LLaVA 路线：投影层对齐 + Token 拼接

**核心思想**：将视觉特征通过一个轻量级投影层映射到 LLM 的 embedding 空间，然后像文本 token 一样直接拼接到 LLM 的输入序列中。

```
图像 → ViT → 视觉 tokens (e.g. 256个) → MLP 投影层 → 视觉 embeddings
文本 → Tokenizer → 文本 embeddings
→ [视觉 embeddings; 文本 embeddings] → LLM → 输出
```

**LLaVA 系列的演进：**

| 版本 | 视觉编码器 | 投影层 | LLM | 关键改进 |
|------|-----------|--------|-----|---------|
| LLaVA (2023) | CLIP ViT-L/14@224 | 线性层 | Vicuna-7B/13B | 首创简洁的投影+指令微调范式 |
| LLaVA-1.5 (2023) | CLIP ViT-L/14@336 | 2层 MLP | Vicuna-7B/13B | 更高分辨率，MLP 投影效果更好 |
| LLaVA-NeXT/1.6 (2024) | CLIP ViT-L/14@336 | MLP | 多种 LLM | 动态分辨率（AnyRes），高分辨率切片 |
| LLaVA-OneVision (2024) | SigLIP-So400m | MLP | Qwen2-7B | 统一图像/视频/多图理解 |
| LLaVA-OneVision-1.5 (2025) | 自训练编码器 | MLP | Qwen2.5-7B | 自研视觉编码器，端到端优化 |

**LLaVA 路线的优势：**
1. **极简架构**：不修改 LLM 内部结构，只在外部添加投影层
2. **训练高效**：两阶段训练——(1) 冻结 ViT+LLM，只训练投影层；(2) 解冻 LLM，进行视觉指令微调
3. **灵活性强**：视觉编码器和 LLM 可自由组合替换
4. **社区生态好**：代码简洁、复现容易，衍生出大量工作

**LLaVA 路线的局限：**
1. **Token 数量膨胀**：视觉 token 直接注入 LLM 输入序列，高分辨率图像或视频会产生大量 token，增加计算开销
2. **视觉信息压缩不足**：所有视觉 patch 同等对待，缺乏选择性注意力
3. **上下文窗口压力**：视觉 token 占用 LLM 的上下文窗口

### 3.2 Flamingo 路线：交叉注意力融合

**核心思想**：在 LLM 的 Transformer 层之间插入**交叉注意力（Cross-Attention）层**，让语言 token 能够"查看"视觉特征，而非直接拼接。

```
图像 → ViT → 视觉特征 → Perceiver Resampler → 固定数量的视觉 tokens
                                                        ↓
文本 → LLM 各层 ←←←←←←← 每隔 N 层插入 Gated Cross-Attention ←←
```

**Flamingo（Alayrac et al., 2022）的关键设计：**
- **Perceiver Resampler**：用一组可学习的 query，通过交叉注意力从视觉编码器的输出中提取固定数量（通常 64 个）的视觉 token，实现信息压缩
- **Gated Cross-Attention**：在冻结的 LLM 层之间插入带门控机制的交叉注意力层，视觉 embeddings 作为 K/V，文本 embeddings 作为 Q
- **门控机制**：新增层的输出通过 tanh gate 控制，初始化为 0，保证训练初期不破坏预训练 LLM 的能力

**Flamingo 路线的代表模型：**
- **Flamingo**（DeepMind, 2022）：80B，开创性工作
- **BLIP-2**（Salesforce, 2023）：引入 Q-Former，支持文本条件的视觉信息提取
- **Idefics**（HuggingFace, 2023）：Flamingo 的开源复现
- **LLaMA 3.2 Vision**（Meta, 2024）：在每 4 层插入交叉注意力，不使用门控
- **Gemini 系列**（Google, 2024-2025）：内部细节未公开但被认为使用了类似策略

**Flamingo 路线的优势：**
1. **Token 压缩**：通过 Perceiver/Q-Former 将任意数量的视觉输入压缩为固定 token 数，对视频理解尤其重要
2. **不增加上下文长度**：视觉信息通过交叉注意力侧向注入，不占用 LLM 的序列长度
3. **多图/视频友好**：可以优雅地处理多帧输入

**Flamingo 路线的局限：**
1. **引入大量新参数**：交叉注意力层的 K/V 投影矩阵参数量不小
2. **需要修改 LLM 内部结构**：不如 LLaVA 路线的"即插即用"灵活
3. **训练复杂度高**：需要仔细设计冻结/解冻策略

### 3.3 第三条路线：Q-Former（BLIP-2）

**BLIP-2**（Li et al., 2023）介于两者之间，引入了 **Q-Former** 作为桥梁：

- Q-Former 包含两个子模块：一个与冻结的视觉编码器交互（提取视觉特征），另一个处理文本输入
- 使用可学习的 query vectors 通过交叉注意力从视觉编码器提取信息
- 文本条件化：Q-Former 可以根据输入文本有选择地提取相关视觉信息
- 但最终仍然是将提取的视觉 token 拼接到 LLM 输入

### 3.4 当前趋势：LLaVA 路线胜出

**2024-2025 年的明确趋势是 LLaVA 式的投影+拼接路线全面胜出：**

- InternVL 系列：ViT-MLP-LLM
- Qwen-VL 系列：从 Qwen-VL（cross-attention resampler）转向 Qwen2-VL（MLP 投影）
- LLaVA-OneVision：MLP 投影
- DeepSeek-VL 系列：MLP 投影
- PaliGemma 系列：线性投影
- Phi-3.5-vision：MLP 投影

**转变原因：**
1. MLP 投影层足够简洁且效果好，"奥卡姆剃刀"原则
2. 通过动态分辨率、token 压缩（如像素洗牌 pixel shuffle）等技术缓解了 token 膨胀问题
3. 全参数微调（而非仅训练交叉注意力层）成为可能，投影层方案训练更简单
4. 社区实践证明简单架构 + 更多/更好的数据比复杂架构更有效

唯一的例外是 **LLaMA 3.2 Vision**（Meta），它仍然使用交叉注意力方案。Meta 的选择可能与其希望视觉模块可拆卸、不影响原始 LLM 能力有关。

---

## 四、SOTA 多模态模型架构对比

### 4.1 InternVL 系列

**InternVL**（Chen et al., 2024，CVPR 2024 Oral）是开源多模态模型的标杆之一。

**架构：ViT-MLP-LLM**

| 组件 | InternVL 2.5 详情 |
|------|------------------|
| 视觉编码器 | InternViT-6B-448px（6B 参数！）或 InternViT-300M |
| 投影层 | 2层 MLP（随机初始化） |
| LLM | InternLM 2.5 / Qwen 2.5（多种规模） |
| 输入分辨率 | 动态分辨率，将图像切分为 448×448 的 tile |
| Token 压缩 | Pixel Shuffle（4倍下采样），每个 tile 256 token |

**InternViT 的独特之处：**
- **超大规模视觉编码器**：6B 参数的 ViT 是业界最大的开源视觉编码器
- **渐进式对齐训练**：先与小 LLM 对齐，再逐步迁移到大 LLM
- InternVL 2.5 论文的重要发现：**大视觉编码器显著降低了对训练数据量的依赖**——相比 Qwen2-VL-72B（600M 视觉编码器），InternVL2.5-78B 用更少的数据就达到了可比或更好的效果

**InternVL3**（2025）的新改进：
- Variable Visual Position Encoding（可变视觉位置编码）
- Native Multimodal Pre-Training（原生多模态预训练）
- Mixed Preference Optimization
- Multimodal Test-Time Scaling

### 4.2 Qwen-VL 系列

**Qwen-VL 的架构演进极具代表性——从复杂走向简洁：**

| 版本 | 视觉编码器 | 对齐方式 | 特色 |
|------|-----------|---------|------|
| Qwen-VL (2023) | CLIP ViT-G (OpenCLIP) | Cross-Attention Resampler (256 tokens) | 类 Flamingo 路线 |
| Qwen2-VL (2024) | 自研 ViT (675M) | 2层 MLP | 转向 LLaVA 路线 + Naive Dynamic Resolution |
| Qwen2.5-VL (2025) | 改进 ViT (675M, SwiGLU+RMSNorm) | MLP | Window Attention + mRoPE |

**Qwen2.5-VL 的关键创新：**

1. **Naive Dynamic Resolution**：不对图像做固定分辨率缩放，直接将原始分辨率的图像送入 ViT。ViT 使用 window attention（最大窗口 8×8），计算量与 patch 数线性增长
2. **ViT 架构对齐 LLM**：视觉编码器使用 SwiGLU 激活和 RMSNorm，与 Qwen2.5 LLM 架构一致
3. **mRoPE（Multimodal RoPE）**：将 RoPE 的频率分量分为时间、高度、宽度三部分，让位置编码同时携带空间和时间信息
4. **从头训练视觉编码器**：不依赖预训练的 CLIP/SigLIP，使用 SigLIP loss + captioning loss 混合训练

### 4.3 LLaVA-OneVision 系列

**LLaVA-OneVision**（Li et al., 2024）代表了 LLaVA 路线的最新进展：

| 组件 | 详情 |
|------|------|
| 视觉编码器 | SigLIP-So400m-patch14-384 |
| 投影层 | 2层 MLP |
| LLM | Qwen2-7B-Instruct |
| 分辨率处理 | AnyRes（将高分辨率图像切片+缩略图） |

**LLaVA-OneVision-1.5**（2025）的突破：
- **自研视觉编码器**：不再依赖外部预训练的 SigLIP，而是使用 cluster discrimination loss 从头训练
- 统一了通用理解、OCR 和定位能力

### 4.4 其他重要模型

**PaliGemma 2**（Google, 2024）：
- 视觉编码器：SigLIP-So400m
- 对齐方式：线性投影
- LLM：Gemma 2（2B/9B/27B）
- 特色：极简架构，图像 token 放在文本之前作为"prefix"

**DeepSeek-VL2**（DeepSeek, 2024）：
- 视觉编码器：SigLIP-So400m + SAM-B 双编码器
- 对齐方式：MLP 投影
- LLM：DeepSeek MoE
- 特色：双视觉编码器捕获语义 + 细粒度空间信息

**CogVLM**（Tsinghua, 2024）：
- 视觉编码器：EVA-02-CLIP-E
- 融合方式：**Modality Experts**——在 LLM 的 FFN 中为视觉和文本设置不同的专家参数
- 这是一种介于投影和交叉注意力之间的方案

**Kimi-VL**（Moonshot, 2025）：
- 视觉编码器：MoonViT（自研，动态分辨率，SigLIP + captioning 混合训练）
- 对齐方式：MLP 投影
- LLM：Kimi MoE
- 策略类似 Qwen2.5-VL

### 4.5 架构对比总结表

| 模型 | 视觉编码器 | 编码器参数量 | 对齐方式 | 融合策略 | 动态分辨率 |
|------|-----------|------------|---------|---------|-----------|
| InternVL 2.5 | InternViT-6B | 6B | MLP | Token 拼接 | Tile 切分 |
| Qwen2.5-VL | 自研 ViT | 675M | MLP | Token 拼接 | Naive Dynamic |
| LLaVA-OneVision | SigLIP-So400m | 400M | MLP | Token 拼接 | AnyRes |
| PaliGemma 2 | SigLIP-So400m | 400M | Linear | Token 拼接 (prefix) | 固定 |
| DeepSeek-VL2 | SigLIP + SAM | 400M+86M | MLP | Token 拼接 | 动态 |
| LLaMA 3.2 Vision | 自研 ViT | - | Cross-Attn | 交叉注意力 | - |
| CogVLM | EVA-02-CLIP-E | 4.4B | MLP | Modality Experts | - |

---

## 五、视觉 Encoder 选型建议

### 5.1 预训练方式的选择

| 预训练方式 | 代表 | 适合场景 | 优劣 |
|-----------|------|---------|------|
| 对比学习（CLIP/SigLIP） | SigLIP-So400m | 通用多模态理解 | 特征与文本天然对齐，但可能丢失细粒度空间信息 |
| 自监督（DINOv2） | DINOv2-g | 需要精细视觉理解的场景 | 出色的局部特征，但不与文本对齐 |
| 混合训练（CoCa/SigLIP+Cap） | Qwen2.5-VL ViT | 追求极致性能 | 兼顾全局语义和细粒度理解，但需要大量训练资源 |
| 对比+自监督双编码器 | DeepSeek-VL2 | 兼顾语义和空间 | 更多参数和复杂度 |

**推荐**：
- **最稳妥选择**：SigLIP-So400m-patch14-384（开箱即用，效果好，社区支持强）
- **追求极致**：自研编码器 + SigLIP + Captioning 混合训练
- **需要细粒度视觉**：SigLIP + DINOv2 双编码器融合

### 5.2 分辨率策略

| 策略 | 代表模型 | 优劣 |
|------|---------|------|
| 固定分辨率 | 早期 LLaVA (224/336) | 简单，但高分辨率图像丢失信息 |
| Tile 切分 + 缩略图 | InternVL（448px tile）| 灵活，token 数可控 |
| AnyRes | LLaVA-NeXT/OneVision | 保持宽高比，切片处理 |
| Naive Dynamic Resolution | Qwen2-VL / Qwen2.5-VL | 最原生，无信息损失，但 token 数不固定 |

**推荐**：
- 如果计算资源充足：Naive Dynamic Resolution（Qwen 路线），避免任何信息损失
- 如果需要控制计算量：Tile 切分 + 缩略图（InternVL 路线），可控制最大 tile 数

### 5.3 编码器规模 vs LLM 规模

InternVL 2.5 论文的一个重要发现值得强调：

> **大视觉编码器显著降低了 MLLM 对训练数据量的依赖。**

这意味着：
- 如果你**训练数据充足**，较小的视觉编码器（如 SigLIP 400M）配合大 LLM 也能达到很好效果（Qwen2.5-VL 路线）
- 如果你**训练数据有限**，投资更大的视觉编码器（如 InternViT-6B）可能更划算
- 视觉编码器和 LLM 的规模比例约为 **1:5 到 1:20** 是合理范围

### 5.4 与 LLM 的兼容性

- **架构对齐**：Qwen2.5-VL 的做法值得借鉴——让 ViT 使用与 LLM 相同的组件（SwiGLU、RMSNorm），可能有利于联合训练
- **Token 压缩**：Pixel Shuffle（InternVL 使用 4 倍下采样）是简单有效的 token 压缩方案
- **位置编码**：2D/3D RoPE（如 Qwen 的 mRoPE）优于学习的位置编码，因为可以自然扩展到更高分辨率

---

## 六、实践建议：从零开始做多模态模型该选什么架构

### 6.1 入门推荐：LLaVA 路线 + SigLIP

如果你是第一次构建多模态模型，或者资源有限：

```
SigLIP-So400m-patch14-384 → 2层 MLP → Qwen2.5/LLaMA 3 系列 LLM
```

**为什么这样选：**
1. SigLIP 编码器质量高、社区支持好、直接从 HuggingFace 下载
2. MLP 投影层训练快、简单
3. 两阶段训练成熟可靠：(1) 预训练投影层；(2) 指令微调
4. 大量开源代码可参考（LLaVA 代码库、InternVL 代码库等）

**训练流程：**
1. **阶段一（预训练对齐）**：冻结 ViT 和 LLM，只训练 MLP 投影层。使用图文配对数据（如 LLaVA-558K），约 1-2 epoch
2. **阶段二（视觉指令微调）**：解冻 LLM（和可选地 ViT），使用高质量指令微调数据。这是模型能力提升的关键阶段

### 6.2 进阶方案：动态分辨率 + 更强编码器

当基础方案跑通后，可以逐步升级：

1. **添加动态分辨率支持**：参考 LLaVA-NeXT 的 AnyRes 方案或 InternVL 的 tile 切分
2. **升级视觉编码器**：尝试 SigLIP 2 或 InternViT
3. **Token 压缩**：添加 Pixel Shuffle 或池化层减少 token 数量
4. **多阶段训练**：增加预训练数据量和多样性

### 6.3 前沿探索：自研视觉编码器

如果你有充足的计算资源（≥256 GPU），可以考虑从头训练视觉编码器：

- **架构**：使用与目标 LLM 对齐的组件（SwiGLU、RMSNorm、RoPE）
- **训练**：SigLIP loss + Captioning loss 混合训练
- **数据**：大规模图文配对数据（DataComp、LAION 等）
- **分辨率**：从 224 开始，渐进提升到 384/448+

### 6.4 关键 Lessons Learned

1. **简单架构 + 好数据 > 复杂架构 + 差数据**：LLaVA 系列反复证明了这一点
2. **视觉编码器的质量是天花板**：LLM 只能处理它"看到"的东西
3. **动态分辨率是大势所趋**：固定分辨率限制了模型能力
4. **Token 压缩很重要**：尤其是处理高分辨率图像和视频时
5. **投影层虽然简单但至关重要**：从线性层升级到 MLP 带来的提升显著且成本极低
6. **交叉注意力路线虽好但社区已转向投影路线**：除非有特殊需求（如模块可拆卸性），否则建议跟随主流

---

## 七、总结

2024-2025 年的多模态模型架构已经形成了清晰的共识：

**视觉编码器**：SigLIP（或其混合训练变体）是主流选择，InternViT 证明了大规模视觉编码器的价值，DINOv2 作为互补特征源有重要价值。

**对齐方式**：MLP 投影层 + Token 拼接（LLaVA 路线）已经成为事实标准，交叉注意力（Flamingo 路线）仅在少数场景使用。

**分辨率处理**：动态分辨率是大势所趋，具体实现方式（Tile 切分 vs Naive Dynamic）各有优劣。

**核心趋势**：
- 架构趋于简化：投影层 > 交叉注意力 > Q-Former
- 训练方法趋于融合：SigLIP + Captioning > 纯对比学习
- 数据质量和规模的重要性超过架构创新
- 视觉编码器从"拿来主义"走向"自研训练"

对于从零开始的实践者，建议从 **SigLIP + MLP + 开源 LLM** 的组合起步，先跑通完整流程，再根据需求逐步升级各个组件。

---

## 参考资料

1. Dosovitskiy et al. "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" (ViT, 2020)
2. Radford et al. "Learning Transferable Visual Models From Natural Language Supervision" (CLIP, 2021)
3. Zhai et al. "Sigmoid Loss for Language Image Pre-Training" (SigLIP, 2023)
4. Tschannen et al. "SigLIP 2: Multilingual Vision-Language Encoders" (SigLIP 2, 2025)
5. Oquab et al. "DINOv2: Learning Robust Visual Features without Supervision" (DINOv2, 2024)
6. Fang et al. "EVA: Exploring the Limits of Masked Visual Representation Learning at Scale" (EVA, 2023)
7. Liu et al. "Visual Instruction Tuning" (LLaVA, 2023)
8. Liu et al. "Improved Baselines with Visual Instruction Tuning" (LLaVA-1.5, 2023)
9. Alayrac et al. "Flamingo: a Visual Language Model for Few-Shot Learning" (Flamingo, 2022)
10. Li et al. "BLIP-2: Bootstrapping Language-Image Pre-training" (BLIP-2, 2023)
11. Chen et al. "InternVL: Scaling up Vision Foundation Models" (InternVL, 2024)
12. Chen et al. "Expanding Performance Boundaries of Open-Source Multimodal Models" (InternVL 2.5, 2024)
13. Bai et al. "Qwen2-VL: Enhancing Vision-Language Model's Perception of the World at Any Resolution" (Qwen2-VL, 2024)
14. Qwen Team. "Qwen2.5-VL Technical Report" (Qwen2.5-VL, 2025)
15. Li et al. "LLaVA-OneVision: Easy Visual Task Transfer" (LLaVA-OneVision, 2024)
16. Yu et al. "CoCa: Contrastive Captioners are Image-Text Foundation Models" (CoCa, 2022)
17. Wang et al. "CogVLM: Visual Expert for Pretrained Language Models" (CogVLM, 2024)
18. Lu et al. "DeepSeek-VL2: Mixture-of-Experts Vision-Language Models" (DeepSeek-VL2, 2024)
