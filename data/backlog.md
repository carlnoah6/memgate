# Backlog - Luna 后台任务队列

优先级：P0（紧急）> P1（重要）> P2（一般）> P3（探索）

## 待办

### 🔧 OpenClaw 优化

#### Privacy Guard — 多用户隐私隔离框架
- [x] 1. 调研现有方案 ✅ 2026-02-10 → 无现有插件，学术论文 Collaborative Memory (arxiv 2505.18279) 最相关
- [x] 2. 设计框架文档 ✅ 2026-02-10 → `docs/privacy-framework.md` + [Wiki](https://fg9w9yu3odc.sg.larksuite.com/wiki/D1GEwdu2EiTmA3kI63KlDQEageb)
- [x] 3. 核心模块（知识存储 + 上下文隔离 + 输出审查）✅ 2026-02-10 → `privacy/`
- [x] 4. 自我攻防测试（18/18 通过）✅ 2026-02-10 → `privacy/tests/test_isolation.py`
- [ ] 5. 集成到 Luna 实际运行（session 注入 + memory_search 过滤）
- [ ] 6. 抽象为通用 OpenClaw 插件并发布

#### API 代理层 Fallback — 到限额自动切换
- **问题**：OpenClaw 内置 fallback 机制有严重问题
  - 切换慢：额度用完后反复聊天仍用旧模型
  - 状态不稳定：成功切到备用模型后又会自动切回去
- **方案**：在 api-proxy 层实现 fallback
  - 代理收到 429/额度用尽错误 → 自动切备用 key/endpoint → 重试
  - 对 OpenClaw 完全透明，无需感知
- **位置**：`/home/ubuntu/api-proxy/server.py`
- **状态**：待实现
- **记录日期**：2026-02-09

#### 重启来源追踪 & 回复路由
- **问题**：重启可能从任何 session 触发，但重启后汇报只回到主 session
- **方案**：`mark-restart.sh` 记录触发来源，重启后路由到正确 session
- **状态**：待实现
- **记录日期**：2026-02-09

#### 🚀 每天消耗 1B Token 的 AI 系统架构
- [x] 1. 供给端分析 ✅ 2026-02-09 → `memory/research/1b-token-daily-architecture-2026-02-09.md`
- [x] 2. 架构设计 ✅ 2026-02-09 → 同上
- [x] 3. 需求挖掘 ✅ 2026-02-09 → 同上
- [x] 4. 成本优化 ✅ 2026-02-09 → 同上
- [x] 5. 实施路线图 ✅ 2026-02-09 → 同上
  - Wiki: `V2hNwrjTtipsdLk0fVKlBjGQgcz` (doc: `GtIudQ8sPoCtBVxc47olz1dPgMb`) — 格式修复中

#### 🧠 从零训练 LLM + 视觉模型（大项目）
- [x] 1. LLM 架构综述：Transformer 变体、Mamba/SSM、MoE，当前 SOTA 选型建议 ✅ 2026-02-08 → `memory/research/llm-architecture-survey-2026-02-08.md`
- [x] 2. 训练数据：公开数据集全景（CommonCrawl、RedPajama、FineWeb 等）、数据清洗流程、数据配比策略 ✅ 2026-02-08 → `memory/research/llm-training-data-guide-2026-02-08.md`
- [x] 3. Tokenizer 设计：BPE vs SentencePiece vs Unigram，中英文混合 tokenizer 方案 ✅ 2026-02-08 → `memory/research/tokenizer-design-2026-02-08.md` + Wiki 节点 NIjpwPJ8RieE2Nkh6ERlEWFUgog
- [x] 4. 训练框架对比：PyTorch + FSDP、DeepSpeed、Megatron-LM、JAX/TPU，各自优劣 ✅ 2026-02-08 → `memory/research/llm-training-framework-comparison-2026-02-08.md` + Wiki节点 C6KkwspVviOnxJk4jGsl10eigqL
- [x] 5. 硬件与成本分析：GPU（H100/A100/4090）vs TPU，不同规模（1B/7B/13B/70B）的算力需求和预算估算 ✅ 2026-02-08 → `memory/research/hardware-cost-analysis-2026-02-08.md` + Wiki节点 Q8fkwEORoiqMeJka5e6luTaxgKc
- [x] 6. Scaling Laws 研究：Chinchilla 定律、compute-optimal 训练策略、小模型高效训练路线 ✅ 2026-02-08 → `memory/research/scaling-laws-research-2026-02-08.md` + Wiki节点 Avc4wZXJYibY9Ikp9xHl5F3ig6c
- [x] 7. 训练技巧：学习率调度、梯度累积、混合精度、checkpoint 策略 ✅ 2026-02-08 → `memory/research/training-techniques-2026-02-08.md` + Wiki节点 JlY7wFLp8iGTvgkUWrAlAmHPgyc
- [x] 8. 对齐与后训练：SFT、RLHF、DPO、Constitutional AI，各方法对比 ✅ 2026-02-08 → `memory/research/alignment-post-training-2026-02-08.md` + Wiki节点 C11RwsQbAiZ63pk4gk8lGHMBgPd
- [x] 9. 评估体系：Benchmark 选择（MMLU、HumanEval、GSM8K 等）、评估框架搭建 ✅ 2026-02-08 → `memory/research/llm-evaluation-system-2026-02-08.md` + Wiki节点 RGnhwXhqriKKuekERtjlXEYdgzd
- [x] 10. 视觉模型架构：ViT、SigLIP、InternVL，视觉-语言对齐方案（LLaVA 路线 vs Flamingo 路线） ✅ 2026-02-08 → `memory/research/vision-model-architecture-2026-02-08.md` + Wiki节点 KRtTwAqASi7snLkhhPKleR4ygre
- [x] 11. 视觉数据集：图文配对数据（LAION、DataComp）、合成数据生成 ✅ 2026-02-08 → `memory/research/vision-datasets-2026-02-08.md` + Wiki节点 B6pewPsOlir7vFklaVXlUOIFgGb
- [x] 12. 多模态融合：视觉 encoder + LLM 的连接方式、训练阶段划分 ✅ 2026-02-08 → `memory/research/multimodal-fusion-2026-02-08.md` + Wiki节点 GPslwFbOdiNtn1kipNXlsxRkgPb
- [x] 13. 端到端路线图：从零到可用模型的完整 step-by-step 计划 ✅ 2026-02-08 → `memory/research/end-to-end-roadmap-2026-02-08.md` + Wiki节点 IbcEwOXWrifarxkWO1alI9sSgYf

#### 其他 P1
- [x] 研究 Balatro（小丑牌）的游戏机制和 AI 策略，整理成文档 ✅ 2026-02-08 → `memory/research/balatro-game-mechanics-ai-strategy-2026-02-08.md`
- [x] 整理 Luna 系统架构文档（当前的 cron 任务、权限、工具链全景图） ✅ 2026-02-08 → `memory/research/luna-system-architecture-2026-02-08.md`
- [x] 优化日报质量：研究更好的时间分析和复盘框架 ✅ 2026-02-08 → `memory/research/daily-report-optimization-2026-02-08.md`

### P2 - 一般
- [x] 研究 Lark API 最佳实践（批量操作、性能优化、错误处理） ✅ 2026-02-08 → `memory/research/lark-api-best-practices-2026-02-08.md`
- [x] 整理 Carl 的人脉网络可视化方案 ✅ 2026-02-08 → `memory/research/contact-network-visualization-2026-02-08.md`
  - Wiki: 不需要（内部参考）
- [x] 探索 token 用量优化策略（缓存、压缩上下文等） ✅ 2026-02-08 → `memory/research/token-optimization-strategies-2026-02-08.md`
  - Wiki: 不需要（内部参考）

### P3 - 探索
- [x] 调研有什么好用的个人生产力工具可以集成 ✅ 2026-02-08 → `memory/research/productivity-tools-survey-2026-02-08.md`
  - Wiki: 不需要（内部参考）
- [x] 研究 OpenClaw 社区有什么新的 skill 可以用 ✅ 2026-02-08 → `memory/research/openclaw-skills-survey-2026-02-08.md`
  - Wiki: 不需要（内部参考）

## Wiki 目标映射（子任务参考）

| 项目 | Wiki Space | 父节点 node_token | 说明 |
|------|-----------|-------------------|------|
| 从零训练模型 | 7604150806383693538 | OZmqwn4yviwsY2k1JBblkgTYg5c | Carl 私人知识库 → AI 研究 → 从头训练模型 |
| AI 玩小丑牌 | 7604150806383693538 | HDiUwEllbiJIdskrKAZlojadgsc | Carl 私人知识库 → AI 研究 → 小丑牌 |
| 1B Token 俱乐部 | 7604150806383693538 | V2hNwrjTtipsdLk0fVKlBjGQgcz | Carl 私人知识库 → AI 研究 → 1B Token 俱乐部 |
| OpenClaw 优化 | 7604126789916479197 | IUBdwFzDhisMDrkm1fAltnOhgGd | Luna 协同知识库 → OpenClaw 优化 |
| 内部参考文档 | — | — | 不上传 Wiki，仅存本地 |

## 消息目标映射（子任务参考）

| 目标 | chat_id | 说明 |
|------|---------|------|
| Carl 私聊 | oc_453c88ec52dd029845c46249837e3ba0 | 一对一任务结果 |
| Luna 群聊 | oc_a2a70c6b4a29c2f2eb6c2500ea42a500 | 群聊任务结果 |

## 已完成
（完成的任务移到这里，附上完成日期和成果文件路径）
