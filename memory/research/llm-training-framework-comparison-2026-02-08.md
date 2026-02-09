# LLM 训练框架对比：PyTorch FSDP / DeepSpeed / Megatron-LM / JAX+TPU

> 研究日期：2026-02-08
> 系列：从零训练 LLM + 视觉模型 #4

---

## 一、概览：四大训练框架定位

| 框架 | 开发者 | 语言/生态 | 核心技术 | 主要硬件 | 定位 |
|------|--------|-----------|----------|----------|------|
| **PyTorch FSDP** (含 FSDP2 / TorchTitan) | Meta / PyTorch 团队 | PyTorch 原生 | ZeRO-style 参数分片 | NVIDIA GPU | PyTorch 官方分布式方案，简洁高效 |
| **DeepSpeed** | Microsoft | PyTorch 插件 | ZeRO-1/2/3/Infinity | NVIDIA GPU | 极致内存优化，支持超大模型 |
| **Megatron-LM** (含 Megatron-Core) | NVIDIA | PyTorch 基础 | 3D 并行（TP+PP+DP） | NVIDIA GPU（深度优化） | 工业级超大模型训练参考实现 |
| **JAX + TPU** (含 MaxText) | Google | JAX (XLA) | 编译器驱动分片 | Google TPU（也支持 GPU） | 函数式编程 + 编译器自动优化 |

---

## 二、PyTorch FSDP / FSDP2

### 2.1 核心原理

FSDP (Fully Sharded Data Parallel) 源自 FairScale 项目，受 DeepSpeed ZeRO 启发，将模型参数、梯度、优化器状态**分片**到多个 GPU 上。PyTorch 2.x 将其升级为一等公民。

**分片策略：**
- `FULL_SHARD`：等效 ZeRO-3，完全分片参数+梯度+优化器状态
- `HYBRID_SHARD`：节点内全分片，节点间仅复制（减少跨节点通信）
- `NO_SHARD`：传统 DDP（每 GPU 一份完整模型副本）

### 2.2 FSDP2 与 TorchTitan

**FSDP2** 是 PyTorch 2.4+ 引入的重写版本，核心改进：
- **Per-parameter sharding**：不再要求 flat parameter，更灵活
- **与 torch.compile 完全兼容**：支持编译器优化
- **原生 DTensor 支持**：统一的分布式张量抽象

**TorchTitan** (Meta, ICLR 2025) 是基于 FSDP2 的参考训练平台：
- **4D 并行**：FSDP2 + Tensor Parallel + Pipeline Parallel + Context Parallel
- **性能数据**：
  - Llama 3.1 8B @ 128 GPU：比优化基线快 **65.08%**（1D 并行）
  - Llama 3.1 70B @ 256 GPU：快 **12.59%**（2D 并行）
  - Llama 3.1 405B @ 512 GPU：快 **30%**（3D 并行）
- 支持 Float8 训练、Ring Attention、异步分布式 checkpoint
- 集成 TorchAO、TorchTune 等生态工具

### 2.3 优势

1. **PyTorch 原生**：无需额外依赖，直接操作 autograd 图，零 Python 层间接开销
2. **性能领先（中等规模）**：IBM/ETH 基准测试显示 FSDP FULL_SHARD 比 DeepSpeed ZeRO-3 快约 **5×**（ViT 模型，V100 集群）
3. **混合精度更灵活**：不强制 FP32 upcasting，允许用户选择全低精度训练（节省内存）
4. **通信高效**：融合 reduce-scatter + all-gather，扁平参数张量，桶化通信
5. **生态整合**：与 HuggingFace Accelerate、torch.compile、DTensor 深度集成
6. **代码简洁**：~3000 行核心代码，易于理解和定制

### 2.4 劣势

1. **超大模型（>10B）性能优势缩小**：随模型增大，通信开销增加，与 DeepSpeed 差距缩小
2. **CPU/NVMe offload 功能不如 DeepSpeed 成熟**
3. **Pipeline Parallelism 支持较晚**：虽然 TorchTitan 已实现，但社区经验相对较少
4. **生态碎片化**：FSDP1 vs FSDP2 过渡期间存在兼容性问题

### 2.5 吞吐量基准数据

来自 HuggingFace Accelerate 团队测试（4× A100 GPU, Granite 7B）：

