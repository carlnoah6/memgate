# Full-Scale Pre-training Plan: 7B Model on 5T Tokens (8×H100)

**Date:** 2026-02-11
**Task:** Phase 3 - Full-Scale Pre-training (5T Tokens)
**Goal:** 执行 7B 模型的主要预训练任务（8×H100, 预计 3-4 周），产出 7B Base Model Checkpoints

---

## 1. 计算量估算 (Compute Estimation)

### 1.1 总 FLOPs 计算

使用标准公式 `C = 6 × N × D`：
- **N** (参数量) = 6.49B ≈ 7B
- **D** (Token 数) = 5T = 5 × 10¹²
- **C** = 6 × 7 × 10⁹ × 5 × 10¹² = **2.1 × 10²³ FLOPs** (210 ZettaFLOPs)

### 1.2 训练时间估算

**H100 SXM bf16 峰值性能:** ~989 TFLOPS/GPU

**实际 MFU（Model FLOPs Utilization）估算：**
- PyTorch FSDP 在 8×H100 单节点上的 7B 模型 MFU: ~37% (PyTorch 官方博客)
- 使用 FP8 + Transformer Engine 可提升至 ~45-50%
- 保守估算: **40% MFU**

**有效吞吐量计算：**
```
有效 TFLOPS/GPU = 989 × 0.40 = 395.6 TFLOPS
8 GPU 总有效 = 395.6 × 8 = 3164.8 TFLOPS = 3.165 × 10¹⁵ FLOPS
```

**训练时间：**
```
时间(秒) = 2.1 × 10²³ / 3.165 × 10¹⁵ = 66,350,710 秒 ≈ 768 天
```

### ⚠️ 关键发现：8×H100 单节点不足以在合理时间内完成 5T tokens

**现实检查:**
- Llama 1 (7B, 1T tokens): 2048 × A100, ~21 天
- Llama 2 (7B, 2T tokens): 类似规模集群
- IBM LlamaT (7B, 2T tokens): 128 × A100, ~50 天
- PyTorch 官方: 128 A100 可达 3,700 tokens/sec/GPU = 40B tokens/day

**8×H100 的实际吞吐量:**
```
tokens/sec/GPU (H100, 7B, no AC) = ~7,500 (PyTorch 官方数据)
8 GPU 总吞吐 = 7,500 × 8 = 60,000 tokens/sec
每天处理 = 60,000 × 86,400 = 5.18B tokens/day
5T tokens 需要 = 5,000B / 5.18B = ~965 天 ≈ 2.6 年
```

### 1.3 修订后的可行方案

| 方案 | GPU 数量 | 预计训练时间 | 预计成本 |
|------|----------|-------------|----------|
| A: 8×H100 (原计划, 5T tokens) | 8 | **~965 天 ❌ 不可行** | ~$300K+ |
| B: 8×H100, 缩减到 500B tokens | 8 | ~96 天 (~3 个月) | ~$30K |
| C: 8×H100, 缩减到 200B tokens | 8 | ~39 天 (~5.5 周) | ~$12K |
| D: 8×H100, 缩减到 100B tokens | 8 | ~19 天 (~3 周) | ~$6K |
| E: 32×H100 (4 节点), 1T tokens | 32 | ~48 天 | ~$60K |
| F: 64×H100 (8 节点), 2T tokens | 64 | ~48 天 | ~$120K |

**推荐: 方案 C 或 D** — 在 8×H100 单节点上可行，用 100-200B 高质量 tokens 训练，符合 Chinchilla 最优比（7B 模型 ≈ 140B tokens），并在 3-6 周内完成。

---

## 2. 推荐训练配置 (Recommended Training Configuration)

### 2.1 硬件配置

```yaml
# 推荐环境
cloud_provider: RunPod / Lambda Cloud
gpu_type: H100 SXM 80GB
gpu_count: 8  # 单节点
interconnect: NVLink (900 GB/s GPU-GPU)
cpu_ram: 512GB+
nvme_storage: 4TB+ (数据 + checkpoint)
```

### 2.2 训练超参数

