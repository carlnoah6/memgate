# 多模态融合：视觉 Encoder 与 LLM 的连接方式与训练阶段划分

> 研究日期：2026-02-08
> 任务来源：backlog P1 - 从零训练 LLM + 视觉模型 #12

---

## 一、总览：多模态融合的核心问题

在构建视觉-语言多模态大模型（Vision-Language Model, VLM）时，最关键的架构决策之一是：**如何将视觉 encoder 的输出与 LLM 连接起来？** 这个"连接"不仅仅是工程上的接口问题，更是决定模型能力上限的架构核心。

从宏观视角看，多模态融合需要回答以下问题：

1. **连接方式**：视觉特征如何进入 LLM？是简单投影、还是深度交互？
2. **训练阶段**：何时冻结、何时解冻？分几个阶段训练？
3. **分辨率处理**：如何应对不同尺寸的输入图像？
4. **Token 效率**：视觉 token 数量如何控制？太多会爆显存，太少丢信息。

这四个问题构成了多模态融合设计的完整框架。以下逐一深入分析。

---

## 二、视觉 Encoder 与 LLM 的连接方式

连接方式（也称 connector 或 projector）是多模态融合的核心模块，负责将视觉 encoder 输出的特征向量映射到 LLM 的 embedding 空间中。根据融合深度，可以分为四大类。

### 2.1 线性投影 / MLP 投影

**核心思想**：用一个简单的线性层或多层感知机（MLP）将视觉 encoder 的输出直接投影到 LLM 的词嵌入空间。投影后的视觉 token 与文本 token 拼接（concatenate），一起送入 LLM 的 decoder 进行自回归生成。

**代表工作**：
- **LLaVA**（Liu et al., 2023）：最早使用单层线性投影连接 CLIP ViT-L 与 Vicuna/LLaMA。LLaVA-1.5 升级为 2 层 MLP（带 GELU 激活），效果显著提升。
- **InternVL 系列**（1.5 / 2.0 / 2.5）：采用 "ViT-MLP-LLM" 范式，使用 2 层随机初始化的 MLP projector。
- **LLaVA-OneVision**：同样使用 2 层 MLP（mlp2x_gelu），与 SigLIP 视觉 encoder 配合。

**优点**：
- 结构极简，参数量少（通常 <50M），训练高效
- 实现简单，易于调试和迭代
- 已被反复验证有效，是当前主流选择
- 视觉 token 与文本 token 共享 LLM 的全部注意力层，信息交互充分

**缺点**：
- 视觉 token 数量与视觉 encoder 的空间分辨率直接耦合（如 ViT-L/14 在 224×224 输入下产生 256 个 token，384×384 下产生 729 个 token）
- 需要额外的 token 压缩手段来控制计算开销

**技术细节**：
```python
# LLaVA-1.5 风格的 2 层 MLP Projector
class MLPProjector(nn.Module):
    def __init__(self, vision_dim, llm_dim):
        self.linear1 = nn.Linear(vision_dim, llm_dim)
        self.act = nn.GELU()
        self.linear2 = nn.Linear(llm_dim, llm_dim)
    
    def forward(self, visual_features):
        return self.linear2(self.act(self.linear1(visual_features)))
```

### 2.2 Q-Former（Queried Transformer）

**核心思想**：引入一组可学习的 query token（通常 32 或 64 个），通过交叉注意力机制从视觉 encoder 的输出中"提问"并提取信息。这些 query token 的输出就是固定数量的视觉表示，随后送入 LLM。

**代表工作**：
- **BLIP-2**（Li et al., 2023）：提出 Q-Former 架构，使用 32 个可学习的 query token。Q-Former 内部包含自注意力层（query 之间交互）和交叉注意力层（query 与视觉特征交互），可看作一个轻量级的 Transformer encoder-decoder。
- **InstructBLIP**（Dai et al., 2023）：在 BLIP-2 基础上增加指令感知能力，让 Q-Former 也接收文本指令。
- **BLIVIA**：采用 MLP + Q-Former 的混合连接器，在文本密集场景表现更好。

