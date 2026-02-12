# 代码地图 — Luna 自研代码

> 生成时间：2026-02-12 08:15 SGT
> 扫描范围：workspace/scripts, workspace/patches, workspace/data, workspace/privacy, ~/api-proxy, ~/webhook-gateway, ~/feishu-original-backup

---

## 模块 1: Lark/飞书集成

飞书 API 封装层，包括消息发送、日历操作、Wiki 同步、交互卡片、OAuth 等。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/lark-send-message.sh` | 139 | 飞书消息发送（text/post 富文本） |
| `scripts/lark-token-refresh.py` | 71 | OAuth token 刷新 |
| `scripts/oauth-callback.py` | 85 | OAuth 回调处理 |
| `scripts/lark-calendar-today.py` | 279 | 查询今日日历（支持重复事件/时区） |
| `scripts/lark-calendar-create.py` | 82 | 创建日历事件 |
| `scripts/lark-calendar-fix-colors.py` | 103 | 日历颜色修复 |
| `scripts/skip-recurring-dates.py` | 133 | 跳过循环日程的指定日期 |
| `scripts/lark-card-builder.py` | 319 | 看板卡片构建器（仪表盘用） |
| `scripts/lark-task-card.py` | 291 | 任务卡片（Lark 交互卡片） |
| `scripts/lark-task-dashboard.py` | 161 | 仪表盘卡片发送/更新 |
| `scripts/lark-lookup-chat.py` | 78 | 群名查 chat_id |
| `scripts/send-confirm-card.sh` | 88 | 确认卡片发送 |
| `scripts/send-diagram.sh` | 129 | 生成并发送图表到 Lark |
| `scripts/md-to-lark-post.py` | 126 | Markdown → Lark Post 格式 |
| `scripts/md-to-lark-wiki.py` | 217 | Markdown → Lark Wiki 格式 |
| `scripts/md-to-email-text.py` | 81 | Markdown → 纯文本邮件格式 |
| `scripts/rewrite-lark-doc.py` | 382 | 重写 Lark Wiki 文档（1B Token Club） |
| `scripts/rewrite-wiki-1b-token.py` | 404 | Wiki 内容重写工具 |
| `scripts/sync-md-to-wiki.py` | 229 | 本地 Markdown 同步到 Wiki |
| `scripts/sync-tracked-docs.py` | 156 | 同步追踪的文档 |
| `scripts/get-source-chat.py` | 62 | 从 message_id 反查 chat_id |
| `scripts/debug-group-members.py` | 83 | 调试群成员列表 |
| `scripts/check-group-privacy.py` | 129 | 群聊隐私检查 |
| `data/lark-secrets.json` | 4 | Lark 密钥配置 |
| `data/lark-user-token.json` | 7 | 用户 OAuth token |
| `data/lark-chats-cache.json` | 184 | 群聊缓存 |
| `data/lark-color-palette.json` | 24 | 日历颜色配置 |

### 统计
- **文件数**: 27
- **总行数**: ~4,186
- **最后修改**: 2026-02-12
- **代码质量**: ⚠️ `lark-send-message.sh` 较长(139行)可拆分；多个 sync 脚本有重复逻辑

---

## 模块 2: 任务管理系统

任务板、Planner（编排层）、任务生命周期管理、任务群聊等。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/task-manager.py` | 348 | 任务板 CLI 管理器 |
| `scripts/task_engine.py` | 938 | 统一任务管理引擎（v2） |
| `scripts/planner.py` | 1,034 | Planner 编排层（多步计划） |
| `scripts/spawn-task.py` | 434 | Spawn 子代理任务 |
| `scripts/task-health-check.py` | 117 | 任务健康检查（卡死检测） |
| `scripts/task-recovery.py` | 123 | 任务恢复 |
| `scripts/task-chat.py` | 187 | 任务群聊管理（创建/解散） |
| `scripts/cleanup-task-chats.py` | 258 | 清理旧任务群聊 |
| `scripts/task-board-notify.py` | 160 | 任务板状态推送到 Lark |
| `scripts/task-dashboard.py` | 59 | 任务仪表盘（轻量版） |
| `scripts/archive-backlog.py` | 182 | 归档 backlog |
| `data/task-board.json` | 252 | 任务板状态数据 |
| `data/task-card-state.json` | 4 | 卡片状态 |
| `data/task-board-notify-state.json` | 0 | 推送状态 |
| `data/spawn-task-footer.md` | 23 | Spawn 任务模板 |
| `data/backlog.md` | 86 | Backlog 列表 |
| `data/TODO.md` | 14 | TODO 列表 |

