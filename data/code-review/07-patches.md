# Patch 系统 Review

**OpenClaw 版本**: 2026.2.3-1
**Review 日期**: 2026-02-12
**Patch 总数**: 13 个（12 个在 review 列表 + 1 个额外发现）
**Target 文件**: 3 个

## 📊 总览

| # | Patch 文件 | Target | 状态 | 仍需要? | PR 候选? |
|---|-----------|--------|------|---------|----------|
| 1 | apply-feishu-streaming-fix.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 2 | disable-queue-notification.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 3 | fix-announce-cross-session.py | plugin-sdk/index.js | ✅ Applied | ⚠️ 冗余 | ❌ |
| 4 | fix-feishu-command-authorized.py | loader-BAZoAqqR.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 5 | fix-feishu-group-session-key.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 6 | fix-feishu-group-wildcard.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 7 | fix-feishu-mention-stripped.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 8 | fix-lane-concurrency.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 9 | fix-streaming-card-ux.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ⚠️ 部分 |
| 10 | fix-streaming-cross-session.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 11 | fix-streaming-race-condition.py | plugin-sdk/index.js | ✅ Applied | ✅ 是 | ✅ 是 |
| 12 | fix-streaming-silent-reply.py | plugin-sdk/index.js | ⚠️ 被覆盖 | ❌ 冗余 | ❌ |
| 13 | fix-announce-no-reply.py *(额外)* | reply-DpTyb3Hh.js | ✅ Applied | ⚠️ 冗余 | ❌ |

## 📋 逐个 Patch 详细分析

### 1. apply-feishu-streaming-fix.py ✅ 保留

**功能**: 修复 Feishu 流式卡片跨 turn 内容重复 bug（替换原始 Patch 9 逻辑）
**Target**: `plugin-sdk/index.js`
**改动范围**: 8 处替换（变量声明、turn 检测、工具状态、API key 脱敏、更多工具处理器）
**上游状态**: 未修复。上游 CHANGELOG 无相关 fix，原始 Patch 9 仍在代码中
**幂等性**: ✅ 良好。检测 "Luna fix v4" marker 跳过
**评估**: **核心 patch，必须保留**。流式卡片的正确性完全依赖它

**PR 建议**: ✅ 高优先级。内容分为两类：
- **Bug fix**: turn 检测逻辑（核心修复）→ 单独 PR
- **Enhancement**: 工具状态中文 label、API key 脱敏 → 可能需要配置化而非硬编码中文

### 2. disable-queue-notification.py ✅ 保留

**功能**: 禁用 3 秒超时的 "前一条消息还在处理中" 误报通知
**Target**: `plugin-sdk/index.js`
**改动范围**: 1 处替换（禁用 setTimeout timer）
**上游状态**: 未修复。上游仍保留 3 秒 timer
**幂等性**: ✅ 良好。检测 "DISABLED" marker
**评估**: **保留**。thinking model 下 3 秒几乎总会超时，误报率 >90%

**PR 建议**: ✅ 建议改为配置项（`queueNotificationDelayMs: 0` 禁用，默认 3000）

### 3. fix-announce-cross-session.py ⚠️ 冗余

**功能**: 在 `plugin-sdk/index.js` 中跳过 NO_REPLY 的 subagent announce
**Target**: `plugin-sdk/index.js`
**改动范围**: 1 处插入
**与 #13 的关系**: **功能完全相同**，但 target 不同！
- #3 patch `plugin-sdk/index.js`
- #13 (fix-announce-no-reply.py) patch `reply-DpTyb3Hh.js`
- 两个文件里都有 `runSubagentAnnounceFlow`（代码重复），两个 patch 都在生效
**幂等性**: ✅ 检测 marker
**评估**: **冗余但无害**。两处代码路径都被修复，形成双保险。但维护成本增加

**建议**: 合并为一个 patch 脚本，同时修补两个文件，或确认哪个文件路径实际被调用

### 4. fix-feishu-command-authorized.py ✅ 保留

**功能**: CommandAuthorized 默认 true（修复 /new /reset 在 Feishu 不可用）
**Target**: `loader-BAZoAqqR.js` ⚠️ 文件名含 hash，版本更新可能变化
**改动范围**: 1 处替换（`=== true` → `!== false`）
**上游状态**: 未修复
**幂等性**: ✅ 良好
**评估**: **保留**。Feishu 是社区贡献的 plugin，上游不一定了解这个问题

**⚠️ 风险**: loader 文件名含 hash（`BAZoAqqR`），OpenClaw 更新时文件名可能变化，需动态查找
**PR 建议**: ✅ 简单修复，适合上游 PR

### 5. fix-feishu-group-session-key.py ✅ 保留