**优点**：
- 输出 token 数量固定且可控，与输入分辨率解耦
- 天然的 token 压缩能力（如 256 个视觉 patch → 32 个 query token）
- 可以学习到更有选择性的视觉特征

**缺点**：
- Q-Former 本身有 ~188M 参数（BLIP-2 中），训练开销不小
- 固定数量的 query 可能在高分辨率或细粒度任务中丢失关键信息
- 架构较为复杂，需要精心设计预训练数据和策略
- 实验表明，在同等训练数据下，Q-Former 的最终效果不一定优于简单的 MLP 投影

**为何逐渐式微**：2024 年以来，社区普遍发现简单的 MLP 投影 + 高质量训练数据的组合足以匹敌甚至超越 Q-Former。Qwen-VL 最初使用类似 Q-Former 的交叉注意力，但 Qwen2-VL 转向了 MLP。这一趋势反映了 "简单架构 + 充分训练" 策略的胜利。

### 2.3 交叉注意力（Cross-Attention）

**核心思想**：在 LLM 的 Transformer 层之间插入额外的交叉注意力层（gated cross-attention），让语言 token 在生成过程中动态地"查看"视觉特征。视觉特征作为 key/value，语言 token 作为 query。

**代表工作**：
- **Flamingo**（Alayrac et al., 2022）：在冻结的 Chinchilla LLM 的每个 Transformer 层之间插入 gated cross-attention 模块。门控机制（tanh gating，初始化为 0）确保新加模块在训练初期不干扰 LLM 的原始行为。
- **CogVLM**（Wang et al., 2024）：先用 MLP 投影视觉嵌入，再在 LLM 内部使用交叉注意力适配器，视觉 token 在 QKV 层拥有独立的投影矩阵。
- **Otter**：基于 Flamingo 的开源实现，验证了交叉注意力在 few-shot 学习中的优势。

**优点**：
- 视觉信息在 LLM 的每一层都可被访问，融合更深入
- 适合 few-shot 和 in-context learning 场景
- 门控机制使得在冻结 LLM 上训练更稳定

**缺点**：
- 新增大量参数（每层 LLM 都需要一个交叉注意力模块）
- 推理时计算开销增加
- 实现复杂度高，调试难度大
- 需要修改 LLM 架构，不如 MLP 投影那样"即插即用"

### 2.4 Perceiver Resampler

**核心思想**：Perceiver Resampler 可以看作 Q-Former 的简化变体，同样使用一组可学习的 latent query，通过交叉注意力从可变长度的视觉特征序列中抽取固定数量的特征向量。与 Q-Former 相比，它更侧重于维度压缩和序列重采样。

**代表工作**：
- **Flamingo**（Alayrac et al., 2022）：使用 Perceiver Resampler 将来自视觉 encoder 的可变长度特征（尤其是视频帧的特征序列）压缩为固定的 64 个 latent token。
- **Idefics2**：继承了 Perceiver Resampler 的设计，但进行了简化和优化。

**工作原理**：
1. 初始化 N 个可学习的 latent query（如 64 个）
2. 视觉特征序列作为 key/value
3. latent query 通过多层交叉注意力从视觉特征中提取信息
4. 输出 N 个固定维度的 token，送入后续模块

**与 Q-Former 的区别**：
| 特性 | Q-Former | Perceiver Resampler |
|------|---------|-------------------|
| 自注意力 | query 之间有自注意力 | latent 之间有自注意力 |
| 文本交互 | 可同时接受文本输入 | 仅处理视觉特征 |
| 参数量 | 较大（~188M） | 较小 |
| 下游连接 | 直接送入 LLM | 通过交叉注意力注入 LLM |

### 2.5 连接方式的演进趋势

从 2022 年到 2025 年底，连接方式的演进可以总结为一条清晰的主线：

```
复杂架构 → 简单架构
Q-Former / 交叉注意力 → MLP 投影

2022: Flamingo（交叉注意力 + Perceiver Resampler）
2023: BLIP-2（Q-Former）→ LLaVA（线性投影）
2024: LLaVA-1.5（MLP）→ InternVL 1.5（MLP）→ Qwen2-VL（MLP）
2025: 几乎所有 SOTA 模型都采用 MLP 投影 + token 压缩
```