```yaml
# training_config.yaml
model:
  name: "llama-7b-custom"
  params: 6.49B
  hidden_size: 4096
  num_layers: 32
  num_heads: 32
  num_kv_heads: 8  # GQA
  intermediate_size: 11008
  vocab_size: 100000
  max_seq_len: 4096

training:
  # 数据
  total_tokens: 200B  # 方案C（或 100B 方案D）
  
  # 批量大小
  micro_batch_size: 2  # per GPU
  gradient_accumulation_steps: 16
  global_batch_size: 256  # 2 × 8 × 16 = 256 sequences
  effective_batch_tokens: 1,048,576  # 256 × 4096 ≈ 1M tokens/step
  
  # 学习率
  optimizer: AdamW
  learning_rate: 3e-4
  min_learning_rate: 3e-5
  lr_scheduler: cosine
  warmup_steps: 2000
  weight_decay: 0.1
  beta1: 0.9
  beta2: 0.95
  eps: 1e-8
  
  # 精度
  precision: bf16  # 或 fp8 (若可用)
  gradient_clipping: 1.0
  
  # 分布式
  strategy: FSDP  # PyTorch FullyShardedDataParallel
  sharding_strategy: FULL_SHARD
  mixed_precision: bf16
  activation_checkpointing: false  # 7B 在 80GB H100 上不需要
  
  # 其他
  seed: 42
  compile: true  # torch.compile
  flash_attention: true
```

### 2.3 Checkpoint 策略

```yaml
checkpointing:
  # 频率
  save_interval_steps: 1000  # 每 1000 步保存
  save_interval_tokens: 1B   # 每 1B tokens 保存完整 checkpoint
  
  # 类型
  method: distributed  # PyTorch DCP (Distributed Checkpoint)
  format: sharded      # 每 GPU 只存自己的 shard
  
  # 存储
  local_path: /workspace/checkpoints/
  remote_path: s3://training-checkpoints/7b-pretrain/
  keep_last_n: 5         # 本地只保留最近 5 个
  remote_keep_all: true  # 远程保留全部
  
  # 中间评估 checkpoint
  eval_checkpoints:
    - 10B tokens
    - 25B tokens
    - 50B tokens
    - 100B tokens
    - 150B tokens
    - 200B tokens  # 最终
```

---

## 3. 数据配比策略 (Data Mixture Strategy)

### 3.1 推荐数据配比

基于 Llama 3, DeepSeek, YuLan-Mini 等最新研究：

```yaml
data_mixture:
  # 主体阶段 (0 - 180B tokens, 90%)
  main_phase:
    web_text: 0.50       # FineWeb-Edu (高质量网页文本)
    code: 0.20           # StarCoder (GitHub 代码)
    math: 0.08           # Nemotron-CC-Math + OpenWebMath
    books: 0.07          # Project Gutenberg + BookCorpus
    academic: 0.05       # ArXiv, S2ORC
    wikipedia: 0.05      # Wikipedia 多语言
    qa_forums: 0.05      # StackExchange, Reddit (高质量)
    
  # 退火阶段 (180B - 200B tokens, 10%) → Mid-training Annealing
  annealing_phase:
    high_quality_web: 0.30
    code: 0.25           # 提高代码比例
    math: 0.20           # 提高数学比例
    academic: 0.15       # 提高学术比例
    instruction_like: 0.10  # 自然指令风格文本
```

### 3.2 数据质量控制

1. **去重**: MinHash + SimHash 全局去重
2. **质量过滤**: 已建 `data/pipeline.py` (语言识别 → 质量过滤 → 去重 → PII 清洗)
3. **Tokenization**: 已训练 SentencePiece BPE (100k vocab)
4. **Packing**: Sequence packing with document separator tokens
5. **Shuffle**: 全局 shuffle 后分片存储

---

## 4. 训练监控体系 (Monitoring System)

### 4.1 WandB 监控指标

```yaml
monitoring:
  tool: wandb
  project: "7b-pretrain"
  
  metrics:
    # 核心指标
    - train/loss           # 训练损失（应平滑下降）
    - train/perplexity     # 困惑度
    - train/learning_rate  # 学习率曲线
    
    # 梯度健康
    - train/grad_norm      # 梯度范数（监控爆炸/消失）
    - train/grad_clip_ratio  # 梯度裁剪比例
    
    # 硬件效率
    - perf/tokens_per_sec  # 吞吐量
    - perf/mfu             # Model FLOPs Utilization
    - perf/gpu_memory_used # GPU 显存使用
    - perf/gpu_utilization # GPU 利用率
    
    # 数据
    - data/tokens_seen     # 已处理 token 数
    - data/epoch           # 数据 epoch 数
    
  alerts:
    - condition: "loss > 2x running_avg"
      action: "notify + save_checkpoint"
    - condition: "grad_norm > 100"
      action: "notify + investigate"
    - condition: "tokens_per_sec < 0.7 * baseline"
      action: "notify (可能硬件问题)"
    - condition: "loss is NaN"
      action: "halt + rollback to last checkpoint"
```

