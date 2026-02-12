# Mid-Training Annealing: 高质量子集上的学习率衰减 (LR Cooldown)

**Date:** 2026-02-11
**Task:** Phase 3 - Mid-training (Annealing)
**Goal:** 在高质量子集（STEM + Code）上进行 LR Cooldown，产出 7B Enhanced Base Model
**上游依赖:** Full-Scale Pre-training（预训练基座模型 checkpoint）

---

## 1. 什么是 Mid-Training Annealing？

### 1.1 定义

Mid-training annealing（中间训练退火）是预训练和后训练之间的关键阶段，核心思想是：

> **在预训练的最后阶段，快速衰减学习率的同时，切换到更高质量的数据配比，引导模型收敛到更优的局部最小值。**

这不是简单的学习率衰减——它同时涉及**数据分布的战略性调整**。在 LR 快速下降时引入高质量数据，可以让模型在"最后一英里"获得不成比例的性能提升。

### 1.2 为什么有效

根据最新研究（A Survey on LLM Mid-Training, 2025; OLMo 2, 2024），annealing 有效的理论基础包括：

1. **梯度方差降低**: 低学习率减少梯度噪声，稳定收敛
2. **更优局部最小值**: 快速 LR 衰减 + 高质量数据引导模型进入更好的 loss basin
3. **信息密度提升**: 高质量数据每个 token 的边际效用更高
4. **领域能力注入**: STEM/Code 数据在退火阶段注入比在 SFT 阶段更有效（避免灾难性遗忘）

### 1.3 与相关概念的区别

| 概念 | 数据 | LR | 时机 | 目标 |
|------|------|----|------|------|
| **Pre-training** | 大规模通用 | Warmup + 缓慢衰减 | 训练开始 | 建立基础能力 |
| **Mid-training / Annealing** | 高质量子集 | 快速衰减到 0 | 预训练末尾 | 强化特定能力 |
| **Continued Pre-training** | 领域数据 | 重新设定 | 任意时刻 | 领域适配 |
| **SFT (Supervised Fine-tuning)** | 指令数据 | 很低 | 后训练 | 对齐/遵循指令 |

---

## 2. 业界实践综述

### 2.1 Meta Llama 3 (405B / 70B / 8B)

**方法:**
- 在预训练最后 **40M tokens** 上线性退火 LR 到 0
- 退火阶段调整数据配比，**大幅提升高质量代码和数学数据**
- 同时将上下文长度扩展到 128K

**数据配比（退火阶段）：**
- 通用知识: 50% → 降低
- 数学与推理: 25% → 提升
- 代码: 17% → 提升
- 多语言: 8%

**效果:**
- 8B 模型在 GSM8K 上提升 **24.0%**，MATH 上提升 **6.4%**
- 405B 模型提升可忽略（说明大模型 in-context learning 能力已足够强）

**关键洞察:**
- Llama 3 将退火用于**评估新数据集质量**：将 50% 训练的 8B 模型在 40B tokens 上退火，新数据占 30%，旧数据占 70%，观察 benchmark 变化
- 这种"annealing as evaluation"方法比 scaling law 实验更高效

### 2.2 OLMo 2 (7B / 13B / 32B) — AI2

**方法（最先进的开源实践）:**

1. **Stage 1**: 标准预训练（WSD schedule），LR 保持恒定高值
2. **Stage 2 (Mid-training/Annealing)**:
   - 从 Stage 1 最终 checkpoint 开始
   - 在 **Dolmino Mix** 高质量数据上训练
   - LR 从 Stage 1 结束值**线性退火到 0**
   - **关键创新: 多次运行 + Model Souping**

**Dolmino Mix 数据:**
- 高质量网页文本（DCLM 过滤、FineWeb-Edu）
- 数学专项数据（TuluMath、GSM8K train）
- 合成数据（由强模型生成的 QA pairs）

**Token 预算:**

| 模型 | 退火 Token 数 | 运行次数 | 最终处理 |
|------|--------------|---------|----------|
| 7B   | 50B × 3     | 3 次（不同数据顺序）| 平均合并 |
| 13B  | 100B × 3 + 300B × 1 | 4 次 | 平均合并 |
| 32B  | 50B × 3     | 3 次 | 平均合并 |

