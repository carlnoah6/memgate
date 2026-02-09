# 训练技巧：学习率调度、梯度累积、混合精度与 Checkpoint 策略

> 研究日期：2026-02-08
> 系列：从零训练 LLM #7

---

## 1. 学习率调度（Learning Rate Schedule）

学习率是大语言模型训练中最关键的超参数之一。选择合适的学习率调度策略，直接影响模型的收敛速度、最终性能和训练稳定性。

### 1.1 Warmup（预热阶段）

几乎所有现代 LLM 训练都以 warmup 阶段开始。其核心思路是：在训练初期，模型参数处于随机初始化状态，此时如果使用过大的学习率，梯度更新可能导致参数剧烈震荡甚至发散。因此，warmup 阶段将学习率从一个很小的值（通常为 0 或峰值的 1/10）线性增长到目标峰值学习率。

**典型配置：**
- 7B 模型：warmup 2000 步，占总训练步数的 0.5%-2%
- 70B 模型：warmup 2000-4000 步
- GPT-3 系列论文使用 375M tokens 的 warmup（约占总训练量的 0.1%）

**为什么 warmup 有效？** Adam 优化器在训练初期，二阶矩估计（v_t）尚未充分积累统计信息，容易产生过大的参数更新。Warmup 给优化器足够的时间来「校准」其内部状态。此外，warmup 也有助于避免训练初期 loss spike，这在大规模训练中尤为关键，因为从 checkpoint 恢复的成本极高。

### 1.2 Cosine Decay（余弦退火）

Cosine decay 是目前 LLM 训练中最流行的学习率衰减策略。在 warmup 之后，学习率按照余弦函数从峰值平滑下降到一个最小值（通常为峰值的 1/10）。

$$\eta_t = \eta_{min} + \frac{1}{2}(\eta_{max} - \eta_{min})(1 + \cos(\frac{\pi t}{T}))$$

其中 $\eta_{max}$ 是峰值学习率，$\eta_{min}$ 是最小学习率，$T$ 是总训练步数。

**优势：**
- 初期保持较高学习率，快速探索参数空间
- 中期平滑下降，逐步精细调整
- 末期接近零学习率，有助于收敛到更好的局部最优
- 被 LLaMA、GPT-4、PaLM 等主流模型采用，经过大量实验验证

**典型配置：** 最终学习率设为峰值的 10%（η_min = 0.1 × η_max）。LLaMA-2 使用 peak lr = 3e-4，cosine decay 到 3e-5。

### 1.3 Linear Decay（线性衰减）

线性衰减在 warmup 之后将学习率线性下降到零或一个最小值。虽然比 cosine decay 简单，但实际效果通常相差不大。

$$\eta_t = \eta_{max} \times (1 - \frac{t}{T})$$

**适用场景：** 训练步数不太确定时，线性衰减更容易调整。一些研究表明，在总训练 token 数较少的情况下，线性衰减与 cosine decay 的差异可以忽略。BLOOM-176B 使用了线性衰减方案。

### 1.4 WSD Schedule（Warmup-Stable-Decay）

WSD 是近两年兴起的新型调度策略，被 MiniCPM（2024）和 DeepSeek 等团队推荐。它将训练分为三个阶段：

1. **Warmup 阶段：** 学习率线性增长到峰值（约占总步数的 1-5%）
2. **Stable 阶段：** 保持恒定的最大学习率（占总步数的 80-90%）
3. **Decay 阶段：** 快速衰减到最小学习率（占总步数的 10-15%）

**核心优势：** WSD 允许在 stable 阶段的任意时间点引入 decay 并终止训练，这极大提升了训练的灵活性。传统的 cosine decay 需要预先确定总训练步数，而 WSD 可以根据 loss 曲线的走势动态决定何时进入 decay。MiniCPM 团队发现，WSD 在相同 compute 下可以达到与 cosine decay 相当甚至更好的效果，且更适合增量预训练（continual pretraining）场景。

### 1.5 学习率峰值选择

不同模型规模的推荐峰值学习率：

| 模型规模 | 峰值学习率 | 参考模型 |
|---------|-----------|---------|
| 125M    | 6e-4      | GPT-3 Small |
| 1.3B    | 2e-4      | GPT-3 Medium |
| 7B      | 3e-4      | LLaMA-2 |
| 13B     | 3e-4      | LLaMA-2 |
| 70B     | 1.5e-4    | LLaMA-2 |
| 175B    | 0.6e-4    | GPT-3 |