### 4.2 Loss Spike 处理流程

```
Loss Spike 检测到
    │
    ├── 轻微 spike (< 2x avg, 自行恢复)
    │   └── 记录, 继续训练
    │
    ├── 中等 spike (2-5x avg)
    │   ├── 检查 gradient norm
    │   ├── 检查 batch 内容 (是否有异常数据)
    │   ├── 观察 5-10 步是否恢复
    │   └── 若不恢复 → 回滚到最近 checkpoint, 跳过问题数据
    │
    └── 严重 spike (> 5x avg 或 NaN)
        ├── 立即停止训练
        ├── 回滚到最近健康 checkpoint
        ├── 降低学习率 (0.5x-0.8x)
        └── 排查数据质量问题
```

### 4.3 常见问题排查

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| Loss 突然飙升 | 异常数据 / LR 过高 | 跳过数据 / 降 LR |
| Loss 停止下降 | LR 过低 / 数据耗尽 | 检查 LR schedule / 数据 |
| 梯度范数突增 | 梯度爆炸 | 降低 grad_clip / 检查数据 |
| MFU 下降 | 热节流 / 通信瓶颈 | 检查 GPU 温度 / 网络 |
| Checkpoint 失败 | 磁盘满 | 清理旧 checkpoint / 扩容 |
| NCCL 超时 | GPU 故障 / 网络中断 | 重启训练, 检查硬件 |

---

## 5. 故障恢复策略 (Fault Tolerance & Recovery)

### 5.1 Checkpoint 恢复流程

```bash
# 自动恢复脚本 (scripts/auto_resume.sh)
#!/bin/bash
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    python train.py \
        --config configs/pretrain_7b.yaml \
        --resume_from_checkpoint auto \  # 自动找最新 checkpoint
        --wandb_resume must
    
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "Training completed successfully"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Training crashed (exit=$EXIT_CODE), retry $RETRY_COUNT/$MAX_RETRIES"
    sleep 60  # 等待 1 分钟再重试
done
```

### 5.2 关键保护措施

1. **异步 Checkpoint**: 使用 `torch.distributed.checkpoint` 的异步保存，不阻塞训练
2. **Checkpoint 验证**: 每次保存后验证 checkpoint 完整性
3. **远程备份**: 每个 checkpoint 同步到 S3/GCS
4. **健康检查**: 每 100 步检查 GPU 状态 (温度、显存、利用率)
5. **Watchdog**: 监控进程，10 分钟无进展自动重启

---

## 6. 训练执行时间线 (Execution Timeline)

### 方案 C: 200B tokens, 8×H100

```
预计总步数: 200B / 1M = 200,000 步
预计训练时间: ~39 天
预计成本: ~$12,000 (按 $2/hr/GPU × 8 GPU × 39 天 × 24hr)

Week 1 (Day 1-7):
  - Day 1: 环境部署, 启动训练
  - Day 1-2: Warmup 阶段 (2000 步)
  - Day 2-7: 主训练阶段 ~35,000 步 (~35B tokens)
  - Checkpoint: 10B, 25B, 35B
  
Week 2-3 (Day 8-21):
  - 持续训练到 ~105B tokens
  - Checkpoint: 50B, 75B, 100B
  - 中期评估: 在 50B 和 100B checkpoint 上跑 benchmark
  
Week 4-5 (Day 22-35):
  - 继续训练到 ~180B tokens (主阶段结束)
  - Checkpoint: 125B, 150B, 175B, 180B
  
Week 5-6 (Day 35-39):
  - 退火阶段 (Annealing): 180B → 200B
  - LR 从 3e-5 降至 3e-6
  - 高质量数据子集 (STEM + Code)
  - 最终 Checkpoint: 200B
  
Week 6: 
  - 评估与分析
  - MMLU, HumanEval, GSM8K benchmark
  - 报告输出
```

