# Scaling Laws 研究：Chinchilla 定律、Compute-Optimal 训练策略与小模型高效训练路线

> 研究日期：2026-02-08
> 系列：从零训练 LLM + 视觉模型 #6

---

## 一、什么是 Scaling Laws？

Scaling Laws（缩放定律）是描述神经网络性能如何随关键因素变化而变化的经验性规律。在大语言模型（LLM）领域，这些因素主要包括三个维度：

- **模型大小 N**：模型的参数量（通常以十亿 B 为单位）
- **数据集大小 D**：训练所用的 token 数量
- **计算预算 C**：训练所消耗的浮点运算次数（FLOPs）

核心发现是：模型的交叉熵损失（cross-entropy loss）与这三个因素之间存在**幂律关系（power-law relationship）**，即 L ∝ x^(-α)，这种关系在多个数量级范围内都成立。

这意味着我们可以通过小规模实验来预测大规模模型的表现，从而在投入巨额计算资源之前做出明智的训练决策。

### 关键公式框架

**基本形式**：损失可以分解为三个不可约部分：

```
L(N, D) = E + A/N^α + B/D^β
```

其中：
- E 是不可约损失（自然语言固有的熵），约 1.69 nats
- A/N^α 是模型容量不足导致的损失
- B/D^β 是数据不足导致的损失
- α ≈ 0.34，β ≈ 0.28（Chinchilla 论文估计值）

**计算预算近似**：对于标准 Transformer，训练一个 N 参数模型处理 D 个 token 的总 FLOPs 约为：

```
C ≈ 6ND
```

其中系数 6 来自前向传播（2ND）+ 反向传播（4ND）的估算。

---

## 二、Kaplan Scaling Laws（2020）——OpenAI 的开创性工作

### 2.1 研究背景

2020 年 1 月，Jared Kaplan 等人（OpenAI）发表了里程碑式的论文《Scaling Laws for Neural Language Models》，首次系统性地研究了 LLM 中的缩放规律。他们训练了参数量从 768K 到 1.5B 不等的模型，使用 22M 到 23B token 的数据集。

### 2.2 核心发现

Kaplan 等人发现三条独立的幂律关系：

```
L(C) = (3.1×10^8 / C)^0.05    （计算-损失关系）
L(D) = (5.4×10^13 / D)^0.095   （数据-损失关系）
L(N) = (8.8×10^13 / N)^0.076   （参数-损失关系）
```

### 2.3 关键结论

**"大模型优先"策略**：Kaplan 的核心建议是，当计算预算增加 10 倍时，应将模型大小增加 5.5 倍，数据仅增加 1.8 倍。用数学表达：

```
N ∝ C^0.73,  D ∝ C^0.27
```

这意味着模型大小应比数据增长得更快。GPT-3（175B 参数，仅 300B token，约 1.7 token/参数）正是按照这一策略设计的。

### 2.4 局限性

事后来看，Kaplan 的研究有几个重要局限：
1. **模型规模太小**：最大仅 1.5B 参数，在更大规模上规律可能不同
2. **未计入 embedding 参数**：在小模型中 embedding 占比较大，导致估计偏差
3. **学习率调度不佳**：warmup 过长影响了小模型的效率表现
4. **未考虑不可约损失 E**：忽略了自然语言的固有熵底线

---

## 三、Chinchilla Scaling Laws（2022）——DeepMind 的范式转变

### 3.1 研究背景

2022 年 3 月，Jordan Hoffmann 等人（DeepMind）发表《Training Compute-Optimal Large Language Models》，彻底改变了业界对模型训练资源分配的认知。他们训练了超过 400 个模型，参数量从 70M 到 16B 不等。

### 3.2 三种估计方法

**方法 1：固定模型大小，变化训练 token 数**
- 对不同大小的模型，变化训练数据量，测量各 FLOP 预算下的最优配置
- 结论：N ∝ C^0.50, D ∝ C^0.50

**方法 2：IsoFLOP 分析**
- 固定 FLOP 预算，变化模型大小
- 结论：N ∝ C^0.49, D ∝ C^0.51

