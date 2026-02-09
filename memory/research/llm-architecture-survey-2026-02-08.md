# LLM 架构综述：Transformer 变体、Mamba/SSM、MoE 及当前 SOTA 选型建议

> 研究日期：2026-02-08
> 任务来源：backlog P1 - 从零训练 LLM + 视觉模型 #1

---

## 一、总览：2024-2025 LLM 架构演进脉络

LLM 架构自 2017 年的 "Attention is All You Need" 以来，核心框架（Decoder-only Transformer）本质上没有剧变，但**组件级别的优化**已经非常丰富。关键演进路线：

```
GPT-1 (2018) → GPT-2 (2019) → GPT-3 (2020) → Llama (2023) → DeepSeek V3 (2024) → 混合架构 (2025)
```

主要变化维度：
1. **位置编码**：绝对位置编码 → ALiBi → RoPE（当前主流）
2. **注意力机制**：MHA → GQA → MLA（DeepSeek）/ 滑动窗口注意力（Gemma）
3. **激活函数**：GELU → SwiGLU（当前主流）
4. **归一化**：LayerNorm → RMSNorm，位置从 Pre-Norm 到 Pre+Post 双重归一化
5. **稀疏化**：Dense → MoE（当前前沿趋势）
6. **替代架构**：SSM/Mamba → 混合 Transformer-Mamba 架构

---

## 二、Transformer 变体详解

### 2.1 标准 Decoder-only Transformer（GPT 系列基线）

**核心组件：**
- Token Embedding + 位置编码
- N × Transformer Block（Self-Attention + FFN + 残差连接 + 归一化）
- 输出头（线性投影 + Softmax）

**当前主流配置（"Modern LLM Recipe"）：**

| 组件 | 主流选择 | 代表模型 |
|------|---------|---------|
| 位置编码 | RoPE | Llama 3/4, Qwen 2/3, Mistral, Gemma, DeepSeek |
| 注意力 | GQA | Llama 3/4, Qwen 2/3, Mistral, Gemma 3 |
| 激活函数 | SwiGLU | 几乎所有现代 LLM |
| 归一化 | RMSNorm (Pre-Norm) | Llama 3, Qwen 2, Mistral |
| FFN 结构 | GLU variant | 标准配置 |

### 2.2 注意力机制变体

#### Multi-Head Attention (MHA)
- 每个 head 有独立的 Q、K、V 投影
- KV Cache 大小 = num_heads × head_dim × 2 × seq_len
- 内存开销最大，但表达能力最强
- **仍在使用**：OLMo 2（7B）

#### Grouped-Query Attention (GQA)
- 多个 Query head 共享同一组 K/V
- 典型配比：32 个 Query head，8 个 KV group
- KV Cache 减少约 4×（取决于 group 数）
- 建模性能接近 MHA，推理效率显著提升
- **当前最主流选择**：Llama 3/4, Qwen 2/3, Mistral, Gemma 2/3

#### Multi-Head Latent Attention (MLA) — DeepSeek 独创
- 不减少 KV head 数量，而是将 KV 压缩到低维潜空间再缓存
- 推理时从压缩表示恢复到原始维度
- 根据 DeepSeek-V2 的消融实验：**MLA 性能 > MHA > GQA**
- KV Cache 压缩率取决于潜空间维度（通常压缩 4-8×）
- **使用模型**：DeepSeek V2/V3/R1, Kimi K2

#### 滑动窗口注意力 (Sliding Window Attention)
- 限制每个 token 只关注固定窗口内的邻居
- Gemma 3 的激进设计：5:1 的局部:全局注意力比例，窗口仅 1024 tokens
- 大幅降低 KV Cache 内存
- **使用模型**：Gemma 2/3, Mistral（早期版本）

### 2.3 归一化层的演进

| 策略 | 描述 | 代表 |
|------|------|------|
| Pre-Norm (Pre-LN) | Norm 放在 Attn/FFN 之前 | GPT-2, Llama 3, Qwen 2 |
| Post-Norm (变体) | Norm 放在 Attn/FFN 之后，但在残差内部 | OLMo 2 |
| Pre+Post 双归一化 | 两侧都加 Norm | Gemma 3 |
| QK-Norm | 在注意力内部对 Q、K 做 RMSNorm（RoPE 之前） | OLMo 2, Gemma 2/3, Qwen 3 |