| 框架 | Tokens/sec/device | Step time (s) | MFU |
|------|-------------------|---------------|-----|
| FSDP (aligned) | 3158.7 | 10.4 | 0.41 |
| DeepSpeed ZeRO-3 | 3094.5 | 10.6 | 0.40 |

→ 小规模下两者接近，FSDP 略快约 **2%**。

---

## 三、DeepSpeed

### 3.1 核心技术：ZeRO 家族

DeepSpeed 的核心是 **ZeRO (Zero Redundancy Optimizer)** 系列：

| 阶段 | 分片内容 | 内存节省 | 通信开销 |
|------|----------|----------|----------|
| **ZeRO-1** | 优化器状态 | ~4× | 最低 |
| **ZeRO-2** | 优化器状态 + 梯度 | ~8× | 中等 |
| **ZeRO-3** | 优化器状态 + 梯度 + 参数 | ~N× (N=GPU数) | 最高 |
| **ZeRO-Infinity** | ZeRO-3 + CPU/NVMe offload | 理论无限 | 最高(含IO) |
| **ZeRO++** | 优化 all-gather 通信 | 同 ZeRO-3 | 降低 ~50% |

### 3.2 关键特性

- **CPU/NVMe Offload**：将优化器状态甚至参数卸载到 CPU 内存或 NVMe SSD
  - 单个 A100 80GB 可训练 **超过 1T 参数**的模型（极慢但可行）
- **Activation Checkpointing**：精细控制激活重计算
- **Sparse Attention**：内置稀疏注意力内核
- **MoE 支持**：原生 Mixture-of-Experts 训练
- **Pipeline Parallelism**：内置 PP 调度器
- **推理优化**：DeepSpeed-Inference 支持量化和内核融合

### 3.3 优势

1. **超大模型能力无与伦比**：ZeRO-Infinity 可在有限硬件上训练 TB 级模型
2. **CPU/NVMe offload 最成熟**：对低内存 GPU（如 4090）特别有价值
3. **缩放特性更好**：从 ViT-Large → ViT-Huge，DeepSpeed 减速仅 **1.26×**，FSDP 为 **1.35×**
4. **与 Megatron-LM 深度集成**：Megatron-DeepSpeed 组合是许多大模型的首选
5. **行业验证**：BLOOM 176B、多个 GPT 变体、Falcon 等使用 DeepSpeed 训练
6. **配置驱动**：通过 JSON 配置文件即可启用各种优化，代码改动少

### 3.4 劣势

1. **中等规模性能较低**：Python/C++ 混合架构带来额外开销
2. **强制 FP32 master weights**：ZeRO-3 内部始终将可训练参数 upcast 到 FP32，少量 GPU 时内存翻倍
3. **与 PyTorch 原生功能兼容性**：有时与 torch.compile 等新特性冲突
4. **运行时 bookkeeping 开销**：需要追踪分区所有权、调度器步骤、状态转换
5. **调试困难**：错误信息有时不够直观，CPU RAM 不足时无提示

### 3.5 适用场景

- 模型规模 **>10B 参数**
- GPU 内存有限但需要训练大模型（offload 场景）
- MoE 模型训练
- 需要与 Megatron-LM 组合使用的场景

---

## 四、Megatron-LM / Megatron-Core

### 4.1 核心技术：3D 并行

Megatron-LM 是 NVIDIA 开发的大模型训练参考框架，以 **3D 并行**闻名：

| 并行维度 | 机制 | 典型度 | 通信需求 |
|----------|------|--------|----------|
| **Tensor Parallelism (TP)** | 将单层权重矩阵切分到多 GPU | 2-8 | 高（需 NVLink） |
| **Pipeline Parallelism (PP)** | 将模型层分配到不同 GPU 组 | 4-64 | 中（跨节点可接受） |
| **Data Parallelism (DP)** | 不同 GPU 组处理不同数据 | 任意 | 中（all-reduce） |

额外支持：
- **Sequence Parallelism (SP)**：将序列维度分片，降低激活内存
- **Expert Parallelism (EP)**：MoE 模型专用
- **Context Parallelism (CP)**：超长序列训练

### 4.2 Megatron-Core（2025 最新）

Megatron-Core 是重构后的模块化版本：
- **Megatron Bridge**：HuggingFace ↔ Megatron 检查点双向转换
- **MoE 路线图**（2025 Q3-Q4）：支持 DeepSeek-V3、Qwen3 架构
- **FP8 优化**：Blackwell GPU 性能增强
- **纯 PyTorch 接口**：降低使用门槛