**功能**: 群消息 From 用 chatId 而非 senderId（避免不同群共享 session）
**Target**: `plugin-sdk/index.js`
**改动范围**: 1 处替换
**上游状态**: 未修复。其他 channel（Telegram、iMessage）已有 `isGroup ? chatId : senderId` 模式
**幂等性**: ✅ 良好
**评估**: **保留**。这是 Feishu plugin 的基础 bug

**PR 建议**: ✅ 高优先级。Telegram/iMessage 已有相同模式，Feishu 显然遗漏

### 6. fix-feishu-group-wildcard.py ✅ 保留

**功能**: resolveFeishuGroupConfig 支持 `"*"` 通配符 fallback
**Target**: `plugin-sdk/index.js`
**改动范围**: 1 处替换
**上游状态**: 未修复
**幂等性**: ✅ 良好
**评估**: **保留**。没有 wildcard fallback，新群聊默认 requireMention=true

**PR 建议**: ✅ 高优先级。一行修复

### 7. fix-feishu-mention-stripped.py ✅ 保留

**功能**: @mention 保留名字（替代完全删除）+ 添加 MentionedUsers 上下文
**Target**: `plugin-sdk/index.js`
**改动范围**: 2 处替换
**上游状态**: 未修复
**幂等性**: ✅ 良好。两处独立检测
**评估**: **保留**。丢失 @mention 上下文会导致 LLM 无法理解谁被提及

**PR 建议**: ✅ 适合上游 PR

### 8. fix-lane-concurrency.py ✅ 保留

**功能**: 非 session 级 lane（main/cron/subagent）并发从 1 → 4
**Target**: `plugin-sdk/index.js`
**改动范围**: 1 处替换
**上游状态**: 未修复。全局默认 maxConcurrent=1
**幂等性**: ✅ 良好
**评估**: **保留**。没有此 patch，群聊等私聊排队 60-120 秒

**PR 建议**: ✅ 建议配置化（`lanes.defaultConcurrency: 4`），而非硬编码。但作为 bug fix 也可以直接 PR（session 级保持 1 是对的，全局级 1 太保守）

### 9. fix-streaming-card-ux.py ✅ 保留

**功能**: 3 合 1 修复 — 移除卡片标题、短内容删卡长内容保留、final 不 return
**Target**: `plugin-sdk/index.js`
**改动范围**: 3 处替换
**上游状态**: 未修复
**幂等性**: ✅ 良好（3 处独立检测）
**与 #12 的关系**: **此 patch 完全包含 #12 的功能**（isSilentContent 检测 + isShortContent 额外逻辑）
**评估**: **保留**。这是流式卡片 UX 的核心改进

**PR 建议**: ⚠️ 部分适合。Fix 1（去标题）和 Fix 3（不 return）是通用改进，Fix 2（短内容删卡）是偏好性行为，可能需要配置项

### 10. fix-streaming-cross-session.py ✅ 保留

**功能**: onAgentEvent 加 sessionKey 过滤，防止工具状态串台
**Target**: `plugin-sdk/index.js`
**改动范围**: 1 处替换
**上游状态**: 未修复。`onAgentEvent` 仍是全局广播
**幂等性**: ✅ 良好
**评估**: **保留**。这是多 session 环境的基础 bug

**PR 建议**: ✅ 高优先级。onAgentEvent 应该原生支持 sessionKey 过滤

### 11. fix-streaming-race-condition.py ✅ 保留

**功能**: 防止 start() 并发调用导致重复流式卡片
**Target**: `plugin-sdk/index.js`
**改动范围**: 4 处替换（start guard + 3 个 caller 同步设 flag）
**上游状态**: 未修复
**幂等性**: ✅ 良好（每处独立检测）
**注意**: Fix 3 和 Fix 4 报 "target not found"，因为 apply-feishu-streaming-fix.py 已修改了 onPartialReply/onReasoningStream 的代码结构。实际 Fix 1/1b/2 已足够（_starting guard 在 start() 方法内），Fix 3/4 是额外保险
**评估**: **保留**。race condition 是真实 bug

**PR 建议**: ✅ 高优先级

### 12. fix-streaming-silent-reply.py ❌ 可删除

**功能**: close() 检测 NO_REPLY/HEARTBEAT_OK 并删卡
**Target**: `plugin-sdk/index.js`
**与 #9 的关系**: **完全被 fix-streaming-card-ux.py (#9) 包含和替代**
- #12 只做 isSilentContent 检测
- #9 的 Fix 2 做 isSilentContent + isShortContent，是 #12 的超集
**当前状态**: #9 已 applied 后，#12 的检测标记 (`isSilentContent`) 已存在 → 报 "already applied"
**幂等性**: ✅ 但语义上误导（实际是 #9 的标记被它误认为自己 applied）
**评估**: **冗余，建议删除或标记 deprecated**

### 13. fix-announce-no-reply.py ⚠️ 冗余（额外发现）