**Model Souping（模型汤）:**
- 每次 annealing run 使用相同数据但不同随机顺序
- 最终对所有 run 的模型权重取**算术平均**
- 这相当于免费的 ensemble，不增加推理成本
- 参考：Wortsman et al., 2022 "Model soups: averaging weights of multiple fine-tuned models"

**Microanneals（微退火）:**
- 用于快速评估不同数据混合配比的效果
- 从同一 checkpoint 出发，执行短时间退火（远小于完整退火）
- 对比不同配比的 benchmark 表现
- 假设：性能排名在不同规模间保持稳定（stability hypothesis）

### 2.3 DeepSeek V3 (671B MoE)

**方法:**
- 总预训练 14.8T tokens
- LR 从 0 warmup 到 2.2×10⁻⁴，在前 10T tokens 保持稳定
- 后 4.3T tokens 逐步衰减到 2.2×10⁻⁵（10% of peak）
- 最后阶段进一步调整数据配比

**特点:**
- 衰减期非常长（4.3T tokens, 占总量 ~29%）
- 全程零 loss spike，无需 rollback
- 采用 Multi-Token Prediction 目标

### 2.4 Phi-4 (14B) — Microsoft

**方法:**
- 以合成数据为核心的训练策略
- 预训练后有一个**短暂的 midtraining 阶段**
- 主要用于长上下文扩展（从 4K 到 16K）
- 引入高质量合成 QA、推理数据

**独特点:**
- Phi-4 的训练数据中**合成数据占主导**
- Midtraining 阶段引入更多样化的格式（对话、问答）

### 2.5 Yi-Lightning (DeepSeek-based)

**三阶段方法:**
1. **初始预训练**: 数据多样性优先，建立基础能力
2. **退火阶段**: 逐步提升高质量数据比例（复杂推理 + 低资源多语言）
3. **快速衰减阶段**: 占总 token 的 12.5%，进一步强化高质量数据，引入早期指令调优适配

### 2.6 YuLan-Mini (2.4B)

**特点:**
- 第一个公开在预训练中引入形式化数学数据的研究
- 退火阶段数据配比大幅调整
- 在 Qwen2.5-Math-7B 上取得竞争性结果

---

## 3. 学习率调度策略

### 3.1 主流 LR Schedule 对比

#### Cosine Decay（传统方法）

```
LR(t) = η_min + 0.5(η_max - η_min)(1 + cos(πt/T))
```

- 优点：平滑衰减，广泛验证
- 缺点：需要预先确定总步数 T，不灵活
- 代表：Llama 1/2, GPT-3

#### WSD (Warmup-Stable-Decay)

```
Phase 1 (Warmup):  LR = η_max × (t / T_warmup)
Phase 2 (Stable):  LR = η_max  (占总步数 ~70-80%)
Phase 3 (Decay):   LR = η_max × (1 - (t - T_stable) / T_decay) → 0
```

- 优点：灵活，可随时开始 decay；main branch 可继续训练
- 缺点：需要决定何时启动 decay
- 代表：OLMo 2, MiniCPM, DeepSeek (变体)

**WSD 的核心优势：** 主分支保持恒定 LR 持续预训练，可随时分叉（branch off）进行 decay 获取中间 checkpoint，而不影响主训练进程。这使得"退火"成为可以**多次独立尝试**的操作。

#### Cosine with Annealing Extension

```
Phase 1: Standard cosine decay over main training
Phase 2: Re-anneal from current LR to 0 over high-quality data
```

- Llama 3 的方法：在 cosine 结束后，额外加一段线性退火

### 3.2 推荐：针对我们 7B 模型

基于我们的训练配置（200B tokens, 8×H100, cosine LR schedule），推荐：

**方案 A: 延续 Cosine + 额外退火阶段（推荐）**

```
主预训练: 200B tokens, cosine decay (η_max=3e-4, η_min=3e-5)
退火阶段: 额外 20B tokens, linear decay (3e-5 → 0), 高质量数据
```