### 统计
- **文件数**: 17
- **总行数**: ~4,219
- **最后修改**: 2026-02-12
- **代码质量**: ⚠️ `planner.py`(1034行) 和 `task_engine.py`(938行) 体量大，可能需要拆分；`task-manager.py` 和 `task_engine.py` 存在功能重叠

---

## 模块 3: 知识同步系统

知识库同步、Wiki 内容上传、文件监听、文档评论处理等。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/knowledge-sync.py` | 963 | 知识同步总线 v2（事件驱动） |
| `scripts/auto-wiki-sync.py` | 319 | 自动 Wiki 同步 |
| `scripts/init-carl-knowledge.py` | 131 | 初始化知识库 |
| `scripts/start-knowledge-watcher.sh` | 56 | 启动文件监听守护进程 |
| `scripts/stop-knowledge-watcher.sh` | 40 | 停止文件监听守护进程 |
| `scripts/sync_memgate_wiki.py` | 106 | MemGate Wiki 同步 |
| `scripts/sync_model_arch_wiki.py` | 114 | 模型架构 Wiki 同步 |
| `scripts/sync_tokenizer_wiki.py` | 121 | Tokenizer Wiki 同步 |
| `scripts/sync_wiki_release.py` | 87 | Wiki 发布同步 |
| `scripts/upload_wiki_content.py` | 101 | Wiki 内容上传 |
| `scripts/write_wiki_content.py` | 103 | Wiki 内容写入 |
| `scripts/write-continuation.py` | 108 | 续写处理 |
| `scripts/check-continuation.py` | 60 | 续写检查 |
| `data/knowledge-sync-state.json` | 1,182 | 同步状态（大文件） |
| `data/tracked-docs.json` | 303 | 追踪文档列表 |
| `data/wiki-sync.json` | 44 | Wiki 同步配置 |
| `data/private-wiki.json` | 64 | 私有 Wiki 配置 |

### 统计
- **文件数**: 17
- **总行数**: ~3,902
- **最后修改**: 2026-02-12
- **代码质量**: ⚠️ `knowledge-sync.py`(963行) 非常大；多个 `sync_*_wiki.py` 脚本高度相似，应抽象公共函数

---

## 模块 4: 文档评论系统

飞书文档评论的扫描、检查、处理流程。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/check-comments.py` | 104 | 检查评论 |
| `scripts/check-comments-batch.py` | 85 | 批量检查评论 |
| `scripts/check-new-comments.py` | 76 | 检查新评论 |
| `scripts/check_comments_batch.py` | 83 | 批量检查（下划线版） |
| `scripts/check_comments_temp.py` | 71 | 临时评论检查 |
| `scripts/fetch_new_comments.py` | 87 | 获取新评论 |
| `scripts/list-pending-comments.py` | 85 | 列出待处理评论 |
| `scripts/scan-comments.py` | 96 | 扫描评论 |
| `scripts/scan-new-comments.py` | 90 | 扫描新评论 |
| `scripts/scan_comments.py` | 80 | 扫描评论（下划线版） |
| `scripts/scan_new_comments.py` | 97 | 扫描新评论（下划线版） |
| `scripts/temp-check-comments.py` | 72 | 临时检查脚本 |
| `scripts/check-doc-comments.sh` | 96 | Bash 版评论检查 |
| `scripts/process-comment-done.sh` | 176 | 处理"完成"评论流程 |
| `data/comment-state.json` | 56 | 评论状态 |

### 统计
- **文件数**: 15
- **总行数**: ~1,354
- **最后修改**: 2026-02-11
- **代码质量**: ❌ **严重冗余**！存在多个功能高度重叠的脚本（check-comments vs check_comments, scan-comments vs scan_comments 等），命名不一致（连字符 vs 下划线），有多个 temp 文件应清理

---

## 模块 5: 系统运维