**方法 3：参数化损失函数拟合**
- 拟合完整的 L(N,D) = E + A/N^α + B/D^β
- 结论：N ∝ C^0.46, D ∝ C^0.54

三种方法高度一致，得出核心结论：**模型大小和数据量应等比例增长**。

### 3.3 核心定律：20:1 法则

Chinchilla 定律的最著名结论是：**每个参数应对应约 20 个训练 token**。

具体对应关系：

| 模型参数量 | Chinchilla 最优 token 数 | 所需 FLOPs |
|-----------|------------------------|-----------|
| 400M | 8.0B | 1.92×10^19 |
| 1B | 20.2B | 1.21×10^20 |
| 10B | 205.1B | 1.23×10^22 |
| 67B | 1.5T | 5.76×10^23 |
| 175B | 3.7T | 3.85×10^24 |
| 1T | 21.2T | 1.27×10^26 |

### 3.4 验证：Chinchilla vs Gopher

DeepMind 训练了 Chinchilla（70B 参数，1.4T token）来验证理论。对比此前的 Gopher（280B 参数，300B token），Chinchilla 不仅表现更好，而且模型更小（推理更便宜）。这证明 Gopher 严重"过大而欠训练"。

同样，GPT-3（175B 参数，300B token）按 Chinchilla 标准也是严重欠训练的——它本应训练约 3.5T token，或者应该只用约 15B 参数。

### 3.5 Kaplan vs Chinchilla 的差异原因

Pearce 和 Song（2024）系统分析了两个定律的差异来源：
1. Kaplan 未计入 embedding 参数，在小模型中造成显著偏差
2. Kaplan 使用更小的模型范围
3. Kaplan 未包含不可约损失项 E
4. Kaplan 的学习率调度对小模型不利

修正这些差异后，两组结果可以很好地统一。

---

## 四、超越 Chinchilla：过训练与推理优化

### 4.1 "Chinchilla 陷阱"

严格遵循 Chinchilla 定律会导致一个实际问题：为了达到某个性能水平，你最终会得到一个**非常大的模型**。这就是所谓的"Chinchilla 陷阱"——训练是 compute-optimal 的，但推理（inference）成本极高。

然而在生产环境中，推理的总计算量往往远超训练。一个模型训练一次，但会被推理千百万次。因此，**整体成本最优（total compute-optimal）** 的策略与 Chinchilla 的训练成本最优策略不同。

### 4.2 过训练（Overtraining）策略

LLaMA 系列是过训练策略的典范：

| 模型 | 参数量 | 训练 token | Token/参数比 | 相对 Chinchilla |
|------|-------|-----------|-------------|----------------|
| LLaMA 1 (7B) | 7B | 1T | 142:1 | 7.1× |
| LLaMA 2 (7B) | 7B | 2T | 284:1 | 14.2× |
| LLaMA 3 (8B) | 8B | 15T | 1,875:1 | 93.8× |
| Qwen 2.5 | 多种 | ~18T | — | — |

关键发现：即使远超 Chinchilla 最优点，损失仍然持续下降（虽然收益递减）。Sardana 等人（MosaicML, 2023）的实验将 token/参数比推至 10,000:1，仍观察到损失持续降低。

### 4.3 推理感知的 Scaling Laws

Sardana 等人提出了考虑推理成本的优化目标：

```
minimize: 6N·D_train + 2N·D_inference
subject to: L(N, D_train) = ℓ（固定目标损失）
```

其中 6N 是每 token 训练 FLOPs，2N 是每 token 推理 FLOPs。

核心发现：
- 如果预期推理需求为 10^12 FLOPs，compute-optimal 模型的参数量仅为 Chinchilla 模型的 33%
- compute-optimal 模型的 token/参数比是 Chinchilla 模型的 5 倍
- 总成本（训练+推理）仅为 Chinchilla 策略的 50%

### 4.4 过训练区间的修正系数

在过训练区间（token/参数 >> 20:1），Sardana 等人重新估计了缩放指数：

```
N ∝ C^0.57,  D ∝ C^0.43
```

这表明在过训练区间，损失降低的速率比 Chinchilla 预测的略慢。但这不改变核心结论：对于有大量推理需求的场景，过训练是值得的。

---