**关键发现**：Post-Norm（OLMo 2 变体）+ QK-Norm 组合可以显著提升训练稳定性，减少 loss spike。

### 2.4 主流开源模型架构横向对比

| 模型 | 参数量 | 注意力 | 位置编码 | 激活 | 归一化 | MoE | 特色 |
|------|--------|--------|---------|------|--------|-----|------|
| **Llama 3.1** | 8B/70B/405B | GQA | RoPE | SwiGLU | RMSNorm Pre | ❌ | 标准配置，广泛使用 |
| **Llama 4 Maverick** | 400B (17B active) | GQA | RoPE | SwiGLU | RMSNorm | ✅ 128专家 | 交替 MoE 和 Dense 层 |
| **Qwen 2.5** | 0.5B-72B | GQA | RoPE | SwiGLU | RMSNorm Pre | ❌/✅ | 多语言，A14B MoE 变体 |
| **Qwen 3** | 0.6B-235B | GQA | RoPE | SwiGLU | RMSNorm | ✅ (30B-A3B) | QK-Norm，思考模式 |
| **DeepSeek V3** | 671B (37B active) | **MLA** | RoPE | SwiGLU | RMSNorm | ✅ 256专家+1共享 | MLA+细粒度MoE |
| **Gemma 3** | 1B-27B | GQA | RoPE | GeGLU | RMSNorm Pre+Post | ❌ | 滑动窗口 5:1 |
| **Mistral 3** | 24B | GQA | RoPE | SwiGLU | RMSNorm | ❌ | 简洁高效 |
| **OLMo 2** | 7B/13B/32B | MHA→GQA | RoPE | SwiGLU | RMSNorm Post | ❌ | 完全开源 |

---

## 三、Mamba / SSM 架构

### 3.1 SSM 基础原理

State Space Models 源自控制理论，核心方程：
```
h'(t) = A·h(t) + B·x(t)    # 状态更新
y(t) = C·h(t) + D·x(t)      # 输出
```

离散化后可以用循环（O(n)）或卷积（并行训练）方式计算。

**SSM 演进路线**：S4 (2021) → S5 → H3 → Mamba/S6 (2023) → Mamba-2 (2024)

### 3.2 Mamba (S6) 的核心创新

**论文**：Gu & Dao, Dec 2023 — "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"

关键突破：
1. **选择性机制 (Selective Mechanism)**：让 B、C、Δ 参数**依赖于输入**，实现内容感知的信息过滤
2. **硬件感知并行算法**：通过 CUDA kernel 优化实现高效并行扫描
3. **线性时间复杂度**：O(n) vs Transformer 的 O(n²)
4. **恒定内存推理**：不需要 KV Cache，生成时内存不随序列增长

**性能数据**：
- Mamba-3B 在语言建模上**超越同等规模 Transformer，匹配 2× 大小的 Transformer**
- 推理吞吐量最高**提升 5×**
- 理论上支持百万级 token 序列

### 3.3 Mamba-2

**论文**：Dao & Gu, May 2024

改进：
- 建立了 SSM 和注意力机制之间的数学联系
- 新的 SSD（State Space Duality）框架
- 速度显著提升（2-8× faster than Mamba-1）
- 更适合与 Transformer 组件混合

### 3.4 SSM 的局限性

1. **In-Context Learning 较弱**：固定大小的状态向量限制了"记住"任意上下文的能力
2. **长序列精确回忆困难**：不擅长 copy/retrieval 类任务
3. **Induction Heads 缺失**：Transformer 通过注意力模式学到的 induction heads 在 SSM 中难以复现
4. **生态不成熟**：缺乏 FlashAttention 级别的优化工具链
5. **规模验证不足**：截至 2025，最大纯 Mamba 模型约 7B（Falcon Mamba），70B+ 级别尚未充分验证

### 3.5 重要的纯 Mamba / SSM 模型