一般规律：模型越大，峰值学习率越小。这是因为大模型的参数空间更大、梯度方差更低，较小的学习率即可实现有效更新。μP（Maximal Update Parametrization）提供了一种系统化方法，可以在小模型上搜索最优学习率，然后可靠地迁移到大模型。

---

## 2. 梯度累积（Gradient Accumulation）

### 2.1 原理

梯度累积是一种在 GPU 显存有限的情况下模拟大 batch size 训练的技术。其核心思想是：在多个 mini-batch 上分别计算梯度并累加，每经过 K 步累积后才执行一次参数更新。

```python
optimizer.zero_grad()
for i, batch in enumerate(dataloader):
    loss = model(batch) / accumulation_steps  # 注意除以累积步数
    loss.backward()
    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()
```

数学上，梯度累积 K 步等价于使用 K 倍的 batch size：

$$\text{等效 batch size} = \text{micro batch size} \times \text{accumulation steps} \times \text{数据并行度}$$

例如：micro_batch_size=4，accumulation_steps=8，data_parallel_size=4，则等效 batch_size = 4 × 8 × 4 = 128。

### 2.2 注意事项

**Loss 缩放：** 累积梯度时，每个 mini-batch 的 loss 需要除以累积步数（accumulation_steps），以保证梯度的期望值与使用大 batch 时一致。否则累积的梯度会是实际梯度的 K 倍，导致参数更新过大。

**Batch Normalization：** 如果模型使用了 Batch Normalization（LLM 中很少见，通常使用 LayerNorm/RMSNorm），梯度累积会导致 BN 统计量不准确，因为每个 mini-batch 的统计量仅基于小 batch 计算。LLM 使用的 RMSNorm 或 LayerNorm 不受此影响。

**数据 shuffle 一致性：** 梯度累积不影响数据 shuffle 的正确性，但需注意 distributed 训练中各 rank 的同步时机——只在实际 step（而非每个 micro-step）时同步梯度。

### 2.3 常见配置

| 场景 | Micro BS | 累积步数 | 等效 BS | 说明 |
|------|---------|---------|---------|------|
| 单卡 A100 80G, 7B 模型 | 2 | 16 | 32 | 受显存限制 |
| 8×H100, 7B 模型 | 4 | 4 | 128 | 平衡速度与效果 |
| 64×H100, 70B 模型 | 1 | 8 | 512 | 大模型需大 batch |

**Batch size 渐增策略：** 一些训练方案在初期使用较小的 batch size（减少累积步数），训练中期增大到目标 batch size。GPT-3 使用了这种策略，从 32K tokens 逐步增长到 3.2M tokens。这样做的好处是：训练初期小 batch 提供较大的梯度噪声，有助于跳出次优解；训练后期大 batch 提供更稳定的梯度估计，有助于精确收敛。

---

## 3. 混合精度训练（Mixed Precision Training）

### 3.1 概述

混合精度训练通过使用低精度浮点数（FP16/BF16/FP8）来加速计算和减少显存占用，同时通过精心设计的策略保持训练精度。这是现代 LLM 训练的标配技术。

### 3.2 FP16（半精度浮点数）

FP16 使用 1 位符号、5 位指数、10 位尾数，动态范围为 5.96e-8 到 65504。

**优势：** 相比 FP32，显存占用减半，且现代 GPU 的 FP16 Tensor Core 算力远高于 FP32（如 A100 FP16 算力 312 TFLOPS vs FP32 19.5 TFLOPS）。

**问题：** FP16 的动态范围较小（max=65504），在 LLM 训练中容易出现溢出（overflow）或下溢（underflow）。特别是当梯度值非常小（如 1e-8 级别）时会下溢为零，导致信息丢失。

**Loss Scaling：** 为了解决 FP16 的下溢问题，需要使用 loss scaling 技术。基本思路是在反向传播前将 loss 乘以一个较大的缩放因子（如 1024 或动态调整），使得小梯度值被放大到 FP16 可表示的范围内，然后在参数更新前再除以缩放因子。PyTorch 的 `torch.cuda.amp.GradScaler` 提供了动态 loss scaling 的自动化实现。

### 3.3 BF16（Brain Floating Point 16）

BF16 使用 1 位符号、8 位指数、7 位尾数。它牺牲了精度（尾数只有 7 位 vs FP16 的 10 位）换取了与 FP32 相同的动态范围（因为指数位数相同）。

**核心优势：** BF16 的动态范围与 FP32 完全一致，这意味着不需要 loss scaling！训练稳定性显著优于 FP16，几乎可以 drop-in 替换 FP32，代码修改量极小。