**方案 B: 重新退火（Re-anneal）**

```
从 200B 预训练最终 checkpoint 开始
重新 warmup 到 1e-4 (短暂, 100 steps)
在 20B tokens 上 linear decay 到 0
```

**推荐方案 A**，因为它更简单且与 Llama 3 的实践一致。

---

## 4. 退火阶段数据策略

### 4.1 数据配比建议

对比主预训练阶段和退火阶段的配比变化：

| 数据类型 | 主预训练 | 退火阶段 | 变化方向 | 来源 |
|----------|---------|---------|---------|------|
| 通用网页文本 | 50% | 25% | ↓ 大幅降低 | FineWeb-Edu (Top 质量) |
| 代码 | 20% | 30% | ↑ 显著提升 | StarCoder (精选) |
| 数学/STEM | 8% | 25% | ↑ 大幅提升 | OpenWebMath + 合成 |
| 学术论文 | 5% | 10% | ↑ 提升 | ArXiv 精选 |
| 指令风格文本 | 0% | 5% | 新增 | 自然指令 QA |
| Books/Wiki | 12% | 5% | ↓ 降低 | Wikipedia 精选 |
| QA Forums | 5% | 0% | ↓ 移除 | — |

### 4.2 数据质量控制

退火阶段的数据质量要求**远高于**主预训练：

1. **更严格的质量过滤**: 仅使用 FineWeb-Edu score ≥ 3 的网页数据
2. **代码质量**: 仅使用有 star/fork 的高质量仓库，排除配置文件、生成代码
3. **数学数据**: 优先使用 step-by-step 解题过程（而非纯题目）
4. **合成数据**: 可使用强模型生成的 QA pairs（OLMo 2 验证有效）
5. **Decontamination**: 严格排除 benchmark 训练集数据（MMLU, GSM8K, HumanEval 等）

### 4.3 可用数据源

| 数据源 | 类型 | 大小 | 质量 | 获取方式 |
|--------|------|------|------|----------|
| FineWeb-Edu (Top) | 通用 | ~1.3T tokens | ⭐⭐⭐⭐⭐ | HuggingFace |
| StarCoder | 代码 | ~250B tokens | ⭐⭐⭐⭐ | HuggingFace |
| OpenWebMath | 数学 | ~15B tokens | ⭐⭐⭐⭐ | HuggingFace |
| ProofPile-2 | 数学/学术 | ~55B tokens | ⭐⭐⭐⭐ | EleutherAI |
| ArXiv (RedPajama) | 学术 | ~28B tokens | ⭐⭐⭐⭐ | RedPajama |
| StackExchange (精选) | QA | ~15B tokens | ⭐⭐⭐⭐ | The Pile |
| Dolmino Mix (参考) | 混合 | 50-300B | ⭐⭐⭐⭐⭐ | AI2 开源 |

---

## 5. 实施方案：我们的 7B 模型

### 5.1 总体计划

```
预训练 (200B tokens, cosine decay)
        │
        ▼
[200B checkpoint] ─── 退火分支 ──┬── Run 1 (20B, seed=42)
                                 ├── Run 2 (20B, seed=123)
                                 └── Run 3 (20B, seed=456)
                                          │
                                          ▼
                                 Model Souping (权重平均)
                                          │
                                          ▼
                                 7B Enhanced Base Model
```

### 5.2 训练配置

```yaml
# annealing_config.yaml
annealing:
  # 基础设置
  base_checkpoint: "checkpoints/pretrain-200B/"
  total_tokens: 20B  # 每次运行
  num_runs: 3  # 不同随机种子

  # 学习率
  lr_schedule: linear_decay
  start_lr: 3e-5  # 从预训练最终 LR 开始
  end_lr: 0
  warmup_steps: 0  # 无需 warmup，直接 decay

  # 批量大小（与预训练保持一致）
  micro_batch_size: 2
  gradient_accumulation_steps: 16
  global_batch_size: 256
  sequence_length: 4096

  # 数据配比
  data_mix:
    fineweb_edu_top:  0.25
    starcoder_select: 0.30
    openwebmath:      0.15
    proofpile2:       0.10
    arxiv_select:     0.10
    instruction_qa:   0.05
    wikipedia:        0.05

  # 其他超参数
  weight_decay: 0.1
  gradient_clipping: 1.0
  precision: bf16
  flash_attention: true
```

