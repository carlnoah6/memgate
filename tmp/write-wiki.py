#!/usr/bin/env python3
"""Write the 1B Token Club research report to Lark Wiki document."""

import json
import requests
import time
import sys

TOKEN = json.load(open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json'))['access_token']
DOC = "GtIudQ8sPoCtBVxc47olz1dPgMb"
BASE = f"https://open.larksuite.com/open-apis/docx/v1/documents/{DOC}/blocks/{DOC}/children"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# block_type mapping:
# 2 = text (paragraph)
# 3 = heading1, field "heading1"
# 4 = heading2, field "heading2"
# 5 = heading3, field "heading3"
# 6 = heading4, field "heading4"
# ...

def h1(text):
    return {"block_type": 3, "heading1": {"elements": [{"type": "text_run", "text_run": {"content": text}}]}}

def h2(text):
    return {"block_type": 4, "heading2": {"elements": [{"type": "text_run", "text_run": {"content": text}}]}}

def h3(text):
    return {"block_type": 5, "heading3": {"elements": [{"type": "text_run", "text_run": {"content": text}}]}}

def para(text):
    return {"block_type": 2, "text": {"elements": [{"type": "text_run", "text_run": {"content": text}}]}}

def bold_para(bold_text, normal_text=""):
    elements = [{"type": "text_run", "text_run": {"content": bold_text, "text_element_style": {"bold": True}}}]
    if normal_text:
        elements.append({"type": "text_run", "text_run": {"content": normal_text}})
    return {"block_type": 2, "text": {"elements": elements}}

def write_blocks(blocks, index):
    payload = {"children": blocks, "index": index}
    resp = requests.post(BASE, headers=HEADERS, json=payload)
    data = resp.json()
    if data.get("code") != 0:
        print(f"  ERROR at index {index}: {data}")
        return False
    print(f"  ✓ Wrote {len(blocks)} blocks at index {index}")
    return True

# Build all content blocks
B = []

B.append(h1("每天消耗 1B Token 的 AI 系统架构研究"))
B.append(para("研究日期: 2026-02-09 | 研究者: Luna (子代理)\n目标: 设计一个每天稳定消耗 10 亿（1B = 1,000,000,000）token 的 AI 系统"))

# 摘要
B.append(h2("摘要"))
B.append(para("每天 1B token ≈ 每秒 11,574 tokens（假设 24h 不间断），≈ 每分钟 694,444 tokens。这是一个工业级吞吐量，需要精心设计的多模型混合架构。本报告从供给端成本、系统架构、需求挖掘三个维度给出完整分析，并提供分阶段实施路线图。"))

# 一、供给端
B.append(h2("一、供给端：Token 来源与成本"))
B.append(h3("1.1 主流模型 API 定价对比（2026年2月）"))

B.append(bold_para("旗舰级模型："))
B.append(para(
    "• Claude Opus 4.5 — 输入 $5.00/M | 输出 $25.00/M | 缓存 $0.50 | Batch 50%\n"
    "• Claude Sonnet 4.5 — 输入 $3.00/M | 输出 $15.00/M | 缓存 $0.30 | Batch 50%\n"
    "• GPT-5 (Batch) — 输入 $0.625/M | 输出 $5.00/M | 缓存 $0.0625 | 已含50%折扣\n"
    "• Gemini 3 Pro Preview — 输入 $2.00/M | 输出 $12.00/M | Batch 50%"
))

B.append(bold_para("高性价比模型："))
B.append(para(
    "• Claude Haiku 4.5 — 输入 $1.00/M | 输出 $5.00/M | 缓存 $0.10 | Batch 50%\n"
    "• GPT-5-mini (Batch) — 输入 $0.125/M | 输出 $1.00/M | 已含50%折扣\n"
    "• GPT-4.1-mini — 输入 $0.40/M | 输出 $1.60/M | Batch 50%\n"
    "• Gemini 2.5 Pro — 输入 $1.25/M | 输出 $10.00/M | 缓存 $0.30 | Batch 50%\n"
    "• Kimi K2 — 输入 $0.60/M | 输出 $2.50/M | 缓存 $0.15"
))

B.append(bold_para("极致低价模型："))
B.append(para(
    "• GPT-5-nano (Batch) — 输入 $0.025/M | 输出 $0.20/M | 最便宜 OpenAI\n"
    "• GPT-4.1-nano — 输入 $0.10/M | 输出 $0.40/M | 极致成本\n"
    "• Gemini 2.5 Flash — 输入 $0.15/M | 输出 $0.60/M | 超高性价比\n"
    "• Gemini 2.5 Flash-Lite — 输入 $0.10/M | 输出 $0.40/M | 最便宜\n"
    "• DeepSeek V3.2 — 输入 $0.28/M (miss) | 输出 $0.42/M | 性价比极致"
))

B.append(h3("1.2 1B Token/Day 成本估算"))
B.append(para("假设输入:输出比例 = 70:30（700M 输入 + 300M 输出）"))
B.append(para(
    "• 纯 GPT-5-nano Batch — $78/天 | $2,325/月 | ~$28K/年\n"
    "• Gemini Flash-Lite Batch — $95/天 | $2,850/月 | ~$35K/年\n"
    "• 纯 Gemini Flash-Lite — $190/天 | $5,700/月 | ~$69K/年\n"
    "• 纯 DeepSeek V3.2 (50% cache) — $234/天 | $7,020/月 | ~$85K/年\n"
    "• 纯 DeepSeek V3.2 (cache miss) — $322/天 | $9,660/月 | ~$117K/年\n"
    "• Claude Haiku 4.5 — $2,200/天 | $66,000/月 | ~$800K/年\n"
    "• GPT-5 Batch — $1,938/天 | $58,125/月 | ~$700K/年\n"
    "• Claude Sonnet 4.5 — $6,600/天 | $198,000/月 | ~$2.4M/年"
))

B.append(h3("🎯 推荐混合策略"))
B.append(para("按任务复杂度路由，混合多个价位的模型："))
B.append(para(
    "• 60% (600M tok) → GPT-5-nano / Gemini Flash-Lite (Batch) — 简单分类、提取、格式化 → ~$60/天\n"
    "• 25% (250M tok) → DeepSeek V3.2 / GPT-4.1-mini — 中等复杂度推理 → ~$130/天\n"
    "• 10% (100M tok) → Claude Sonnet 4.5 / Gemini 2.5 Pro — 复杂分析 → ~$180/天\n"
    "• 5% (50M tok) → Claude Opus 4.5 / GPT-5 — 最高难度推理 → ~$175/天"
))
B.append(bold_para("混合策略总日成本：~$545/天 = ~$16,350/月 = ~$199K/年"))

B.append(h3("1.3 开源模型自托管 vs API 对比"))
B.append(para(
    "使用 Llama 3.1 70B-AWQ 在 H100 上运行：\n"
    "• 吞吐量：~1,000 tok/s/GPU (连续批处理)\n"
    "• 每 GPU 每天产出：86.4M tokens\n"
    "• 达到 1B/天需要：≈12 张 H100\n"
    "• 12×H100 月租金（RunPod）：$17,196/月\n"
    "• 等效 token 单价：$0.57/M tokens"
))
B.append(para(
    "结论：对于旗舰级模型（Claude Sonnet/Opus, GPT-5），自托管开源模型性价比更高。"
    "但对于已经极低价的 API（DeepSeek、GPT-5-nano、Gemini Flash-Lite），API 胜出，因为省去运维。"
))

# 二、架构设计
B.append(h2("二、架构设计：多 Agent 协调系统"))

B.append(h3("2.1 系统整体架构"))
B.append(para(
    "Central Orchestrator（任务调度、模型路由、成本监控、熔断管理）\n"
    "  ├── Task Queue (Redis/NATS)\n"
    "  ├── Model Router (智能路由)\n"
    "  └── Cost Tracker (实时成本监控)\n\n"
    "Agent Pool (分层执行)\n"
    "  ├── Planner (规划者) — 5% token\n"
    "  ├── Worker (执行者) — 85% token\n"
    "  └── Reviewer (验证者) — 10% token\n\n"
    "Model Backend Pool\n"
    "  ├── DeepSeek V3.2 (bulk) | GPT-5 nano/mini (batch)\n"
    "  ├── Gemini Flash Lite | Claude Haiku 4.5\n"
    "  ├── Claude Opus 4.5 (premium) | GPT-5 (premium)\n"
    "  └── Self-hosted Llama 70B"
))

B.append(h3("2.2 任务队列设计"))
B.append(para(
    "优先级定义：\n"
    "• CRITICAL (P0) — 用户直接请求，实时需要\n"
    "• HIGH (P1) — 时效性任务（新闻分析、漏洞检测）\n"
    "• MEDIUM (P2) — 常规批处理（代码分析、文档生成）\n"
    "• LOW (P3) — 后台填充（知识图谱、数据清洗）\n"
    "• IDLE (P4) — 闲时任务（创意生成、模拟对话）\n\n"
    "队列策略：\n"
    "• 实时队列 (5%) — 直接调用 API，走标准定价\n"
    "• 准实时队列 (15%) — 小批量聚合（1-5分钟窗口），走 Flex 定价\n"
    "• 批处理队列 (80%) — 大批量聚合（1-24小时窗口），走 Batch API（50%折扣）"
))

B.append(h3("2.3 Agent 分层架构"))
B.append(para(
    "Planner（规划者）：使用 Claude Sonnet 4.5 / GPT-5，消耗 ~5% (50M/day)。接收高级任务，拆解为子任务，分配优先级和复杂度标签。\n\n"
    "Worker（执行者）：根据复杂度路由（nano → mini → standard → premium），消耗 ~85% (850M/day)。执行具体任务，高吞吐大量并行。\n\n"
    "Reviewer（验证者）：使用 Claude Haiku 4.5 / GPT-4.1-mini，消耗 ~10% (100M/day)。质量检查、一致性验证、结果评分。"
))

B.append(h3("2.4 智能模型路由"))
B.append(para(
    "• complexity < 0.2 → gpt-5-nano-batch / gemini-flash-lite（简单分类、提取）\n"
    "• complexity 0.2-0.5 → gpt-5-mini-batch / deepseek-v3.2（摘要、翻译）\n"
    "• complexity 0.5-0.8 → claude-sonnet-4.5（代码生成、深度分析）\n"
    "• complexity > 0.8 → claude-opus-4.5（架构设计、科研推理）"
))

B.append(h3("2.5 并行与调度"))
B.append(para(
    "• 每天请求数：~400,000 (avg 2,500 tok/req)\n"
    "• 每秒请求数：~4.6 requests/second\n"
    "• 实时并发：~10 个并行请求\n"
    "• Batch：每小时打包 ~13,333 个请求提交"
))

B.append(h3("2.6 错误处理与韧性"))
B.append(para(
    "降级链：\n"
    "• Claude Opus 4.5 → GPT-5 → Claude Sonnet 4.5 → Gemini 3 Pro\n"
    "• Claude Sonnet 4.5 → GPT-4.1 → Gemini 2.5 Pro → DeepSeek V3.2\n"
    "• GPT-5-nano Batch → Gemini Flash-Lite Batch → DeepSeek V3.2\n\n"
    "熔断器：连续 5 次失败触发 → 60s 恢复超时 → 半开状态 3 个探测请求\n\n"
    "重试策略：429 指数退避+切换模型 | 500 重试3次 | 超时降级 | 成本超限暂停非关键任务"
))

# 三、需求挖掘
B.append(h2("三、需求挖掘：24/7 有意义的工作"))

B.append(h3("Token 消耗分配计划"))
B.append(para(
    "• 代码分析 25% (250M/天) — 开源仓库审计、漏洞检测、文档生成\n"
    "• 知识处理 25% (250M/天) — 论文阅读、网页分析、知识图谱\n"
    "• 数据处理 20% (200M/天) — 数据清洗、标注、格式转换\n"
    "• 创意生成 15% (150M/天) — 内容生成、对话模拟、训练数据\n"
    "• 研究辅助 10% (100M/天) — 假设验证、文献综述、实验设计\n"
    "• 系统运维 5% (50M/天) — 自检、报告、监控分析"
))

B.append(h3("具体任务流水线"))
B.append(para(
    "🔧 代码分析 (250M tok/天)：每天分析 ~4,000 个文件，漏洞检测，API 文档生成，PR diff 分析。\n\n"
    "📚 知识处理 (250M tok/天)：每天处理 ~7,000 篇论文摘要，~200 篇深度分析，~5,000 篇网页内容分析。\n\n"
    "🗃️ 数据处理 (200M tok/天)：数据清洗标准化，多语言翻译，PDF→Markdown 转换，情感分析标注。\n\n"
    "🎨 创意生成 (150M tok/天)：多轮对话模拟，角色扮演数据，技术文章和教程生成。\n\n"
    "🔬 研究辅助 (100M tok/天)：自动化文献综述，假设验证，实验设计，技术趋势跟踪。"
))

# 四、关键数字
B.append(h2("四、关键数字总结"))

B.append(h3("核心指标"))
B.append(para(
    "• 每日目标：1,000,000,000 tokens\n"
    "• 每秒吞吐：~11,574 tokens\n"
    "• 每日请求数：~400,000 (avg 2.5K tok/req)\n"
    "• 并发请求数：~10 (实时) + Batch\n"
    "• 日成本（最低）：~$78 (纯 GPT-5-nano Batch)\n"
    "• 日成本（推荐混合）：~$545\n"
    "• 日成本（高质量混合）：~$2,000-3,000\n"
    "• 月成本范围：$2,300 - $90,000"
))

B.append(h3("不同预算的方案"))
B.append(para(
    "• $2,500/月 — 100% GPT-5-nano Batch — ⭐⭐ 基础\n"
    "• $5,000/月 — 80% nano/Flash-Lite + 20% mini — ⭐⭐⭐ 可用\n"
    "• $15,000/月 — 推荐混合策略 — ⭐⭐⭐⭐ 良好\n"
    "• $50,000/月 — 高质量混合 + 旗舰模型占比提升 — ⭐⭐⭐⭐⭐ 优秀\n"
    "• $100,000/月 — 全旗舰 + 自托管 70B 补充 — 🌟 极致"
))

# 五、路线图
B.append(h2("五、分阶段实施路线图"))

B.append(bold_para("Phase 0: 原型验证（第 1-2 周）"))
B.append(para(
    "目标：1M tokens/day | 成本：~$1/天\n"
    "• 搭建基础任务队列（Redis + Python worker）\n"
    "• 单模型测试（DeepSeek V3.2 API）\n"
    "• 定义 5 个核心任务类型\n"
    "• 监控仪表板（Grafana/简单 dashboard）"
))

B.append(bold_para("Phase 1: 小规模运行（第 3-4 周）"))
B.append(para(
    "目标：10M tokens/day | 成本：~$5-10/天\n"
    "• 多模型路由（2-3 个 API）\n"
    "• Batch API 集成\n"
    "• 自动化任务发现（GitHub API, arXiv RSS）\n"
    "• 结果存储和索引（PostgreSQL + 向量数据库）"
))

B.append(bold_para("Phase 2: 百倍扩展（第 5-8 周）"))
B.append(para(
    "目标：100M tokens/day | 成本：~$50-100/天\n"
    "• 完整的 5 个 API 提供商集成\n"
    "• Agent 分层架构（Planner/Worker/Reviewer）\n"
    "• 熔断器和降级机制\n"
    "• 成本实时监控和预警"
))

B.append(bold_para("Phase 3: 达成目标（第 9-12 周）"))
B.append(para(
    "目标：1B tokens/day | 成本：~$500-600/天\n"
    "• 10x 并发扩展\n"
    "• 全量任务流水线上线\n"
    "• 缓存优化（prompt caching 利用率 >50%）\n"
    "• 自托管开源模型节点上线（可选）"
))

B.append(bold_para("Phase 4: 稳态运营（持续）"))
B.append(para(
    "目标：稳定 1B+/day\n"
    "• A/B 测试不同模型效果\n"
    "• 任务质量自动评估\n"
    "• 新模型自动纳入路由池\n"
    "• 成本持续优化 | 知识库持续膨胀和利用"
))

# 六、技术栈
B.append(h2("六、技术栈建议"))
B.append(para(
    "• 任务队列：Redis + Bull/BullMQ（备选 NATS, RabbitMQ）\n"
    "• 编排引擎：Python (asyncio) + FastAPI（备选 Node.js）\n"
    "• 数据库：PostgreSQL + pgvector（备选 Supabase）\n"
    "• 向量存储：Qdrant / Weaviate（备选 Pinecone, Milvus）\n"
    "• 监控：Prometheus + Grafana（备选 DataDog）\n"
    "• 日志：Structured JSON → ElasticSearch（备选 Loki）\n"
    "• 部署：Docker Compose → K8s（备选 Railway, Fly.io）\n"
    "• 成本追踪：自建 Dashboard（备选 LangSmith, Helicone）"
))

# 七、风险
B.append(h2("七、风险与缓解"))
B.append(para(
    "• API 价格上涨 → 多供应商冗余 + 自托管兜底\n"
    "• 速率限制收紧 → 多账号 + Batch API + 自托管\n"
    "• 模型质量下降 → Reviewer 自动检测 + 切换模型\n"
    "• 服务宕机 → 多供应商 failover + 队列持久化\n"
    "• Token 浪费 → 定期审计任务有效性和输出质量"
))

# 八、结论
B.append(h2("八、结论"))
B.append(para(
    "构建每天消耗 1B token 的 AI 系统在 2026 年完全可行，核心发现：\n\n"
    "1. 成本已经很低：纯粹最低价路线仅需 ~$78/天（GPT-5-nano Batch），推荐混合策略约 $545/天\n"
    "2. Batch API 是关键：50% 的折扣对大规模消耗至关重要，80% 的任务可以异步处理\n"
    "3. 智能路由必不可少：60% 的 token 可以用最便宜的模型处理，仅 5% 需要旗舰模型\n"
    "4. DeepSeek 是性价比冠军：$0.28/$0.42 的定价在中等复杂度任务上无可匹敌\n"
    "5. 需求不是瓶颈：代码分析、论文处理、数据清洗等任务源几乎无限\n"
    "6. 3个月可达成目标：从 0 到 1B/day 的路径清晰，分 4 个阶段渐进"
))
B.append(bold_para("建议立即开始 Phase 0，$1/天的成本即可验证核心架构。"))
B.append(para("报告结束 | Luna 子代理 | 2026-02-09"))

# Write in batches of 50
print(f"Total blocks: {len(B)}")
idx = 0
for i in range(0, len(B), 50):
    batch = B[i:i+50]
    print(f"\nBatch {i//50+1}: {len(batch)} blocks at index {idx}...")
    if not write_blocks(batch, idx):
        sys.exit(1)
    idx += len(batch)
    time.sleep(0.5)

print(f"\n✅ Done! {len(B)} blocks written.")