**GPU 兼容性：**
- **支持 BF16：** NVIDIA A100、H100、H200、RTX 3090/4090、Google TPU v2+
- **不支持 BF16：** NVIDIA V100、RTX 2080（这些卡只能用 FP16）

**推荐：** 如果 GPU 支持 BF16，几乎总是优先选择 BF16 而非 FP16。LLaMA、GPT-4、PaLM、Gemini 等主流模型均使用 BF16 训练。

### 3.4 FP8（8 位浮点数）

FP8 是 NVIDIA H100（Hopper 架构）引入的新精度格式，包括两种变体：
- **E4M3：** 4 位指数、3 位尾数，用于前向传播和权重存储
- **E5M2：** 5 位指数、2 位尾数，用于反向传播（需要更大动态范围）

**优势：** 相比 BF16，FP8 进一步将显存占用减半，且 H100 的 FP8 Tensor Core 算力高达 1979 TFLOPS（vs BF16 的 989 TFLOPS），理论速度提升近 2 倍。

**挑战：** FP8 训练需要更复杂的量化和缩放策略（per-tensor 或 per-channel scaling），目前主要由 NVIDIA TransformerEngine 库支持。实际训练中，FP8 的精度损失需要仔细监控，目前在 7B-70B 规模的实验中已证明可行，但尚未成为绝对主流。

**GPU 支持：** 目前仅 H100/H200/B100/B200 及更新架构原生支持 FP8。

### 3.5 混合精度训练的最佳实践

典型的混合精度训练策略：

1. **Master weights 保留 FP32：** 优化器状态（Adam 的一阶矩 m 和二阶矩 v）和模型的 master copy 使用 FP32
2. **前向/反向传播使用 BF16/FP16：** 矩阵乘法和卷积等计算密集操作在低精度下进行
3. **梯度通信使用 BF16/FP16：** 分布式训练中的 allreduce 操作使用低精度以减少通信量
4. **特殊层保留 FP32：** Softmax、LayerNorm、loss 计算等对精度敏感的操作保持 FP32

**显存估算（以 7B 模型为例）：**
- 模型参数（BF16）：7B × 2B = 14 GB
- 优化器状态（FP32）：7B × 4B × 2 = 56 GB（Adam 的 m 和 v）
- 梯度（BF16）：7B × 2B = 14 GB
- Master weights（FP32）：7B × 4B = 28 GB
- 总计约 112 GB（不含激活值）

---

## 4. Checkpoint 策略

### 4.1 为什么 Checkpoint 极其重要

LLM 训练通常持续数周到数月，期间可能遭遇各种故障：GPU 硬件故障、网络中断、NaN/Inf loss spike、OOM 等。没有合理的 checkpoint 策略，一次故障可能浪费数天的训练时间和数万美元的计算成本。

### 4.2 Checkpoint 频率

**推荐策略：**
- **常规 checkpoint：** 每 500-2000 步保存一次（视训练规模而定）
- **滚动保留：** 只保留最近 3-5 个常规 checkpoint，旧的自动删除
- **里程碑 checkpoint：** 每 10000 步或每处理 100B tokens 永久保存一个
- **基于时间的备选：** 对于很长的步（大 batch），每 1-4 小时保存一次

**大规模训练的实践：**
- LLaMA-65B 训练：每 ~1500 步保存，总训练 ~200K 步
- BLOOM-176B：每 3 小时保存一次
- GPT-3 级别训练：通常每 1000 步保存

### 4.3 Checkpoint 存储优化

一个 70B 模型的完整 checkpoint（含优化器状态）可能超过 500 GB。存储优化至关重要：

**分片存储（Sharded Checkpoints）：** 在分布式训练中，每个 rank 只保存其负责的模型分片。FSDP 的 `SHARDED_STATE_DICT` 和 DeepSpeed 的 ZeRO checkpoint 都支持这种方式。优点是保存速度快、I/O 分散；缺点是加载时需要相同的并行配置。

**统一格式：** PyTorch 2.0+ 引入了 Distributed Checkpoint（DCP），支持将分片 checkpoint 保存为统一格式，后续可以用不同的并行度加载。DeepSpeed 也提供了 `convert_zero_checkpoint_to_fp32_model_state_dict.py` 工具。

**异步保存：** 训练主进程将 checkpoint 数据交给后台线程/进程写入存储，避免阻塞训练。PyTorch DCP 和 Megatron-LM 都支持异步 checkpoint 保存，可将 checkpoint overhead 从分钟级降低到秒级。