| 模型 | 规模 | 基于 | 关键结果 |
|------|------|------|---------|
| Mamba (原版) | 130M-2.8B | Mamba-1 | 匹配 2× Transformer |
| Falcon Mamba | 7.27B | Mamba-1 | 超越 Llama 3.1-8B, Mistral 7B |
| Codestral Mamba | 7.3B | Mamba-2 | 代码专用，256K 上下文 |

---

## 四、混合架构（Transformer + Mamba / SSM）

### 4.1 为什么要混合？

- 纯 Mamba 在效率上有优势，但在需要精确回忆的任务上不如 Transformer
- 少量注意力层可以弥补 SSM 在 recall 上的不足
- 理想组合：用 Mamba 处理大部分序列（高效），用 Attention 做精确检索

### 4.2 代表性混合模型

#### Jamba (AI21, Mar 2024)
- **首个大规模** Transformer-Mamba-MoE 混合模型
- Attention:Mamba = **1:7** 比例
- MoE 每两个 block 加一层
- 支持 256K 上下文
- Apache 2.0 开源

#### Jamba 1.5 (AI21, Aug 2024)
- 398B 总参数，94B 激活
- 72 层，交替 Mamba 和注意力
- GQA + MoE (16 专家)
- NVIDIA RULER 长上下文基准 SOTA

#### Nemotron-H (NVIDIA, Apr 2025)
- 8B/47B/56B 系列
- **92% Mamba-2 层 + 8% Attention 层**
- 推理吞吐量 **3× faster** 于同等 Llama/Qwen
- MMLU、GSM8K、HumanEval 性能匹配或超越纯 Transformer
- FP8 训练 + MiniPuzzle 蒸馏压缩

#### Bamba (IBM, Apr 2025)
- 9B 参数，Mamba-2 + Transformer 混合
- **2× 吞吐量**于同级 Transformer
- 仅用 Llama 3.1-8B **1/7 数据**即达同等性能
- 支持 vLLM 推理框架

#### Hunyuan TurboS (Tencent, May 2025)
- 560B 总参数，56B 激活
- Attention-Mamba-FFN 交错模式，128 层
- MoE 32 专家 (2+1 active)
- 16T tokens 预训练，256K 上下文
- 链式思维融合（动态选择长短推理策略）

#### Phi-4-mini-flash (Microsoft, Jul 2025)
- 3.8B 参数，面向边缘设备
- **SambaY 架构**：Mamba + 滑动窗口注意力 + GMU
- 线性 prefill 复杂度
- **10× 吞吐量，2-3× 低延迟**
- 64K 上下文

#### Mamba-Llama (Together AI, Aug 2024)
- 将 Llama 3-8B-Instruct 的 75% 注意力层替换为 Mamba
- 推理延迟降低 **5×**
- 通过权重映射 + 迭代蒸馏保留 chat 性能
- 证明 Transformer→Mamba 转换可行

### 4.3 混合架构的关键洞察

1. **少量注意力就够了**：Nemotron-H 只需 8% 注意力层就能匹配纯 Transformer 性能
2. **Mamba-2 优于 Mamba-1**：在混合模型中，底层 SSM 架构的选择对最终性能影响很大
3. **MoE + Mamba 是强组合**：MoE-Mamba 可以用 2.2× 更少的训练步骤达到 Mamba 相同性能
4. **蒸馏是可行路径**：可以从纯 Transformer 蒸馏到混合架构

---

## 五、Mixture of Experts (MoE) 深度分析

### 5.1 MoE 核心机制

```
# 每层的前向传播
router_logits = Router(x)                    # 计算每个 expert 的分数
top_k_experts = TopK(router_logits, k)       # 选择 top-k 个专家
output = Σ (gate_i × Expert_i(x))            # 加权求和
```

**关键设计选择**：
- **Expert 数量**：8 (Mixtral) → 64 (Qwen MoE) → 256 (DeepSeek V3)
- **Top-K 选择**：通常 top-2 (Mixtral) 或 top-8+1 (DeepSeek V3)
- **路由方式**：Token-level routing（主流）
- **负载均衡**：Auxiliary loss / Expert parallelism

### 5.2 重要 MoE 模型对比