看门狗、Gateway 重启、Patch 系统、心跳调度、Session 管理等。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/independent-watchdog.py` | 479 | 独立看门狗（进程监控） |
| `scripts/watchdog-log.py` | 71 | 看门狗日志 |
| `scripts/patch-openclaw.sh` | 596 | OpenClaw 源码 Patch 脚本 |
| `scripts/restart-gateway.sh` | 48 | Gateway 统一重启 |
| `scripts/check-restart.sh` | 40 | 检查重启状态 |
| `scripts/mark-restart.sh` | 9 | 标记重启 |
| `scripts/heartbeat-scheduler.py` | 91 | 心跳调度器 |
| `scripts/session-overview.py` | 274 | Session 概览生成 |
| `scripts/inspect_session.py` | 148 | Session 检查工具 |
| `scripts/cleanup-session-locks.sh` | 21 | Session 锁清理 |
| `scripts/check-ci-events.py` | 35 | CI/CD 事件处理 |
| `scripts/now.sh` | 4 | 当前 SGT 时间 |
| `data/watchdog-state.json` | 7 | 看门狗状态 |
| `data/restart-marker.json` | 5 | 重启标记 |
| `data/session-overview.json` | 91 | Session 概览数据 |
| `data/heartbeat-state.json` | 9 | 心跳状态 |
| `data/gateway.pid` | 1 | Gateway PID |

### 统计
- **文件数**: 17
- **总行数**: ~1,929
- **最后修改**: 2026-02-12
- **代码质量**: ⚠️ `patch-openclaw.sh`(596行) 非常长，应拆分为多个独立 patch 脚本；`independent-watchdog.py`(479行) 也较大

---

## 模块 6: Patch 系统（OpenClaw 源码修改）

运行时 Patch OpenClaw 源码的 Python 脚本。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `patches/apply-feishu-streaming-fix.py` | 216 | 飞书流式消息修复 |
| `patches/disable-queue-notification.py` | 73 | 禁用队列通知 |
| `patches/fix-announce-cross-session.py` | 61 | 跨 Session 公告修复 |
| `patches/fix-feishu-command-authorized.py` | 48 | 飞书命令授权修复 |
| `patches/fix-feishu-group-session-key.py` | 53 | 群聊 Session Key 修复 |
| `patches/fix-feishu-group-wildcard.py` | 57 | 群聊通配符修复 |
| `patches/fix-feishu-mention-stripped.py` | 102 | @提及文本被剥离修复 |
| `patches/fix-lane-concurrency.py` | 65 | Lane 并发修复 |
| `patches/fix-streaming-card-ux.py` | 226 | 流式卡片 UX 修复 |
| `patches/fix-streaming-cross-session.py` | 61 | 流式跨 Session 修复 |
| `patches/fix-streaming-race-condition.py` | 191 | 流式竞态条件修复 |
| `patches/fix-streaming-silent-reply.py` | 63 | 流式静默回复修复 |

### 统计
- **文件数**: 12
- **总行数**: 1,216
- **最后修改**: 2026-02-12
- **代码质量**: ✅ 每个 patch 专注一个问题，结构清晰；但部分 patch 可能已过时需要清理

---

## 模块 7: 隐私与安全

Privacy Guard 框架，隐私审查、上下文过滤、知识隔离。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `privacy/privacy_context.py` | 135 | 隐私上下文管理 |
| `privacy/privacy_review.py` | 215 | 消息隐私审查 |
| `privacy/knowledge_store.py` | 185 | 知识库存储 |
| `privacy/config.json` | 14 | 隐私配置 |
| `privacy/knowledge/carl/private.jsonl` | 31 | Carl 私有知识 |
| `privacy/knowledge/carl/public.jsonl` | 8 | Carl 公开知识 |
| `privacy/tests/test_integration.py` | 167 | 集成测试 |
| `privacy/tests/test_isolation.py` | 342 | 隔离测试 |
| `privacy/tests/test_check_group_privacy.py` | 117 | 群聊隐私测试 |
| `scripts/privacy-check.py` | 15 | CLI 入口（超薄封装） |
| `scripts/privacy-hook.sh` | 36 | OpenClaw Hook |

### 统计
- **文件数**: 11
- **总行数**: ~1,265
- **最后修改**: 2026-02-11
- **代码质量**: ✅ 良好，有完整测试；`privacy-check.py` 仅15行，主要逻辑在 privacy/ 模块中

---

## 模块 8: 日报与统计

日报引擎、Token 用量统计、配额监控。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/daily-report-engine.py` | 1,126 | 日报引擎（综合报告生成） |
| `scripts/deliver-daily-report.sh` | 140 | 日报交付脚本 |
| `scripts/token-hourly-stats.py` | 495 | Token 小时级统计 |
| `scripts/log-quota.sh` | 41 | API 配额快照日志 |
| `data/daily-report-prompt.md` | 212 | 日报 prompt 模板 |
| `data/periodic-check-prompt.md` | 120 | 定期检查 prompt |
| `data/weekly-review-prompt.md` | 52 | 周报 prompt |
| `data/quota-snapshots/*.json` | ~5 files | 配额快照数据 |