## 五、推理时缩放（Test-Time Compute Scaling）

### 5.1 新范式的崛起

2024-2025 年，一个全新的缩放维度浮现：**推理时计算（test-time compute）**。不再仅仅是"训练时投入更多"，而是"推理时给模型更多思考时间"。

代表性工作：
- **OpenAI o1/o3**（2024）：通过生成长链推理（chain-of-thought）提升表现
- **Google Gemini 2.0 Flash Thinking**（2024）：类似的推理时思考机制
- **DeepSeek-R1**（2025）：开源推理模型
- **s1: Simple test-time scaling**（Muennighoff et al., 2025）

### 5.2 推理缩放的方式

推理时计算的两种主要策略：

**并行缩放（Parallel Scaling）**：
- 生成多个候选答案，通过投票或验证器选择最佳
- 例如 Best-of-N 采样、多数投票
- 计算量线性增长，但收益递减

**顺序缩放（Sequential Scaling）**：
- 让模型迭代思考、修正、深化推理
- 链式推理（Chain-of-Thought）
- 自我修正（Self-Revision）
- 计算量与推理深度成正比

### 5.3 惊人的效果

以 ARC 基准为例：
- o3 low：每问题约 330K token，1.3 分钟运行时间
- o3 high：每问题约 57M token，13.8 分钟运行时间（172× 计算量）
- 性能从 o3-low 到 o3-high 有显著跳升

### 5.4 训练与推理计算的权衡

Jones（2021）提出了训练-推理计算权衡的理论框架：在某些情况下，用 15 倍的推理时计算可以替代 10 倍的训练计算。当训练计算非常昂贵而推理计算相对便宜时，这种权衡是有利的。

这为小模型 + 更多推理时计算的路线提供了理论支持。

---

## 六、小模型高效训练路线

### 6.1 当前最佳实践总结

综合 Chinchilla 定律和后续研究，2025-2026 年训练小模型的推荐策略：

**1B 参数模型**：
- Chinchilla 最优：20B token
- 推荐实际训练：200B-1T token（10-50× 过训练）
- 期望与 2-3B Chinchilla 模型性能相当
- 训练成本：约 1.2×10^21 - 6×10^21 FLOPs

**3B 参数模型**：
- Chinchilla 最优：60B token
- 推荐实际训练：500B-3T token
- 期望与 7-10B Chinchilla 模型性能相当
- 训练成本：约 9×10^21 - 5.4×10^22 FLOPs

**7B 参数模型**：
- Chinchilla 最优：140B token
- 推荐实际训练：2T-15T token（参考 LLaMA 3）
- 期望与 13-30B Chinchilla 模型性能相当
- 训练成本：约 8.4×10^22 - 6.3×10^23 FLOPs

### 6.2 数据质量的杠杆效应

数据质量可以改变缩放定律的指数。关键发现：
- **数据过滤**可以使缩放指数变大，意味着同样计算量下获得更好性能
- **Phi 系列模型**（Microsoft）使用教科书质量的合成数据，在极小参数量下达到惊人性能
- **数据去重和清洗**在过训练区间尤其重要（多轮训练相同数据时）

### 6.3 多 epoch 训练的注意事项

当数据量有限而需要过训练时，可能需要多 epoch 训练：
- 1-4 个 epoch 通常影响不大
- 超过 4 epoch 性能可能开始退化
- 使用数据混洗和 curriculum learning 可以缓解多 epoch 的负面影响
- 对于稀缺语言（如少数民族语言），多 epoch + 去噪目标是有效策略

### 6.4 Scaling Laws 驱动的实验设计

实际应用中，Scaling Laws 最重要的用途是**用小规模实验预测大规模结果**：

1. 训练 3-5 个小模型（如 50M, 100M, 200M, 500M 参数）
2. 每个模型训练多个 token 数配置
3. 拟合 L(N, D) = E + A/N^α + B/D^β 的参数
4. 外推预测目标规模模型的表现
5. 基于预测做出训练决策（模型大小、数据量、是否值得投入）

这种方法可以节省 90%+ 的计算成本，避免"盲目训练大模型"的巨大浪费。

---

## 七、前沿进展与展望（2024-2026）

### 7.1 数据瓶颈