**结论**：MLP 投影已成为事实标准。简单的两层 MLP + GELU 激活足以完成视觉到语言的特征空间对齐。更复杂的连接器（如 Q-Former）带来的收益被更充分的训练数据和更精细的训练策略所替代。

---

## 三、训练阶段划分

多模态模型的训练通常分为多个阶段，每个阶段有不同的目标、数据和冻结策略。

### 3.1 经典两阶段训练（LLaVA 范式）

**Stage 1：预训练对齐（Pre-training for Feature Alignment）**

- **目标**：训练 projector，让视觉特征与 LLM 的词嵌入空间对齐
- **冻结策略**：冻结视觉 encoder 和 LLM，**仅训练 projector**
- **数据**：大规模图文配对数据（如 CC3M 子集 595K 对、LCS-558K 等），格式为简单的图片-caption 对
- **训练时间**：相对较短（LLaVA-1.5 约 6 小时，8×A100）
- **核心思路**：这个阶段本质上是"训练一个视觉 tokenizer"，让 LLM 能把视觉特征当作"外语单词"来理解

**Stage 2：指令微调（Visual Instruction Tuning）**

- **目标**：教会模型遵循多模态指令、进行视觉问答和对话
- **冻结策略**：冻结视觉 encoder，**解冻 projector 和 LLM 全部参数**
- **数据**：高质量多模态指令数据，包括：
  - GPT 生成的多模态对话数据（约 150K）
  - 学术 VQA 数据（约 515K，来自 VQAv2、GQA、OKVQA 等）
  - OCR 数据（TextVQA、OCR-VQA）
  - 合计约 665K（LLaVA-1.5）
- **训练时间**：较长（LLaVA-1.5 约 20 小时，8×A100）
- **学习率**：通常比 Stage 1 更低（如 2e-5 vs 1e-3）

### 3.2 三阶段训练（LLaVA-OneVision 范式）

LLaVA-OneVision 在经典两阶段基础上引入了第三个阶段，实现跨场景的能力迁移：

**Stage 1：语言-图像对齐（Language-Image Alignment）**
- 与经典 Stage 1 基本相同，使用 558K LCS 数据训练 projector
- 冻结 ViT + LLM，仅训练 MLP projector

**Stage 1.5：高质量知识学习（High-Quality Knowledge Learning）**
- **创新点**：在对齐之后、指令微调之前，加入一个中间阶段
- 使用高质量的图文知识数据（如 ALLaVA、ShareGPT4V 等）
- 解冻 LLM 和 projector，ViT 仍冻结
- 目的是让模型在大规模指令微调之前先建立高质量的视觉理解基础

**Stage 2：视觉指令微调（Visual Instruction Tuning）**
- 使用大规模混合数据集（3.2M 单图、0.56M 多图、0.35M 视频样本）
- 全参数训练（ViT、projector、LLM 全部解冻）
- 采用课程学习策略：先单图 → 再加入多图 → 最后加入视频

### 3.3 InternVL 的训练策略

InternVL 2.5 采用了更细粒度的渐进式训练策略：

**阶段 1：视觉 encoder 增量预训练**
- 对 InternViT-6B 进行增量预训练（在 CLIP 基础上继续训练）
- 使用大规模图文对数据，增强 OCR、中文理解等能力
- 此阶段 LLM 未参与

**阶段 2：视觉-语言对齐**
- 使用随机初始化的 2 层 MLP projector 连接 InternViT 和 LLM
- 冻结 ViT 和 LLM，仅训练 projector

**阶段 3：端到端微调**
- 解冻全部模块（ViT、projector、LLM），使用高质量指令数据
- 特别注重数据质量：通过大量人工标注和 GPT-4 辅助校验提升数据质量

### 3.4 Qwen2-VL / Qwen2.5-VL 的训练策略

Qwen 系列采用了独特的三阶段方案：

**阶段 1：视觉 encoder 预训练**
- Qwen2.5-VL 从头训练了一个原生动态分辨率 ViT（使用 window attention）
- 不依赖 CLIP 预训练权重，直接在大规模数据上训练
- 这是与其他方案最大的差异化点