### 统计
- **文件数**: 8 (+5 snapshots)
- **总行数**: ~2,186
- **最后修改**: 2026-02-12
- **代码质量**: ⚠️ `daily-report-engine.py`(1126行) 非常长，是整个代码库最大的单文件，强烈建议拆分

---

## 模块 9: 数据管理与备份

数据备份、云同步、MemGate 同步等。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/daily-backup.sh` | 44 | 每日备份 |
| `scripts/cloud_sync_data.sh` | 58 | 云同步数据 |
| `scripts/memgate-sync.sh` | 70 | MemGate 同步到本地 |
| `scripts/memgate-pr.sh` | 39 | MemGate PR 创建 |
| `data/important-dates.json` | 63 | 重要日期配置 |
| `data/recurring-meetings.json` | 32 | 循环会议配置 |
| `data/calendar-categories.md` | 54 | 日历分类配置 |
| `data/personal-system.md` | 70 | 个人系统提示 |

### 统计
- **文件数**: 8
- **总行数**: ~430
- **最后修改**: 2026-02-11
- **代码质量**: ✅ 简单清晰

---

## 模块 10: ML/AI 训练相关（MemGate 预研）

Tokenizer、数据处理、模型训练相关脚本和配置（大部分是 MemGate 项目预研代码）。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `scripts/prepare_corpus.py` | 38 | 语料准备 |
| `scripts/tokenize_corpus.py` | 66 | 语料 tokenize |
| `scripts/train_tokenizer.py` | 56 | 训练 tokenizer |
| `scripts/test_tokenizer.py` | 28 | 测试 tokenizer |
| `scripts/train.py` | 30 | 训练入口 |
| `scripts/generate_scaffold_report.py` | 80 | 脚手架报告生成 |
| `data/pipeline.py` | 145 | 数据 pipeline |
| `data/prepare_data.py` | 237 | 数据准备 |
| `data/dataloader.py` | 341 | DataLoader |
| `data/dataset.py` | 50 | Dataset 定义 |
| `data/__init__.py` | 27 | 包初始化 |
| `data/tokenizer.model` | - | 训练好的 tokenizer |
| `data/tokenizer.vocab` | - | 词表文件 |

### 统计
- **文件数**: 13
- **总行数**: ~1,098
- **最后修改**: 2026-02-11
- **代码质量**: ⚠️ 这些脚本更像是实验性代码，缺少文档和错误处理

---

## 模块 11: API Proxy（独立项目）

API Key 反代服务，支持多 Key 轮转、降级、用量统计。

### 项目路径: `/home/ubuntu/api-proxy/`

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/app.py` | 374 | 主应用（FastAPI） |
| `src/proxy.py` | 203 | 代理核心逻辑 |
| `src/fallback.py` | 146 | 降级策略 |
| `src/admin.py` | 270 | 管理 API |
| `src/auth.py` | 80 | 认证模块 |
| `src/usage.py` | 62 | 用量统计 |
| `src/config.py` | 29 | 配置 |
| `src/health.py` | 14 | 健康检查 |
| `src/__init__.py` | 1 | 包初始化 |
| `scripts/smoke-test.sh` | 93 | 冒烟测试 |
| `tests/test_server.py` | 871 | 服务器测试 |
| `tests/test_fallback.py` | 649 | 降级测试 |
| `tests/test_integration.py` | 127 | 集成测试 |
| `tests/mock_upstream.py` | 168 | Mock 上游服务 |
| `keys.json` | ~500 | API Key 配置 |

### 统计
- **文件数**: 15
- **总行数**: ~3,387 (源码 1,179 + 测试 1,815 + 其他 393)
- **最后修改**: 2026-02-12
- **代码质量**: ✅ 良好，有完善的测试（测试行数 > 源码行数），有 CI/CD、Docker 配置

---

## 模块 12: Webhook Gateway（独立项目）

Webhook 接收网关，处理 GitHub/Lark webhook 事件。