### 4.3 优势

1. **极致性能**：通过手写 CUDA kernel 和 NCCL 优化，在 NVIDIA GPU 上达到最高 MFU
2. **3D 并行成熟度最高**：TP 的 column/row parallel 实现是业界标准
3. **经过最大规模验证**：Megatron-Turing NLG 530B (NVIDIA+Microsoft) 使用此框架
4. **序列并行**：独特优势，显著降低激活内存
5. **NVIDIA 硬件深度优化**：充分利用 NVLink、NVSwitch、InfiniBand

### 4.4 劣势

1. **学习曲线陡峭**：代码复杂，定制新模型需要深入了解框架内部
2. **与 HuggingFace 生态不直接兼容**（Megatron Bridge 正在改善）
3. **模型定义需要重写**：不能直接使用标准 PyTorch 模型
4. **主要服务 NVIDIA 硬件**：对非 NVIDIA 加速器支持有限
5. **更新速度慢于社区驱动的项目**

### 4.5 实际使用案例

| 模型 | 训练框架 | 规模 |
|------|----------|------|
| **Llama 3 405B** | Meta 内部框架（PyTorch 原生 4D 并行，类似 TorchTitan） | 16,384 × H100 GPU |
| **DeepSeek-V3 671B** | HAI-LLM（内部框架），16-way PP + 64-way EP + ZeRO-1 DP | 2,048 × H800 GPU |
| **BLOOM 176B** | Megatron-DeepSpeed | 384 × A100 GPU |
| **Falcon 180B** | Megatron-LM + 自定义修改 | 4,096 × A100 GPU |
| **Qwen 系列** | Megatron-based | 未公开 |

---

## 五、JAX + TPU

### 5.1 核心理念

JAX 是 Google 开发的**函数式数值计算框架**，其训练方法与 PyTorch 生态截然不同：

- **XLA 编译器**：将 Python 代码编译为高度优化的机器码
- **自动并行**：通过 `jax.sharding` API + XLA 编译器自动推导最优分片策略
- **函数式编程**：模型是纯函数，天然支持 JIT 编译和自动微分
- **SPMD（Single Program Multiple Data）**：一份代码自动分布到所有设备

### 5.2 关键框架

**MaxText**（Google, 2023-present）：
- 纯 Python/JAX 编写的参考 LLM 训练实现
- 支持 Llama、Gemma、Mistral、DeepSeek 等架构
- 在 TPU v5e 上实现高 MFU，无需手写内核
- 与 Tunix（对齐训练）和 vLLM-TPU（推理）形成完整 AI 栈
- Kakao 验证：MaxText 在 TPU 上的性能**与 GPU 上的 Megatron-LM 相当**

**其他 JAX 训练框架**：
- **T5X / Pax**：Google 内部使用（逐渐迁移到 MaxText）
- **EasyLM**：社区驱动的 JAX LLM 训练工具
- **Levanter**：Stanford 开发，用于 Haliax 模型

### 5.3 并行策略

JAX 通过 **named axes** 和 **PartitionSpec** 声明式地指定分片：

```python
# 声明式分片 — 编译器自动处理通信
mesh = jax.sharding.Mesh(devices, axis_names=('data', 'model'))
sharding = NamedSharding(mesh, P('data', 'model'))
```

支持的并行类型：
- **FSDP-style sharding**：通过 PartitionSpec 自动实现
- **Tensor Parallelism**：通过 axis 分片实现
- **Pipeline Parallelism**：通过 `xmap` 或手动调度实现
- **混合 FSDP + TP**：编译器自动选择最优比例

### 5.4 优势

1. **编译器驱动**：无需手写通信代码，XLA 自动融合算子、优化内存、调度通信
2. **TPU 原生支持**：TPU 上的性能和生态优于 PyTorch/XLA
3. **代码简洁**：MaxText 核心代码远少于 Megatron-LM，纯 Python
4. **自动并行推导**：只需声明 sharding，编译器处理 all-gather/reduce-scatter
5. **函数式天然优势**：JIT 编译、vmap、自动微分、可复现性
6. **Google Cloud 生态**：免费 TPU 配额（TRC 项目）、GKE 集成、完整工具链
7. **成本效益**：TPU v4/v5e 的 perf/$ 通常优于 H100（取决于工作负载）