| 模型 | 总参数 | 激活参数 | Expert数 | Top-K | 共享Expert | 特色 |
|------|--------|---------|---------|-------|-----------|------|
| Mixtral 8×7B | 46.7B | ~12.9B | 8 | 2 | ❌ | 首个主流开源 MoE |
| Mixtral 8×22B | 141B | ~39B | 8 | 2 | ❌ | 扩展版 |
| DeepSeek V2 | 236B | 21B | 160 | 6+1 | ✅ | MLA + 细粒度 MoE |
| DeepSeek V3 | 671B | 37B | 256 | 8+1 | ✅ | MTP 训练目标 |
| Qwen 2.5-MoE | ~14B | ~3B | 64 | 4 | ✅ | 轻量 MoE |
| Qwen 3 30B-A3B | 30B | 3B | - | - | - | 小型 MoE |
| DBRX | 132B | ~36B | 16 | 4 | ❌ | Fused MoE kernels |
| Llama 4 Maverick | 400B | 17B | 128 | - | - | 交替 MoE/Dense |
| Phi-3.5-MoE | 42B | ~6.6B | 16 | 2 | ❌ | 微软出品 |
| Kimi K2 | ~1T | ~32B | - | - | - | AA 排行榜第一开源 |

### 5.3 MoE 的优势与挑战

**优势**：
- 以少量激活参数达到大模型性能（DeepSeek V3 用 37B 激活参数超越 405B Dense Llama 3）
- 训练更高效（给定 FLOP 预算下容量更大）
- 推理时 per-token 计算量可控

**挑战**：
- 总参数量大，**显存需求高**（即使不全部激活，所有参数都需加载）
- Expert 并行带来的**通信开销**
- **负载不均**问题（部分 expert 过热/过冷）
- 部署更复杂，需要专门的推理引擎支持
- 小批量推理时效率优势不明显

### 5.4 DeepSeek 的 MoE 创新

DeepSeek 在 MoE 上有多项独特设计：
1. **细粒度专家 (Fine-grained Experts)**：将标准 FFN 拆分成更多、更小的专家，提高专家专业化程度
2. **共享专家 (Shared Experts)**：1 个永远激活的专家学习通用知识，减少其他专家的知识冗余
3. **Multi-Token Prediction (MTP)**：V3 采用多 token 预测训练目标，进一步提升效率
4. **低成本训练**：V3 的 671B 模型仅花费约 500 万美元计算成本

---

## 六、其他值得关注的架构创新

### 6.1 新兴线性注意力变体
- **Gated DeltaNet**：结合线性注意力和门控机制
- **RWKV**：RNN-Transformer 混合，线性复杂度
- **RetNet**：保留网络，支持并行训练+循环推理

### 6.2 长上下文技术
- **RoPE 外推**：通过调整 base frequency 扩展上下文（YaRN, NTK-aware 等）
- **Sparse Attention**：Native sparse attention in DeepSeek V3.1
- **Ring Attention**：分布式长序列注意力计算

### 6.3 Multi-Token Prediction (MTP)
- DeepSeek V3 采用的训练方法
- 同时预测多个未来 token，加速训练收敛
- 可在推理时用于推测解码 (Speculative Decoding)

---

## 七、选型建议：从零训练 LLM 该选什么架构？

### 7.1 按模型规模推荐

#### 小规模 (1B-3B)
- **推荐**：标准 Transformer + GQA + RoPE + SwiGLU + RMSNorm
- **理由**：架构成熟、工具链完善、训练稳定
- **参考**：Llama 3.2-1B/3B, Qwen 2.5-1.5B, Gemma 2-2B

#### 中规模 (7B-13B)
- **推荐方案 A**：Dense Transformer (GQA + RoPE + SwiGLU)
- **推荐方案 B**：Mamba-Transformer 混合（如果目标是高效推理）
- **理由**：Dense 方案成熟可靠；混合方案在推理效率上有 2-3× 优势
- **参考**：Llama 3.1-8B（Dense）, Bamba-9B / Nemotron-H-8B（混合）

#### 大规模 (30B-70B+)
- **推荐**：MoE Transformer 或 MoE + Mamba 混合
- **理由**：MoE 在这个规模的效率优势非常显著；可以 100B+ 总参数但只需 10-20B 激活
- **参考**：DeepSeek V3 架构思路, Jamba 1.5, Hunyuan TurboS