### 项目路径: `/home/ubuntu/webhook-gateway/`

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/main.py` | 17 | 主入口 |
| `src/config.py` | 37 | 配置 |
| `src/webhook/github.py` | 142 | GitHub webhook 处理 |
| `src/webhook/lark.py` | 100 | Lark webhook 处理 |
| `src/__init__.py` | 0 | 包初始化 |
| `scripts/smoke-test.sh` | 16 | 冒烟测试 |
| `tests/test_main.py` | 92 | 测试 |
| `tests/__init__.py` | 0 | 包初始化 |

### 统计
- **文件数**: 8
- **总行数**: 404 (源码 296 + 测试 92 + 脚本 16)
- **最后修改**: 2026-02-12
- **代码质量**: ✅ 良好，结构清晰，有测试

---

## 模块 13: 飞书插件原始备份

OpenClaw 飞书插件的原始 TypeScript 源码备份。

### 项目路径: `/home/ubuntu/feishu-original-backup/`

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `index.ts` | 15 | 入口 |
| `src/channel.ts` | 276 | 频道处理 |
| `src/onboarding.ts` | 278 | Onboarding 流程 |
| `src/config-schema.ts` | 47 | 配置 Schema |

### 统计
- **文件数**: 4
- **总行数**: 616 (TypeScript)
- **最后修改**: 2025-02-06 (较旧)
- **代码质量**: ℹ️ 备份性质，不需要维护

---

## 模块 14: Prompt 模板与任务配置

Spawn 任务 prompt 模板和各类配置数据。

### 文件列表

| 文件 | 行数 | 说明 |
|------|------|------|
| `data/spawn-prompts/t*.json` | ~25 files | Spawn 任务 prompt（历史） |
| `data/planner/*.json` | 3 files | Planner 计划数据 |
| `data/t074~t103 prompt.md` | ~10 files | 各任务 prompt 模板 |
| `data/staging-setup.md` | 213 | Staging 环境配置文档 |
| `data/upgrade-report.md` | 221 | 升级报告 |
| `data/upgrade-streaming-plan.md` | 172 | 流式升级方案 |
| `data/homepage-design.md` | 443 | 主页设计文档 |
| `data/sysmonitor-review.md` | 136 | 系统监控审查 |

### 统计
- **文件数**: ~42
- **总行数**: ~2,500 (估算)
- **代码质量**: ℹ️ 配置/文档性质，部分历史 prompt 可归档清理

---

# 总览统计

| 模块 | 文件数 | 行数 | 优先级 |
|------|--------|------|--------|
| Lark/飞书集成 | 27 | ~4,186 | 🔴 高 |
| 任务管理系统 | 17 | ~4,219 | 🔴 高 |
| 知识同步系统 | 17 | ~3,902 | 🟡 中 |
| 文档评论系统 | 15 | ~1,354 | 🔴 高（冗余严重） |
| 系统运维 | 17 | ~1,929 | 🟡 中 |
| Patch 系统 | 12 | 1,216 | 🟡 中 |
| 隐私与安全 | 11 | ~1,265 | 🟢 低（质量好） |
| 日报与统计 | 13 | ~2,186 | 🟡 中 |
| 数据管理 | 8 | ~430 | 🟢 低 |
| ML/AI 训练 | 13 | ~1,098 | 🟡 中 |
| API Proxy | 15 | ~3,387 | 🟢 低（质量好） |
| Webhook Gateway | 8 | 404 | 🟢 低（质量好） |
| 飞书插件备份 | 4 | 616 | ⬜ 无需 Review |
| Prompt/配置 | ~42 | ~2,500 | 🟢 低 |

**总计**: ~219 文件, ~28,692 行代码

### 主要代码质量问题（一目了然）

1. **🔴 文档评论系统严重冗余** — 15 个脚本做类似的事，需要大幅合并
2. **🔴 超大单文件** — `daily-report-engine.py`(1126行), `planner.py`(1034行), `knowledge-sync.py`(963行), `task_engine.py`(938行)
3. **⚠️ 命名不一致** — 混用连字符和下划线（`check-comments.py` vs `check_comments.py`）
4. **⚠️ 功能重叠** — `task-manager.py` vs `task_engine.py`, 多个 `sync_*_wiki.py` 重复逻辑
5. **⚠️ 临时脚本未清理** — `temp-check-comments.py`, `check_comments_temp.py`, `temp_calendar_check.py`