### 方案 D: 100B tokens, 8×H100 (更经济)

```
预计总步数: 100,000 步
预计训练时间: ~19 天 (~3 周)
预计成本: ~$6,000

更适合预算有限的情况, 但 token 量低于 Chinchilla 最优比
```

---

## 7. 预期结果与评估 (Expected Results)

### 7.1 Loss 预期

- **初始 Loss**: ~11-12 (随机初始化, vocab=100k → ln(100000) ≈ 11.5)
- **Warmup 后**: ~7-8
- **训练 50B tokens 后**: ~3.5-4.0
- **训练 100B tokens 后**: ~3.0-3.3
- **训练 200B tokens 后**: ~2.7-2.9

### 7.2 Benchmark 预期 (200B tokens)

| Benchmark | Llama 2 7B (2T tokens) | 预期 (200B tokens) |
|-----------|----------------------|-------------------|
| MMLU (5-shot) | 0.47 | 0.30-0.35 |
| HellaSwag | 0.76 | 0.55-0.65 |
| ARC-Challenge | 0.46 | 0.35-0.40 |
| GSM8K (8-shot) | 0.13 | 0.02-0.05 |
| HumanEval | ~0.12 | 0.05-0.08 |

注: 200B tokens 的模型性能会明显低于 2T tokens 训练的 Llama 2，这是正常的。主要目的是验证训练流程的完整性。

---

## 8. 关键风险与缓解 (Risks & Mitigations)

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| GPU 故障 (单卡) | 训练中断 | 自动恢复脚本 + 频繁 checkpoint |
| 云实例被抢占 | 训练中断 | 使用 on-demand 实例 / 多云备份 |
| 数据质量问题 | Loss spike | 预先全量数据扫描 + 异常检测 |
| 磁盘空间不足 | Checkpoint 丢失 | 定期清理 + 远程备份 (IBM 经验教训) |
| 训练不稳定 | 浪费计算 | Gradient clipping + LR warmup + z-loss |
| 超预算 | 资金不足 | 先跑方案 D (100B), 评估后决定是否继续 |

---

## 9. 启动前检查清单 (Pre-Launch Checklist)

- [ ] 数据集准备完毕 (tokenized, sharded, 存储到 NVMe)
- [ ] Docker 镜像构建并测试
- [ ] 训练脚本在 8×H100 上完成 100 步测试
- [ ] WandB 项目创建并配置告警
- [ ] S3/GCS bucket 创建用于 checkpoint 备份
- [ ] 自动恢复脚本测试通过
- [ ] 磁盘空间预算确认 (至少 4TB)
- [ ] 成本预算确认并审批
- [ ] 评估脚本准备就绪 (lm-evaluation-harness)

---

## 10. 总结与建议

### 核心结论

1. **5T tokens 在 8×H100 上不可行** — 需要 ~965 天，远超合理时间范围
2. **推荐缩减到 100-200B tokens** — 接近 Chinchilla 最优比 (7B × 20 = 140B)，3-6 周可完成
3. **如需 2T+ tokens**，需要至少 64-128 GPU 的多节点集群

### 行动建议

1. **短期 (下一步)**: 在 8×H100 上执行 100-200B tokens 训练 (方案 C/D)
2. **中期**: 评估结果后，决定是否扩大到多节点进行更大规模训练
3. **长期**: 如果模型质量满意，进入 Phase 4 (视觉扩展) 或 Phase 5 (评估)

### 参考资料

- [PyTorch FSDP Maximizing Training Throughput](https://pytorch.org/blog/maximizing-training/)
- [Databricks H100 Benchmarking](https://www.databricks.com/blog/coreweave-nvidia-h100-part-1)
- [IBM fms-fsdp](https://github.com/foundation-model-stack/fms-fsdp)
- [Spike No More: Stabilizing LLM Pre-training](https://openreview.net/forum?id=52YBEzcI0l)
- [SPAM: Spike-Aware Adam with Momentum Reset](https://www.rohan-paul.com/p/stabilizing-llm-training-techniques)
- [RunPod H100 Training Guide](https://www.runpod.io/articles/guides/training-llms-h100-pcle-gpus)
- [FlashRecovery: Fast Recovery for LLM Training](https://arxiv.org/html/2509.03047)
- Llama 1/2/3 技术报告 (Meta)