### 7.2 架构选型决策树

```
你的目标是什么？
├── 最大化性能（不太在乎推理成本）
│   ├── 预算 < $10K → Dense Transformer 7B (GQA)
│   ├── 预算 $10K-$100K → Dense Transformer 13B-30B
│   └── 预算 > $100K → MoE Transformer 60B+ 总参
│
├── 最大化推理效率
│   ├── 上下文 < 32K → Mamba-Transformer 混合 (92% Mamba + 8% Attn)
│   ├── 上下文 32K-256K → 滑动窗口注意力 + 少量全局注意力 (Gemma 3 式)
│   └── 上下文 > 256K → 纯 Mamba 或 SSM 混合 + Ring Attention
│
└── 平衡性能和效率
    ├── 小型 (< 10B active) → MoE (参考 Qwen MoE / DeepSeek MoE 轻量版)
    └── 中大型 (> 10B active) → MoE + Mamba 混合 (Jamba / Hunyuan TurboS 路线)
```

### 7.3 实操建议

1. **起步从 Dense Transformer 开始**：技术最成熟、教程最多、调试最容易
2. **推荐 "Llama 3 Recipe"**：GQA + RoPE + SwiGLU + RMSNorm Pre-Norm + QK-Norm
3. **加 QK-Norm**：几乎零成本提升训练稳定性
4. **考虑 Post-Norm 变体**：OLMo 2 的结果表明 Post-Norm 有利于稳定训练
5. **MoE 和 Mamba 作为进阶选项**：先在 Dense 架构上验证数据和流程，再升级架构
6. **关注 MLA**：如果有能力实现，MLA 的性能略优于 GQA（但实现复杂度高）

### 7.4 工具链成熟度

| 架构 | 训练框架支持 | 推理框架支持 | 社区资源 | 成熟度 |
|------|------------|------------|---------|--------|
| Dense Transformer (GQA) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 最成熟 |
| MoE Transformer | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 成熟 |
| Mamba / SSM | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 快速发展中 |
| 混合 (Mamba+Transformer) | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 快速发展中 |
| MLA | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 需自行实现 |

---

## 八、2025-2026 趋势预测

1. **Transformer 仍是主流**，但会越来越多地融入 Mamba/SSM 层（混合成为新默认）
2. **MoE 已成为大模型的标配**，不再是可选项
3. **推理时扩展 (Inference-time scaling)** 将与架构设计深度结合
4. **RLVR + GRPO** 后训练方法比架构选择更影响最终模型质量
5. **Mamba-2 + MoE** 的组合有望成为高效大模型的新范式
6. **边缘设备模型** (Gemma 3n, Phi-4-mini-flash) 推动混合架构在小模型上的应用

---

## 参考资料

1. Vaswani et al., "Attention Is All You Need", 2017
2. Gu & Dao, "Mamba: Linear-Time Sequence Modeling with Selective State Spaces", 2023
3. Dao & Gu, "Transformers are SSMs", 2024 (Mamba-2)
4. DeepSeek-V2: https://arxiv.org/abs/2405.04434
5. DeepSeek-V3: https://arxiv.org/abs/2412.19437
6. DeepSeek R1: https://arxiv.org/abs/2501.12948
7. Jamba: https://arxiv.org/abs/2403.19887
8. Jamba 1.5: https://arxiv.org/abs/2408.12570
9. Nemotron-H: https://arxiv.org/abs/2504.03624
10. Falcon Mamba: https://arxiv.org/abs/2410.05355
11. OLMo 2: https://arxiv.org/abs/2501.00656
12. Sebastian Raschka, "The Big LLM Architecture Comparison", 2025
13. Sebastian Raschka, "The State of LLMs 2025", 2025
14. AI21, "Attention was never enough: Tracing the rise of hybrid LLMs", 2025
15. Mixtral 8×7B: https://arxiv.org/abs/2401.04088
16. Hunyuan TurboS: https://arxiv.org/abs/2505.15431
17. Phi-4-mini-flash: Microsoft Azure Blog, July 2025