**功能**: 与 #3 完全相同，但 target 是 `reply-DpTyb3Hh.js`
**Target**: `reply-DpTyb3Hh.js` ⚠️ 文件名含 hash，版本更新可能变化
**与 #3 的关系**: 功能重复。`runSubagentAnnounceFlow` 存在于两个文件中（可能是打包时的 code splitting）
**评估**: 与 #3 合并或确认实际调用路径后保留其一

## 🔥 Patch 之间的冲突和依赖

### 依赖链（执行顺序重要）

```
1. apply-feishu-streaming-fix.py     ← 必须最先执行（修改 onPartialReply 结构）
2. fix-streaming-race-condition.py   ← 依赖 #1 修改后的结构（Fix 3/4 找不到 target 是因为 #1 改了代码）
3. fix-streaming-card-ux.py          ← 依赖 #1 修改后的 close() 方法
4. fix-streaming-silent-reply.py     ← 被 #3(card-ux) 完全覆盖，不应再执行
5-12: 其余 patch 互相独立
```

### 已知冲突

| Patch A | Patch B | 冲突类型 |
|---------|---------|---------|
| #9 (card-ux) | #12 (silent-reply) | **功能覆盖** — #9 包含 #12 所有功能。#12 的 isSilentContent 检测被 #9 的 Fix 2 替代。当前两者的 marker 相同导致 #12 误判为 "already applied" |
| #3 (announce-cross) | #13 (announce-no-reply) | **功能重复** — 同一逻辑 patch 到不同文件。可能只有一个路径实际执行 |
| #1 (streaming-fix) | #11 (race-condition) | **结构依赖** — #1 修改了 onPartialReply 结构，导致 #11 的 Fix 3/4 找不到 target。不影响功能（Fix 1/1b/2 已足够） |

### 无冲突

- #2 (queue-notification)、#4 (command-authorized)、#5 (group-session-key)、#6 (wildcard)、#7 (mention)、#8 (lane-concurrency)、#10 (cross-session) — 各自独立，互不影响

## 🎯 上游 PR 建议（按优先级排序）

### P0 — 高优先级（核心 Bug Fix）

1. **fix-feishu-group-session-key** (#5) — 群聊 session 隔离，一行修复
2. **fix-feishu-group-wildcard** (#6) — 通配符 fallback，一行修复
3. **fix-streaming-cross-session** (#10) — 多 session 工具状态串台
4. **fix-streaming-race-condition** (#11) — 并发创建重复卡片
5. **fix-feishu-command-authorized** (#4) — /new /reset 不可用

### P1 — 中优先级

6. **fix-feishu-mention-stripped** (#7) — @mention 上下文丢失
7. **fix-lane-concurrency** (#8) — 全局 lane 队列阻塞（建议配置化）
8. **apply-feishu-streaming-fix** (#1) — 流式卡片 turn 检测（需要拆分 bug fix 和 enhancement）

### P2 — 低优先级 / 需要讨论

9. **disable-queue-notification** (#2) — 建议改为配置项
10. **fix-streaming-card-ux** (#9) — 部分是偏好性行为，需要讨论

### 不适合 PR

- **fix-announce-cross-session** (#3) / **fix-announce-no-reply** (#13) — 与我们的 planner/task-manager 架构强耦合，上游无此场景

## 🧹 清理建议

1. **删除 fix-streaming-silent-reply.py (#12)** — 已被 fix-streaming-card-ux.py 完全覆盖
2. **合并 fix-announce-cross-session.py (#3) 和 fix-announce-no-reply.py (#13)** — 同功能双文件
3. **HEARTBEAT.md 中的 patch 列表缺 4 个 patch** — 缺少 #3(announce-cross)、#4(command-authorized)、#7(mention)、#9(card-ux)、#11(race-condition)，需要同步
4. **fix-feishu-command-authorized.py 的 target 文件名含 hash** — 需要改为动态查找（`ls dist/loader-*.js`）
5. **fix-announce-no-reply.py 的 target 文件名含 hash** — 同上（`reply-DpTyb3Hh.js`）
6. **建立 patch 执行顺序文档** — 避免依赖链错误

## ⚠️ 风险评估

### OpenClaw 更新后 patch 失效风险

| 风险级别 | Patch | 原因 |
|---------|-------|------|
| 🔴 高 | #4 (command-authorized) | loader 文件名含 hash，更新必变 |
| 🔴 高 | #13 (announce-no-reply) | reply 文件名含 hash，更新必变 |
| 🟡 中 | #1 (streaming-fix) | 大量精确匹配，上游任何重构都会断 |
| 🟡 中 | #11 (race-condition) | 与 #1 强耦合，#1 断则 #11 也断 |
| 🟢 低 | #2,#5,#6,#7,#8,#10 | 小范围精确替换，相对稳定 |

### 应对措施
- 每次 `npm update` 后运行所有 patch 并检查 ⚠️ 输出
- 将 hash 文件名的 patch 改为 `glob` 动态查找
- 提交上游 PR 从根本上减少 patch 数量