### 5.5 劣势

1. **生态系统较小**：社区规模远小于 PyTorch
2. **GPU 支持较弱**：虽然 JAX 支持 GPU，但 GPU 上 PyTorch 生态远更成熟
3. **调试困难**：XLA 编译错误信息晦涩，tracing vs execution 概念门槛高
4. **模型迁移成本**：HuggingFace 模型大多是 PyTorch，迁移到 JAX 需要重写
5. **硬件锁定风险**：TPU 仅通过 Google Cloud 提供，不可本地部署
6. **动态计算图支持有限**：函数式范式对动态控制流不友好
7. **学习曲线陡峭**：函数式编程 + JAX 特有概念（pytree、vmap 等）

---

## 六、横向对比

### 6.1 综合对比表

| 维度 | PyTorch FSDP | DeepSpeed | Megatron-LM | JAX/TPU |
|------|-------------|-----------|-------------|---------|
| **易用性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **小模型性能 (<1B)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **中模型性能 (1-10B)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **大模型性能 (>10B)** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **内存效率** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **代码简洁度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **社区/生态** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **HuggingFace 集成** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **多硬件支持** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ (TPU 最佳) |
| **Offload 能力** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **MoE 支持** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **长序列支持** | ⭐⭐⭐⭐ (CP) | ⭐⭐⭐ | ⭐⭐⭐⭐ (SP) | ⭐⭐⭐⭐⭐ |

### 6.2 内存分析（7B 模型，bf16 训练）

以 7B 参数模型为例，单 GPU 内存需求估算：

| 组件 | DDP (无分片) | FSDP FULL_SHARD (8 GPU) | DeepSpeed ZeRO-3 (8 GPU) |
|------|-------------|-------------------------|--------------------------|
| 参数 | 14 GB | 1.75 GB | 1.75 GB (但 FP32 master = 3.5 GB) |
| 梯度 | 14 GB | 1.75 GB | 1.75 GB |
| 优化器状态 (AdamW) | 56 GB | 7 GB | 7 GB |
| 激活（batch=8, seq=4096） | ~12 GB | ~12 GB | ~12 GB |
| **总计** | **~96 GB** | **~22.5 GB** | **~25 GB** |

> 注：DeepSpeed 因 FP32 upcasting 多消耗约 ~1.75 GB，但分片数量更多时差异可忽略。

### 6.3 通信开销对比

| 操作 | FSDP | DeepSpeed ZeRO-3 | Megatron TP |
|------|------|-------------------|-------------|
| Forward | all-gather 参数 | all-gather 参数 | 2× all-reduce per layer |
| Backward | all-gather + reduce-scatter | all-gather + reduce-scatter | 2× all-reduce per layer |
| 通信量/step | 2×model_size | 2×model_size | 4×hidden_size×seq_len per layer |
| 需要高带宽互联 | 推荐 | 推荐 | **必需** (NVLink) |

---

## 七、选型建议

### 7.1 按模型规模选型

```
模型 < 1B 参数：
  → PyTorch FSDP（简单高效，无需额外配置）
  → 或 PyTorch DDP（如果单 GPU 能放下）

模型 1B-10B 参数：
  → PyTorch FSDP + Tensor Parallelism (TorchTitan)
  → 或 Megatron-LM（追求极致性能）
  → 或 DeepSpeed ZeRO-2/3

模型 10B-100B 参数：
  → Megatron-LM（3D 并行，性能最优）
  → 或 Megatron-DeepSpeed（结合两者优势）
  → 或 JAX/MaxText + TPU（Google Cloud 环境）
  → 或 TorchTitan（PyTorch 原生，快速迭代）

模型 > 100B 参数：
  → Megatron-DeepSpeed（业界验证最多）
  → 或 定制框架（如 DeepSeek 的 HAI-LLM）
  → 或 JAX + TPU Pod（Google 内部路线）
```

### 7.2 按硬件环境选型

```
NVIDIA H100/A100 集群 + NVLink + InfiniBand：
  → Megatron-LM 或 Megatron-DeepSpeed（充分利用硬件特性）

NVIDIA 消费级 GPU（4090/3090 等）：
  → DeepSpeed ZeRO-Infinity（CPU/NVMe offload 补偿内存不足）
  → 或 FSDP + gradient checkpointing

Google Cloud TPU：
  → JAX + MaxText（原生支持，性能最优）

混合/多云环境：
  → PyTorch FSDP（最大兼容性）
  → 或 HuggingFace Accelerate（一键切换 FSDP/DeepSpeed）
```