### 5.3 Model Souping 实现

```python
import torch
from pathlib import Path

def model_soup(checkpoint_paths: list[str], output_path: str):
    """
    Average weights of multiple annealing runs (OLMo 2 style).
    
    Args:
        checkpoint_paths: List of paths to annealing run checkpoints
        output_path: Path to save the averaged model
    """
    n = len(checkpoint_paths)
    print(f"Souping {n} models...")

    # Load first model as base
    avg_state = torch.load(checkpoint_paths[0], map_location="cpu")

    # Accumulate weights from remaining models
    for path in checkpoint_paths[1:]:
        state = torch.load(path, map_location="cpu")
        for key in avg_state:
            avg_state[key] = avg_state[key] + state[key]

    # Average
    for key in avg_state:
        avg_state[key] = avg_state[key] / n

    # Save
    torch.save(avg_state, output_path)
    print(f"Souped model saved to {output_path}")

# Usage
model_soup(
    checkpoint_paths=[
        "checkpoints/anneal-run1/final.pt",
        "checkpoints/anneal-run2/final.pt",
        "checkpoints/anneal-run3/final.pt",
    ],
    output_path="checkpoints/7b-enhanced-base/model.pt"
)
```

### 5.4 时间和成本估算

```
退火阶段 Token 数: 20B × 3 runs = 60B tokens total
8×H100 吞吐量: ~5.18B tokens/day (来自预训练估算)
每次运行时间: 20B / 5.18B ≈ 3.86 天 ≈ 4 天

方案 A (顺序执行):
  3 runs × 4 天 = 12 天
  成本: 12天 × $25.6/hr × 24hr = ~$7,373

方案 B (并行执行, 需要 3 节点):
  4 天
  成本: 4天 × $25.6/hr × 24hr × 3 = ~$7,373 (相同成本, 更快)

推荐方案 A (顺序): 无需额外硬件，12 天可接受
```

### 5.5 评估检查点

在退火过程中插入评估检查点，监控能力变化：

| Token 进度 | 评估 Benchmark | 目的 |
|-----------|----------------|------|
| 0B (起始) | MMLU, GSM8K, HumanEval | 基线 |
| 5B | MMLU, GSM8K, HumanEval | 早期趋势 |
| 10B | MMLU, GSM8K, HumanEval, MATH | 中期检查 |
| 20B (结束) | 全套 Benchmark | 最终评估 |

**关键观察指标:**
- GSM8K / MATH: 数学能力是否显著提升
- HumanEval / MBPP: 代码能力是否提升
- MMLU: 通用知识是否保持（不应下降）
- Loss 曲线: 应在退火期间显著下降

---

## 6. 关键风险与注意事项

### 6.1 常见陷阱

1. **灾难性遗忘**: 退火数据比例过偏可能导致通用能力下降
   - 缓解：保留 25-30% 通用高质量数据
   - OLMo 2: 保留一般高质量数据混合

2. **过拟合退火数据**: 数据量太少或质量差时可能过拟合
   - 缓解：确保退火数据量足够（≥10B tokens for 7B model）
   - 使用 validation loss 监控

3. **LR 衰减过快**: 模型来不及学习新数据就已经"冻结"
   - 缓解：线性衰减比指数衰减更平缓
   - 建议衰减周期 ≥ 5B tokens

4. **Benchmark 污染**: 退火数据包含 benchmark 训练集
   - 缓解：严格 decontamination
   - 不包含任何常用 benchmark 的训练集

### 6.2 Microanneal 验证流程

在正式退火前，先用 **microanneal** 快速验证数据配比：