**阶段 2：多模态预训练**
- 将 ViT 与 LLM 通过 MLP 连接，进行大规模多模态预训练
- 使用数十亿级图文对数据

**阶段 3：指令微调**
- 使用高质量指令数据进行精调
- 全参数训练

### 3.5 高分辨率适配阶段

在主要训练阶段之外，许多模型还有专门的高分辨率适配策略：

- **LLaVA-NeXT**：在 LLaVA-1.5 基础上引入 AnyRes 策略，将图像切分为多个 tile（最多 2×2），每个 tile 按 ViT 原生分辨率处理，同时保留一个全局缩略图
- **InternVL 1.5/2.0/2.5**：采用 448×448 的 tile 划分，支持 1-12 个 tile（即最高约 4K 分辨率），加上 pixel unshuffle 压缩
- **Qwen2-VL/2.5-VL**：原生支持动态分辨率，ViT 的位置编码使用 M-RoPE（Multimodal Rotary Position Embedding），无需 tile 划分

---

## 四、冻结策略

冻结策略直接决定了训练效率和模型性能的平衡。

### 4.1 冻结视觉 Encoder

**何时冻结**：
- Stage 1（对齐阶段）：几乎总是冻结 ViT
- Stage 2（微调阶段）：LLaVA 冻结 ViT，InternVL 和 LLaVA-OneVision 解冻 ViT

**冻结的理由**：
- 预训练的视觉 encoder（如 CLIP ViT、SigLIP）已在数十亿图文对上训练，视觉特征已非常强大
- 冻结可以保留视觉表示的泛化能力
- 显著减少训练的 GPU 显存和计算需求

**解冻的理由**：
- 冻结的 ViT 特征可能与下游任务不完全匹配
- 解冻可以让 ViT 学习到更适合当前 LLM 的视觉表示
- 实验证明，在 Stage 2 解冻 ViT 可以带来 1-3% 的 benchmark 提升
- 对于 OCR、文档理解等细粒度任务，解冻 ViT 尤其重要

### 4.2 冻结 LLM

**何时冻结**：
- Stage 1（对齐阶段）：冻结 LLM，避免大规模图文对数据"污染"语言能力
- Stage 2（微调阶段）：几乎总是解冻 LLM

**冻结的理由**：
- LLM 的预训练投入巨大，贸然在噪声较多的图文对数据上训练可能损害语言能力
- Stage 1 的数据量和质量可能不足以支撑 LLM 的有效更新

**解冻的理由**：
- LLM 需要学习如何利用视觉信息来生成更好的回答
- 只训练 projector 的表达力有限，必须让 LLM 参与多模态学习

### 4.3 全参数微调

**何时使用**：
- Stage 2 或 Stage 3：在高质量指令数据上进行全参数训练
- InternVL 2.5、LLaVA-OneVision 等 SOTA 模型在最终阶段都采用全参数微调

**取舍分析**：

| 策略 | 参数量 | 训练速度 | 最终效果 | 适用场景 |
|------|--------|---------|---------|---------|
| 仅训练 projector | <50M | ⚡极快 | 一般 | Stage 1、快速实验 |
| 训练 projector + LLM | ~7B | 中等 | 较好 | Stage 2 标准方案 |
| 全参数（ViT + projector + LLM） | ~13B+ | 较慢 | 最佳 | 最终训练阶段 |
| LoRA 适配 | <100M | 较快 | 接近全参 | 资源受限场景 |

### 4.4 冻结策略的最佳实践

综合各方案经验，推荐的冻结策略路线：

```
Stage 1: freeze(ViT) + freeze(LLM) + train(projector)
         ↓ 使用大规模图文对，学习对齐
Stage 2: freeze(ViT) + train(LLM) + train(projector)
         ↓ 使用指令数据，学习多模态理解
Stage 3: train(ViT) + train(LLM) + train(projector)  [可选]
         ↓ 使用高质量数据，端到端优化
```

---

## 五、分辨率处理策略

分辨率处理是多模态融合中最实际的工程挑战之一。图像分辨率直接影响视觉 token 数量，进而影响计算开销和模型效果。