**增量/差量 Checkpoint：** 只保存自上次 checkpoint 以来发生变化的部分。目前支持较少，但对于频繁保存场景可显著减少 I/O。

**压缩：** 对 checkpoint 文件进行压缩（如 gzip、zstd），通常可以节省 20-40% 的存储空间。

### 4.4 断点续训（Resume from Checkpoint）

断点续训不仅需要恢复模型参数，还需要恢复整个训练状态：

**必须恢复的内容：**
1. 模型参数（model state dict）
2. 优化器状态（Adam 的 m, v, step count）
3. 学习率调度器状态（当前步数、lr 值）
4. 数据加载器状态（当前 epoch、已处理的样本索引）
5. 随机数种子状态（torch、numpy、python random）
6. GradScaler 状态（如果使用 FP16 + loss scaling）
7. 当前训练步数和已处理的 token 数

**数据加载器恢复的关键性：** 很多人忽略数据加载器状态的恢复，导致续训时重复处理已见过的数据。正确做法是记录已消耗的 sample 索引或使用确定性的 data shuffle 方案（基于 epoch + seed），续训时跳过已处理的部分。

**验证续训正确性：** 好的实践是在保存 checkpoint 前记录当前的 loss 值和学习率，续训后验证这些值是否匹配。如果 loss 出现明显跳变，说明某些状态未正确恢复。

**弹性训练（Elastic Training）：** 续训时 GPU 数量可能发生变化。FSDP 的 Resharding 和 DeepSpeed 的 elastic checkpoint 支持在不同并行度下加载 checkpoint，但需要注意 batch size 可能需要相应调整。

---

## 5. 梯度裁剪与权重衰减

### 5.1 梯度裁剪（Gradient Clipping）

梯度裁剪是防止训练发散的关键安全网。当梯度范数超过阈值时，将其缩放到阈值以内。

**Max Norm Clipping（最常用）：**

$$g \leftarrow g \cdot \frac{\text{max\_norm}}{||g||} \quad \text{if } ||g|| > \text{max\_norm}$$

**典型配置：**
- LLaMA 系列：max_norm = 1.0
- GPT-3：max_norm = 1.0
- PaLM：max_norm = 1.0
- 几乎所有主流 LLM 都使用 1.0 作为梯度裁剪阈值

**梯度范数监控：** 训练过程中应持续监控梯度范数。正常训练时梯度范数应在一个稳定范围内波动。如果突然飙升（spike），可能预示着训练即将发散。可以在梯度范数超过阈值 K 倍（如 5-10 倍）时触发告警。

### 5.2 权重衰减（Weight Decay）

权重衰减是正则化的重要手段，防止模型参数过大导致过拟合。在 AdamW 优化器中，权重衰减与 L2 正则化被解耦，效果更好。

$$\theta_{t+1} = (1 - \lambda)\theta_t - \eta \cdot \hat{m}_t / (\sqrt{\hat{v}_t} + \epsilon)$$

**典型配置：**
- 权重衰减系数 λ = 0.1（LLaMA、GPT-3、PaLM）
- 仅对 2D 参数（权重矩阵）施加权重衰减
- 不对 bias、LayerNorm/RMSNorm 参数施加权重衰减
- 不对 embedding 层施加权重衰减（有争议，部分工作会施加）

```python
# 典型的参数分组
decay_params = [p for n, p in model.named_parameters() if p.dim() >= 2]
no_decay_params = [p for n, p in model.named_parameters() if p.dim() < 2]
optimizer = AdamW([
    {"params": decay_params, "weight_decay": 0.1},
    {"params": no_decay_params, "weight_decay": 0.0},
], lr=3e-4, betas=(0.9, 0.95))
```

### 5.3 Adam 超参数

除了学习率，Adam 优化器的 β 参数也很重要：

- **β1 = 0.9：** 一阶矩的指数衰减率，控制动量
- **β2 = 0.95：** 二阶矩的指数衰减率（注意：传统默认值 0.999，LLM 训练中通常降低到 0.95）
- **ε = 1e-8：** 数值稳定性常数

β2 降低到 0.95 的原因：LLM 训练的数据分布变化较大，较低的 β2 使得二阶矩估计对最新梯度更敏感，有助于适应分布的变化。LLaMA-2、GPT-3、PaLM 均使用 β2=0.95。

---

## 6. 其他关键训练技巧

### 6.1 Embedding 缩放