### 7.3 按团队经验选型

```
PyTorch 熟练，追求简洁：
  → FSDP2 + TorchTitan

需要快速实验，模型变动频繁：
  → PyTorch FSDP（代码改动最少）

追求极致性能，有经验的基础设施团队：
  → Megatron-LM 或 Megatron-Core

研究导向，重视可复现性：
  → JAX + MaxText

预算有限，GPU 内存紧张：
  → DeepSpeed ZeRO-Infinity
```

---

## 八、新兴趋势（2025-2026）

### 8.1 框架融合

- **TorchTitan** 正在成为 PyTorch 官方的 "all-in-one" 方案，吸收了 FSDP、TP、PP、CP 的优势
- **Megatron-Core** 向模块化发展，降低使用门槛
- **HuggingFace Accelerate** 作为抽象层，让用户一键切换 FSDP/DeepSpeed

### 8.2 编译器驱动的自动并行

- PyTorch **SimpleFSDP**（实验性）：编译器级别的 FSDP，无需手动 wrap
- JAX 的 **GSPMD**：自动推导最优分片策略
- 趋势：手写并行代码 → 声明式分片 → 全自动编译器分片

### 8.3 FP8 训练

- DeepSeek-V3 首次大规模使用 FP8 训练，节省约 50% 内存和带宽
- NVIDIA Blackwell 架构原生支持 FP8
- TorchTitan、Megatron-Core、MaxText 都在积极支持 FP8

### 8.4 超长序列训练

- Context Parallelism / Ring Attention 成为标配
- TorchTitan 支持最长 1M token 序列
- JAX 在超长序列场景下有编译器优势

### 8.5 MoE 训练优化

- DeepSeek-V3 的 DualPipe 算法显著减少 pipeline bubble
- Expert Parallelism 变得越来越重要
- Megatron-Core 2025 路线图重点支持 MoE

---

## 九、实操建议：从零开始选哪个？

### 对于个人/小团队初学者

**首选 TorchTitan + FSDP2**，原因：
1. 代码最简洁、文档最好
2. PyTorch 原生，不需要学新框架
3. 从 1B 到 405B 模型都有参考配置
4. 社区活跃，问题容易解决

### 对于已有 PyTorch 经验、追求性价比

**FSDP2 + DeepSpeed offload 按需切换**：
1. 先用 FSDP2 跑通训练
2. 如果 GPU 内存不够，切换 DeepSpeed ZeRO-Infinity
3. 通过 HuggingFace Accelerate 一键切换

### 对于追求极致性能的团队

**Megatron-Core + DeepSpeed**：
1. 使用 Megatron 的 TP+PP 获得最佳计算效率
2. 使用 DeepSpeed ZeRO 管理内存
3. 参考 BLOOM、Falcon 等成功案例

### 对于 Google Cloud 用户

**JAX + MaxText + TPU**：
1. 申请 Google TRC 项目获取免费 TPU 配额
2. 使用 MaxText 参考实现快速启动
3. 编译器自动优化分片策略

---

## 十、参考资料

1. [FSDP vs DeepSpeed 实验对比](https://medium.com/@romeokienzler/fsdp-vs-deepspeed-9df47ee5ccbb) - IBM Research & ETH Zürich, 2025
2. [From DeepSpeed to FSDP and Back](https://huggingface.co/blog/deepspeed-to-fsdp-and-back) - HuggingFace, 2024
3. [TorchTitan: One-stop PyTorch native solution](https://arxiv.org/abs/2410.06511) - Meta, ICLR 2025
4. [How To Scale Your Model](https://jax-ml.github.io/scaling-book/) - JAX Team, 2025
5. [MaxText](https://github.com/AI-Hypercomputer/maxtext) - Google, 2023-2025
6. [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437) - DeepSeek, 2024
7. [Megatron-LM](https://github.com/NVIDIA/Megatron-LM) - NVIDIA, ongoing
8. [FSDP vs DeepSpeed Concept Guide](https://huggingface.co/docs/accelerate/en/concept_guides/fsdp_and_deepspeed) - HuggingFace