### 5.1 固定分辨率（传统方式）

**方法**：将所有输入图像 resize 到固定尺寸（如 224×224 或 336×336）。

**问题**：
- 高分辨率图像被强制缩小，丢失细节
- 非正方形图像被拉伸变形
- 对 OCR、小字体识别、文档理解等任务不友好

### 5.2 AnyRes / Tile 策略（LLaVA-NeXT / InternVL）

**核心思想**：将高分辨率图像切分为多个固定大小的 tile（瓦片），每个 tile 单独送入 ViT 编码。同时保留一个全局缩略图（thumbnail），提供整体语义理解。

**LLaVA-NeXT / LLaVA-OneVision 的 AnyRes**：
1. 根据图像长宽比，选择最佳的 tile 网格布局（如 2×1、1×2、2×2 等）
2. 将图像 resize 到网格大小，切分为各 tile（每个 384×384）
3. 生成一个全局缩略图（384×384）
4. 每个 tile 和缩略图分别送入 SigLIP 编码
5. 所有 tile 的视觉 token 拼接后送入 LLM
6. LLaVA-OneVision 支持最多 9 个 tile（anyres_max_9）

**InternVL 1.5 / 2.0 / 2.5 的动态分辨率**：
1. 将图像按 448×448 的 tile 大小进行划分
2. 支持 1-12 个 tile（最高约 4K 分辨率）
3. 同时添加一个 448×448 的全局缩略图
4. 每个 tile 产生 256 个视觉 token（经过 pixel unshuffle 后）
5. 加上缩略图共 (N+1)×256 个 token

### 5.3 原生动态分辨率（Qwen2-VL / Qwen2.5-VL）

**核心创新**：彻底抛弃 tile 划分，让 ViT 直接处理任意分辨率的输入。

**Qwen2-VL 的 Naive Dynamic Resolution**：
1. 输入图像按原始长宽比进行最小化 resize（确保总像素数在限制范围内）
2. ViT 直接编码完整图像（不切分）
3. 使用 Multimodal Rotary Position Embedding（M-RoPE）提供位置信息
4. 视觉 token 数量与输入分辨率成正比

**Qwen2.5-VL 的进一步改进**：
1. 从头训练的原生动态分辨率 ViT
2. 使用 window attention 实现线性计算复杂度（相对于 patch 数量）
3. 支持更高分辨率，计算效率更好

**对比**：

| 策略 | 代表 | 优点 | 缺点 |
|------|------|------|------|
| AnyRes/Tile | LLaVA-OV, InternVL | 可复用现有 ViT，灵活 | tile 边界信息割裂，额外缩略图成本 |
| 原生动态 | Qwen2-VL/2.5-VL | 无信息割裂，端到端更优 | 需重新训练 ViT，实现复杂度高 |

### 5.4 多尺度输入

一些模型同时使用多个尺度的视觉特征来提升效果：

- **多层特征融合**：提取 ViT 不同层的特征，低层特征包含更多空间细节，高层特征包含更多语义信息。CVPR 2025 的研究表明，融合倒数第 2-4 层的特征比仅用最后一层更好。
- **多 encoder 融合**：Eagle 等工作探索了混合多个视觉 encoder 的方案（如 SigLIP + SAM + DINOv2），不同 encoder 擅长不同类型的视觉信息。
- **缩略图 + 高分辨率 tile**：大多数 AnyRes 方案隐含了多尺度——缩略图提供全局语义，高分辨率 tile 提供局部细节。

---

## 六、多模态 Token 设计与压缩

### 6.1 视觉 Token 数量的挑战

一张 1024×1024 的图像，在 ViT-L/14（patch_size=14）下会产生 73×73 = 5329 个 patch。如果直接作为 token 送入 LLM，计算开销将极为巨大（LLM 的注意力机制是 O(n²)）。

**典型的视觉 token 数量**：
| 模型 | 单图 token 数（标准分辨率） | 高分辨率最大 token 数 |
|------|--------------------------|---------------------|
| LLaVA-1.5 | 576 (336×336) | 576 |
| LLaVA-OneVision | 729 (384×384) | ~6500 (9 tiles) |
| InternVL 2.5 | 256 (448×448, pixel unshuffle 后) | ~3328 (12+1 tiles) |
| Qwen2-VL | 动态 | 最多 16384 |