一些模型对 embedding 层的输出进行缩放（乘以 √d_model），以稳定训练初期的激活值范围。GPT-NeoX 和一些较新的架构使用了这种技术。

### 6.2 Z-Loss / Auxiliary Loss

为了防止 logits 过大导致 softmax 计算不稳定，可以添加 z-loss：

$$L_z = \alpha \cdot \log^2(\sum_i e^{z_i})$$

PaLM 使用了 z-loss（α=1e-4），发现它能显著减少训练中的 loss spike。

### 6.3 序列并行与重计算

**激活重计算（Activation Checkpointing/Recomputation）：** 用计算换显存——前向传播时只保存部分层的激活值，反向传播时重新计算丢弃的激活值。通常可以节省 60-70% 的激活显存，代价是约 33% 的计算时间增加。

**选择性重计算：** 只对显存占用大但计算便宜的操作（如 Attention 的 softmax 输出）进行重计算，在显存节省和计算开销之间取得更好的平衡。Megatron-LM 支持这种细粒度控制。

### 6.4 数据预处理与打包

**Sequence Packing：** 将多个短文本打包到一个固定长度的序列中，减少 padding 浪费。需要使用 attention mask 或 document mask 防止跨文档的注意力泄露。

**数据预 tokenize：** 将原始文本预先 tokenize 并存储为二进制格式（如 numpy memmap），训练时直接加载 token ids，避免运行时 tokenize 的 CPU 瓶颈。

---

## 7. 实践建议：不同规模模型的推荐配置

### 7.1 小模型（1B-3B，学习/实验用）

```yaml
hardware: 1-8× A100/H100
precision: BF16
optimizer: AdamW (β1=0.9, β2=0.95, ε=1e-8)
learning_rate: 3e-4
lr_schedule: cosine decay to 3e-5
warmup: 2000 steps
batch_size: 512K tokens (micro_bs=8, grad_accum=8)
weight_decay: 0.1
gradient_clipping: 1.0
checkpoint: 每 1000 步, 保留最近 5 个
activation_checkpointing: 可选（显存充足则不需要）
framework: PyTorch + FSDP 或 DeepSpeed ZeRO-2
```

### 7.2 中等模型（7B-13B，正式训练）

```yaml
hardware: 8-64× H100
precision: BF16
optimizer: AdamW (β1=0.9, β2=0.95, ε=1e-8)
learning_rate: 3e-4 (7B) / 2e-4 (13B)
lr_schedule: WSD 或 cosine decay
warmup: 2000 steps
batch_size: 2M-4M tokens
weight_decay: 0.1
gradient_clipping: 1.0
checkpoint: 每 500 步, 异步保存, 保留最近 3 个 + 里程碑
activation_checkpointing: 建议开启
framework: DeepSpeed ZeRO-3 或 FSDP
z_loss: 1e-4
```

### 7.3 大模型（70B+，工业级）

```yaml
hardware: 256-2048× H100
precision: BF16 (可尝试 FP8)
optimizer: AdamW (β1=0.9, β2=0.95, ε=1e-8)
learning_rate: 1.5e-4
lr_schedule: WSD（推荐，灵活性更好）
warmup: 2000-4000 steps
batch_size: 4M-16M tokens
batch_rampup: 从小 batch 逐步增大
weight_decay: 0.1
gradient_clipping: 1.0
checkpoint: 每 500 步 + 异步保存 + 分片
activation_checkpointing: 必须开启（选择性重计算）
framework: Megatron-LM (3D 并行) 或 DeepSpeed ZeRO-3 + TP
loss_spike_detection: 监控梯度范数, 自动跳过异常 batch
elastic_training: 配置故障自动恢复
```

---

## 8. 总结

训练大语言模型是一项系统工程，每个训练技巧都不是孤立存在的，而是相互影响、需要综合考虑的：

1. **学习率调度**决定了参数更新的节奏——推荐 WSD（灵活性好）或 cosine decay（成熟稳定）
2. **梯度累积**解决了显存限制——让小显存也能训大 batch
3. **混合精度**是性能优化的基石——BF16 是当前最佳选择，FP8 是未来趋势
4. **Checkpoint 策略**是训练的保险——异步保存 + 分片存储 + 滚动保留
5. **梯度裁剪 + 权重衰减**是训练稳定性的护栏——max_norm=1.0，weight_decay=0.1

最后，训练前务必在小规模上验证所有配置（包括 checkpoint 的保存/恢复），确认无误后再启动大规模训练。大规模训练的试错成本极高，每一个配置错误都可能浪费数天的时间和大量的资金。