```
1. 从预训练 checkpoint 分叉
2. 在候选数据配比上退火 1B tokens（约 4-5 小时）
3. 评估几个关键 benchmark (GSM8K, HumanEval, MMLU)
4. 对比不同配比的效果
5. 选择最优配比用于完整退火
```

估计 3-4 个 microanneal 实验 × 5 小时 = ~1 天，非常值得投资。

---

## 7. 总结与行动项

### 7.1 核心结论

1. **Mid-training annealing 是业界共识**: Llama 3, OLMo 2, DeepSeek V3, Phi-4, Yi-Lightning 全部采用
2. **效果显著**: 特别是对小模型（≤13B），8B 模型在 GSM8K 上可提升 24%（Llama 3 数据）
3. **关键技术**: LR 线性衰减到 0 + 高质量 STEM/Code 数据 + Model Souping
4. **我们的方案**: 20B tokens × 3 runs，预计 12 天，成本 ~$7K
5. **Microanneal 先行**: 用 1B token 的快速实验验证数据配比

### 7.2 实施步骤

```
Step 1: 准备退火数据集 (2-3天)
  - 下载/筛选 FineWeb-Edu Top, StarCoder, OpenWebMath, ProofPile-2
  - Tokenize + Quality Filter + Decontaminate
  - 打包为 memory-mapped 分片格式

Step 2: Microanneal 实验 (1天)
  - 测试 3-4 种数据配比
  - 每次 1B tokens, 评估 GSM8K + HumanEval + MMLU

Step 3: 正式退火 (12天)
  - Run 1: seed=42, 20B tokens, linear decay
  - Run 2: seed=123, 20B tokens, linear decay
  - Run 3: seed=456, 20B tokens, linear decay

Step 4: Model Souping (0.5天)
  - 平均三次运行的最终 checkpoint
  - 完整 benchmark 评估

Step 5: 评估与报告 (1天)
  - MMLU, GSM8K, MATH, HumanEval, MBPP 全套评估
  - 对比预训练基座 vs 退火后的提升
```

### 7.3 预期效果

基于业界数据的保守估计（7B 模型, 20B tokens 退火）：

| Benchmark | 预训练基座 (估) | 退火后 (估) | 预期提升 |
|-----------|----------------|------------|----------|
| GSM8K     | ~35-45%        | ~55-65%    | +15-25%  |
| MATH      | ~10-15%        | ~15-22%    | +5-8%    |
| HumanEval | ~20-30%        | ~28-38%    | +5-10%   |
| MMLU      | ~45-55%        | ~46-56%    | +1-2%    |

> **注意**: 以上为基于 Llama 3 8B 退火效果的类比估计，实际效果取决于我们的预训练质量和退火数据质量。

---

## 参考文献

1. **Llama 3 Herd of Models** (Meta, 2024) - arXiv:2407.21783
   - 40M tokens 退火, 24% GSM8K 提升 (8B)
2. **OLMo 2: 2 OLMo 2 Furious** (AI2, 2024) - arXiv:2501.00656
   - Model souping, microanneals, Dolmino Mix
3. **A Survey on LLM Mid-Training** (Meituan/PKU, 2025) - arXiv:2510.23081
   - 最全面的 mid-training 综述
4. **Mid-Training of Large Language Models: A Survey** (2025) - arXiv:2510.06826
   - 另一篇全面综述
5. **DeepSeek-V3 Technical Report** (DeepSeek, 2024) - arXiv:2412.19437
   - 14.8T tokens, WSD 变体
6. **Phi-4 Technical Report** (Microsoft, 2024) - arXiv:2412.08905
   - 合成数据为核心的 midtraining
7. **Understanding Warmup-Stable-Decay LR** (2024) - arXiv:2410.05192
   - WSD schedule 理论分析
8. **Scaling Laws and Compute-Optimal Training Beyond Fixed Durations** (NeurIPS 2024)
   - Cooldown phase 分析
9. **Model soups: averaging weights of multiple fine-tuned models** (ICML 2022)
   - Model souping 原始论文
10. **How Learning Rate Decay Wastes Your Best Data** (2025) - arXiv:2511.18903
    - LR decay 与数据排序的交互