### 6.2 主流压缩方法

**1. Pixel Unshuffle（像素反洗牌）**
- **代表**：InternVL 系列
- **原理**：将空间维度折叠到通道维度，2×2 的 patch 合并为 1 个，token 数减少到 1/4
- **具体做法**：将 (H, W, C) 的特征图 reshape 为 (H/2, W/2, 4C)，然后通过 MLP 降维回 (H/2, W/2, C')
- **效果**：448×448 输入原本 1024 个 token → pixel unshuffle 后 256 个 token

**2. 平均池化（Average Pooling）**
- **代表**：Gemma 3、一些轻量化方案
- **原理**：对相邻 token 进行平均池化，将 2×2 或更大窗口的 token 合并
- **优点**：实现最简单，无需额外参数
- **缺点**：信息丢失较多，不可学习

**3. 卷积下采样**
- **代表**：LDPv2（Low-Dimension Projector v2）
- **原理**：使用卷积层对视觉特征图进行下采样
- **优点**：可学习的压缩，保留重要信息
- **缺点**：引入额外参数和计算

**4. Bilinear Interpolation + Reshape**
- **代表**：LLaVA-OneVision（对 tile 的处理）
- **原理**：对每个 tile 的特征进行双线性插值缩小，然后 reshape
- **效果**：每个 tile 从 729 个 token 压缩到更少数量

**5. 可学习的 Token 选择/合并**
- **代表**：TokenCarve、VisionSelector（2025 年新工作）
- **原理**：根据 token 重要性动态选择保留哪些 token，或将相似 token 合并
- **优点**：自适应压缩，对不同图像内容区别对待
- **缺点**：需要额外训练信号

### 6.3 Token 数量的经验法则

基于各 SOTA 方案的实践，视觉 token 数量的选择有以下经验：

- **标准分辨率（~384-448px）**：256-729 个 token 是合理范围
- **高分辨率场景**：总 token 数控制在 2000-4000 个以内，性能/效率最佳
- **超过 4000 个视觉 token**：边际收益迅速递减，且推理成本急剧上升
- **视频场景**：通常每帧 100-256 个 token，多帧共享视觉 encoder

---

## 七、SOTA 方案深度对比

### 7.1 InternVL 2.5（OpenGVLab，2024.12）

**架构设计**：
- 视觉 encoder：InternViT-6B（基于 ViT-6B 增量预训练）或 InternViT-300M
- 连接器：2 层 MLP projector（随机初始化）
- LLM：InternLM 2.5 / Qwen 2.5（多种规模：1B-78B）
- 范式：ViT-MLP-LLM

**融合策略**：
- Pixel unshuffle 将 token 压缩到 1/4
- 动态分辨率 tile 划分（448×448 为单位，1-12 tiles + 缩略图）
- 全参数端到端训练

**特色**：
- 视觉 encoder 投入最大（InternViT-6B 是目前最大的开源视觉 encoder）
- 注重数据质量：大量人工标注 + 自动化质量过滤
- 模型规模覆盖广（1B-78B），适用于不同场景

**训练策略总结**：
```
InternViT 增量预训练 → MLP 对齐 → 端到端微调 → 测试时缩放（CoT、best-of-N）
```

### 7.2 Qwen2-VL / Qwen2.5-VL（阿里通义，2024.9 / 2025.1）

**架构设计**：
- 视觉 encoder：ViT-600M（Qwen2-VL）/ 原生动态分辨率 ViT（Qwen2.5-VL，从头训练）
- 连接器：2 层 MLP
- LLM：Qwen2 / Qwen2.5（2B-72B）
- 范式：ViT-MLP-LLM

**融合策略（关键创新）**：
- **Naive Dynamic Resolution**：不做 tile 划分，ViT 直接处理任意分辨率输入
- **M-RoPE（Multimodal Rotary Position Embedding）**：为视觉 token 提供 2D 位置编码，与 LLM 的 1D RoPE 统一
- **Window Attention**（Qwen2.5-VL）：ViT 内部使用窗口注意力实现线性计算复杂度
- 视觉 token 数量与输入面积成正比（约每 28×28 像素 1 个 token）

**特色**：
- 最激进的分辨率处理方案——完全取消了 tile 机制
- 视频理解能力强（支持长视频，动态时间分辨率）
- M-RoPE 统一了 1D（文本）和 2D（图像）以及 3D（视频）的位置编码

**训练策略总结**：
```
ViT 从头训练（Qwen2.5-VL） → 多模态预训练 → 指令微调
```

### 7.3 LLaVA-OneVision（Evolving LMMs Lab，2024.8）

**架构设计**：
- 视觉 encoder：SigLIP-SO400M
- 连接器：2 层 MLP（mlp2x_gelu）
- LLM：Qwen2（0.5B-72B）
- 范式：ViT-MLP-LLM

**融合策略**：
- **AnyRes 策略**：图像切分为最多 9 个 tile（anyres_max_9），每个 384×384
- **跨场景 token 预算均衡**：设计单图、多图、视频三种场景的最大 token 数相近（约 6500-7200），确保训练时不同场景之间的能力迁移
- 课程学习：先单图 → 再多图 → 最后视频
- 使用 bilinear interpolation 对 tile 特征进行压缩

**特色**：
- 最注重"开源可复现"和数据方案透明度
- 跨场景迁移设计是独特亮点——单图训练的能力可以零样本迁移到视频
- 训练数据总量最大（3.2M 单图 + 0.56M 多图 + 0.35M 视频）

**训练策略总结**：
```
Stage 1: LI 对齐 → Stage 1.5: 高质量知识学习 → Stage 2: 单图指令微调 → Stage 2续: 混合 one-vision 微调
```

### 7.4 三大方案对比总结

| 维度 | InternVL 2.5 | Qwen2.5-VL | LLaVA-OneVision |
|------|-------------|------------|-----------------|
| 视觉 encoder | InternViT-6B（最大） | 原生动态 ViT（最创新） | SigLIP-SO400M（最通用） |
| 连接器 | 2 层 MLP | 2 层 MLP | 2 层 MLP |
| 分辨率策略 | 448px tile × 12 | 原生动态分辨率 | AnyRes tile × 9 |
| Token 压缩 | pixel unshuffle (1/4) | 按面积比例 | bilinear interpolation |
| 位置编码 | 标准 ViT PE | M-RoPE（2D/3D） | 标准 + AnyRes 拼接 |
| 训练策略 | ViT 增量预训 + 对齐 + 端到端 | ViT 从头训 + 预训 + 指令微调 | 3 阶段课程学习 |
| 最大模型 | 78B | 72B | 72B |
| 开源程度 | 权重+部分数据 | 权重+部分数据 | 权重+数据+完整流程 |

---

## 八、实践建议：从零开始的推荐方案

基于对 SOTA 方案的全面分析，如果从零开始构建多模态模型，推荐以下方案：

### 8.1 推荐架构

```
SigLIP-SO400M → 2层 MLP (GELU) → Qwen2.5 / LLaMA 3.x
```

**选择理由**：
- **SigLIP-SO400M**：参数量适中（400M），视觉表示质量优秀，支持 384×384 原生分辨率，社区生态完善
- **2 层 MLP**：简单、有效、已被充分验证。无需 Q-Former 或交叉注意力
- **Qwen2.5 / LLaMA 3.x**：当前最强开源 LLM，中英文能力均衡

### 8.2 推荐训练流程

**第一步：对齐预训练（1-2 天，8×A100/H100）**
```
数据：LCS-558K 或 ShareGPT4V-PT（图文对）
冻结：ViT ✅  LLM ✅  Projector ❌
学习率：1e-3
Epoch：1
```

**第二步：指令微调（3-5 天，8×A100/H100）**
```
数据：665K-1M 多模态指令数据（LLaVA-665K + 额外 OCR/文档数据）
冻结：ViT ✅  LLM ❌  Projector ❌
学习率：2e-5
Epoch：1
```

**第三步（可选）：全参数优化（5-7 天，8×A100/H100）**
```
数据：扩展到 2-3M 高质量混合数据
冻结：ViT ❌  LLM ❌  Projector ❌
学习率：1e-5（ViT）/ 2e-5（LLM）
Epoch：1
```

### 8.3 分辨率策略建议

- **入门阶段**：先用 384×384 固定分辨率跑通全流程
- **进阶阶段**：引入 AnyRes tile 策略（最多 4-6 tiles），复用 SigLIP 的 384×384 编码
- **高级阶段**：如果需要极致性能，考虑训练原生动态分辨率 ViT（参考 Qwen2.5-VL）

### 8.4 Token 预算建议

- 标准分辨率：576-729 tokens/image（直接使用 SigLIP 输出）
- 高分辨率：引入 pixel unshuffle 或 bilinear interpolation，将每个 tile 压缩到 ~144-256 tokens
- 总预算：单张图片不超过 2048 tokens，视频每帧不超过 256 tokens

### 8.5 常见陷阱

1. **不要在 Stage 1 就解冻 LLM**：噪声较多的图文对数据会损害 LLM 的语言能力
2. **不要忽视数据质量**：1M 高质量数据 > 10M 低质量数据，在后期阶段尤其如此
3. **不要使用过高分辨率**：除非有明确的下游需求（如文档 OCR），否则 768×768 以内已足够
4. **不要忘记缩略图**：使用 tile 策略时，全局缩略图对语义理解至关重要
5. **注意学习率差异**：ViT 的学习率通常应设置为 LLM 的 1/2 到 1/10

---

## 九、总结与展望

### 9.1 核心结论

1. **连接方式**：MLP 投影已成为事实标准，Q-Former 和交叉注意力逐渐边缘化
2. **训练阶段**：经典两阶段（对齐 + 微调）是最低要求，三阶段训练效果更好
3. **冻结策略**：渐进式解冻（先 projector → 再 LLM → 最后 ViT）是最佳实践
4. **分辨率**：AnyRes/tile 是当前主流，原生动态分辨率是未来方向
5. **Token 效率**：pixel unshuffle 是性价比最高的压缩方案

### 9.2 未来趋势

- **统一视觉-语言架构**：如 Fuyu、Chameleon 等探索完全不需要独立视觉 encoder 的方案，直接用 LLM 处理 raw pixels
- **更高效的 Token 压缩**：基于内容自适应的动态压缩将成为标配
- **原生多模态预训练**：不再分为 ViT 预训练 → LLM 预训练 → 多模态对齐，而是从一开始就联合训练
- **超越视觉**：音频、3D、触觉等模态的融合将复用视觉融合的经验

---

## 参考文献

1. Liu et al., "Visual Instruction Tuning" (LLaVA), NeurIPS 2023
2. Liu et al., "Improved Baselines with Visual Instruction Tuning" (LLaVA-1.5), CVPR 2024
3. Li et al., "LLaVA-OneVision: Easy Visual Task Transfer", arXiv 2408.03326, 2024
4. Li et al., "BLIP-2: Bootstrapping Language-Image Pre-training with Frozen Image Encoders and Large Language Models", ICML 2023
5. Alayrac et al., "Flamingo: a Visual Language Model for Few-Shot Learning", NeurIPS 2022
6. Chen et al., "InternVL: Scaling up Vision Foundation Models and Aligning for Generic Visual-Linguistic Tasks", CVPR 2024
7. Chen et al., "Expanding Performance Boundaries of Open-Source Multimodal Models" (InternVL 2.5), arXiv 2412.05271, 2024
8. Wang et al., "Qwen2-VL: Enhancing Vision-Language Model's Perception of the World at Any Resolution", arXiv 2409.12191, 2024
9. Qwen Team, "Qwen2.5-VL Technical Report", arXiv 2502.13923, 2025
10. Wang et al., "CogVLM: Visual Expert for Pretrained Language Models", arXiv 2024
11. Lin et al., "Multi-Layer Visual Feature Fusion in Multimodal LLMs", CVPR 2025
12. Li et al., "LaCo: Efficient Layer-wise Compression of Visual Tokens for Multimodal LLMs", arXiv 2507.02279, 2025