EpochAI 估计索引 web 上约有 510T token 的数据，但大部分是低质量或重复的。已知最大数据集约 18T token（Qwen 2.5）。高质量数据正在成为缩放的主要瓶颈。

应对策略：
- 合成数据生成（用大模型生成训练数据）
- 视频/音频转录
- 多语言数据整合
- 专有数据

### 7.2 "缩放墙"争论

2024 年曾有关于"预训练缩放是否撞墙"的热议。但 o3 等推理模型的突破表明，缩放仍有巨大空间——只是缩放的维度从纯粹的预训练扩展到了推理时计算。

行业领袖的看法：
- Dario Amodei（Anthropic）："我已经看到缩放成功太多次了，真的相信缩放会继续。"
- Sam Altman（OpenAI）："没有墙。"

### 7.3 Broken Neural Scaling Laws

2022 年 Caballero 等人提出了"断裂缩放定律"（BNSL），发现某些下游任务的性能并非简单幂律，而是呈现**平滑断裂幂律**形式：

```
L(x) = a · (x + c)^(-α) · [1 + (x/x₀)^(1/w)]^(-β·w) + b
```

这意味着在某些尺度点上，性能提升的速率会突然改变（可能加速或减速），解释了为什么某些"涌现能力"似乎在特定模型大小突然出现。

### 7.4 数据混合的缩放定律

最新研究（2025）发现，数据混合比例（不同领域数据的配比）也遵循缩放定律。可以在小规模实验中找到最优数据配比，然后将其推广到大规模训练，准确预测不同配比下的模型表现。

---

## 八、实践建议

### 8.1 对于个人/小团队从零训练

1. **先做 Scaling Law 实验**：花 5-10% 的预算训练多个小模型，拟合缩放定律参数
2. **选择过训练策略**：如果推理需求大，选择小模型+大量数据
3. **投资数据质量**：好的数据清洗比更多计算更有价值
4. **使用 token/参数比 100-500:1**：在 Chinchilla 和极端过训练之间的甜蜜点
5. **监控训练损失曲线**：如果损失下降明显变缓，可以考虑停止
6. **保留 checkpoint**：不同过训练程度的模型可能适合不同用途

### 8.2 推荐的起步方案

对于学习和实验目的：
- 从 **125M-350M 参数**模型开始，训练 10B-50B token
- 验证 Scaling Laws 在你的数据上是否成立
- 然后决定是否扩展到 1B-7B 参数

对于生产级小模型：
- **1-3B 参数 + 500B-2T token** 是当前最佳性价比区间
- 配合推理时缩放技术（如 chain-of-thought）可以弥补模型大小的不足

---

## 参考来源

1. Kaplan, J. et al. (2020). "Scaling Laws for Neural Language Models." arXiv:2001.08361
2. Hoffmann, J. et al. (2022). "Training Compute-Optimal Large Language Models." arXiv:2203.15556（Chinchilla 论文）
3. Sardana, N. et al. (2023). "Beyond Chinchilla-Optimal: Accounting for Inference in Language Model Scaling Laws." arXiv:2401.00448
4. Pearce, T. & Song, J. (2024). "Reconciling Kaplan and Chinchilla Scaling Laws." arXiv:2406.12907
5. Touvron, H. et al. (2023). "LLaMA: Open and Efficient Foundation Language Models." arXiv:2302.13971
6. Meta AI (2024). "The Llama 3 Herd of Models." arXiv:2407.21783
7. Snell, C. et al. (2024). "Scaling LLM Test-Time Compute Optimally." arXiv:2408.03314
8. Muennighoff, N. et al. (2025). "s1: Simple test-time scaling." arXiv:2501.19393
9. Caballero, E. et al. (2022). "Broken Neural Scaling Laws." arXiv:2210.14891
10. Gadre, S.Y. et al. (2024). "Language Models Scale Reliably with Over-Training and on Downstream Tasks." arXiv:2403.08540
11. Wikipedia: Neural Scaling Law - https://en.wikipedia.org/wiki/Neural_scaling_law
12. JonVet: A brief history of LLM Scaling Laws - https://www.jonvet.com/blog/llm-scaling-in-2025
