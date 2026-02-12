# OpenClaw 升级兼容性报告

**当前版本**: 2026.2.3-1  
**目标版本**: 2026.2.9  
**分析日期**: 2026-02-12  
**分析范围**: 12 个自定义 Patch 的兼容性

---

## 版本变更摘要

从 2026.2.3-1 → 2026.2.9，经过以下中间版本：
- **2026.2.3** — Telegram 清理、Cron 大改、消息 responsePrefix、安全加固
- **2026.2.6** — Cron wakeMode 改默认、Opus 4.6 / Codex 5.3 模型支持、xAI/百度 provider、Voyage 记忆、cron 可靠性大修
- **2026.2.9** — **架构巨变**（详见下方）

### 🔴 2026.2.9 关键架构变更

| 变更 | 影响 |
|------|------|
| **Feishu 从 plugin-sdk 内联代码迁移为独立 TypeScript 扩展** (`extensions/feishu/`) | 所有 Feishu 相关 patch 需要完全重写，目标文件从 `plugin-sdk/index.js` 变为 `extensions/feishu/src/*.ts` |
| **构建系统迁移至 tsdown/tsgo** | `plugin-sdk/index.js` 从 71,437 行缩减至 24,800 行，代码完全重组 |
| **Feishu 流式卡片 (Streaming Card) 功能已移除** | 新版 Feishu 使用 `blockStreaming: true` 模式，不再有独立的流式卡片系统 |
| **代码分割** | 主要逻辑分布在 `loader-Ds3or8QX.js`（~50k行）和 `extensionAPI.js`（~62k行）等文件中 |
| **Feishu 扩展为 TypeScript 源码** | `extensions/feishu/src/*.ts` 是源码，运行时编译加载，patch 需修改 `.ts` 文件 |
| **Session 路由改为 `resolveAgentRoute` API** | 不再直接设置 `ctx.From`，通过 `peer: { kind, id }` 路由 |
| **队列通知机制已移除** | 新版无 `queueTimer` / `queueNotified` 代码 |

---

## Patch 兼容性矩阵

| # | Patch | 修改文件 | 新版状态 | 操作建议 |
|---|-------|----------|----------|----------|
| 1 | `apply-feishu-streaming-fix.py` | `plugin-sdk/index.js` (Patch 9 区域) | 🟢 **不再需要** | ✅ 可移除。新版无流式卡片，无跨 turn 重复问题 |
| 2 | `disable-queue-notification.py` | `plugin-sdk/index.js` (queueTimer) | 🟢 **不再需要** | ✅ 可移除。新版已完全移除队列通知机制 |
| 3 | `fix-announce-cross-session.py` | `plugin-sdk/index.js` (runSubagentAnnounceFlow) | 🟡 **需验证** | ⚠️ 新版 announce 流程已重构（使用 `maybeQueueSubagentAnnounce`），但仍可能存在 NO_REPLY 场景，需在新版中测试确认 |
| 4 | `fix-feishu-group-session-key.py` | `plugin-sdk/index.js` (From: senderId → chatId) | 🟢 **已被官方修复** | ✅ 可移除。新版使用 `resolveAgentRoute({ peer: { kind: "group", id: chatId } })` 正确路由群聊 session |
| 5 | `fix-feishu-group-wildcard.py` | `plugin-sdk/index.js` (resolveFeishuGroupConfig) | 🔴 **仍然需要** | ⚠️ 新版 `policy.ts` 仍无 `*` 通配符回退。需重写为修改 `extensions/feishu/src/policy.ts` |
| 6 | `fix-feishu-mention-stripped.py` | `plugin-sdk/index.js` (mention 处理) | 🔴 **仍然需要** | ⚠️ 新版 `stripBotMention()` 仍然删除所有 @mention（不只是 bot），需重写为修改 `extensions/feishu/src/bot.ts` |
| 7 | `fix-lane-concurrency.py` | `plugin-sdk/index.js` (lanes) | 🔴 **仍然需要** | ⚠️ 新版 `maxConcurrent` 仍为 1，但代码已移至 `loader-Ds3or8QX.js`（含 hash 的文件名），并提供了 `setCommandLaneConcurrency()` API。需使用新方式设置 |
| 8 | `fix-streaming-card-ux.py` | `plugin-sdk/index.js` (FeishuStreamingSession) | 🟢 **不再需要** | ✅ 可移除。新版无流式卡片，使用 blockStreaming + 文本/卡片回复 |
| 9 | `fix-streaming-cross-session.py` | `plugin-sdk/index.js` (onAgentEvent) | 🟢 **不再需要** | ✅ 可移除。新版无流式卡片，无跨 session 污染问题 |
| 10 | `fix-streaming-race-condition.py` | `plugin-sdk/index.js` (FeishuStreamingSession.start) | 🟢 **不再需要** | ✅ 可移除。新版无流式卡片，无竞态条件 |
| 11 | `fix-streaming-silent-reply.py` | `plugin-sdk/index.js` (close + isSilentContent) | 🟢 **不再需要** | ✅ 可移除。新版无流式卡片 close() 逻辑 |
| 12 | `fix-feishu-command-authorized.py` | `loader-BAZoAqqR.js` (normalizer CommandAuthorized) | 🟢 **已被官方修复** | ✅ 可移除。新版 Feishu 扩展在 `bot.ts` 中硬编码 `CommandAuthorized: true`，不再依赖 normalizer 默认值 |

### 统计

| 状态 | 数量 | Patches |
|------|------|---------|
| ✅ 可移除（已修复或不再需要） | **9** | #1, #2, #4, #8, #9, #10, #11, #12 |
| ⚠️ 仍需要但需重写 | **3** | #5 (wildcard), #6 (mention), #7 (lane) |
| 🟡 需验证 | **1** | #3 (announce) |

---

## 各 Patch 详细分析

### Patch 1: apply-feishu-streaming-fix.py ✅ 可移除

**原问题**: 跨 turn 内容重复（Patch 9 累积逻辑错误）  
**新版状态**: 整个 Feishu 流式卡片系统已被移除。新版使用 `blockStreaming: true`，回复通过 `sendMessageFeishu` / `sendMarkdownCardFeishu` 直接发送完整文本/卡片。  
**包含的子修复**（API key 脱敏、工具状态面板增强）也随之不再适用，因为工具状态显示已移至核心层。

### Patch 2: disable-queue-notification.py ✅ 可移除

**原问题**: 3 秒 setTimeout 队列通知，thinking 模型误触发  
**新版状态**: `queueTimer`、`queueNotified`、`replyStarted` 等代码在新版中完全不存在。队列通知功能已被移除。

### Patch 3: fix-announce-cross-session.py 🟡 需验证

**原问题**: NO_REPLY 子任务仍触发 announce，导致主 session 串台  
**新版状态**: announce 流程已完全重构为 `maybeQueueSubagentAnnounce`，使用基于 queue 的异步机制。announce prompt 中已包含 `"You can respond with NO_REPLY if no announcement is needed"` 指导。但是否在回复为 NO_REPLY 时自动跳过仍需测试。  
**建议**: 升级后实际测试 subagent 任务的 NO_REPLY 行为，确认不会导致不必要的 announce。

### Patch 4: fix-feishu-group-session-key.py ✅ 可移除

**原问题**: 群聊消息使用发送者 open_id 作为 session key，导致不同群共享 session  
**新版状态**: 已修复。新版 `bot.ts` 使用 `core.channel.routing.resolveAgentRoute({ peer: { kind: "group", id: chatId } })`，正确以 chatId 路由群聊 session。`feishuFrom` 设为 `feishu:${ctx.senderOpenId}` 用于标识发言人，不影响 session 路由。

### Patch 5: fix-feishu-group-wildcard.py 🔴 仍需要，需重写

**原问题**: `resolveFeishuGroupConfig` 只查找 `groups[chatId]`，不回退到 `groups["*"]`  
**新版状态**: `extensions/feishu/src/policy.ts` 中 `resolveFeishuGroupConfig` 仍然只做精确匹配（+ 大小写不敏感匹配），没有 `*` 通配符回退：
```typescript
const direct = groups[groupId];
if (direct) return direct;
const lowered = groupId.toLowerCase();
const matchKey = Object.keys(groups).find((key) => key.toLowerCase() === lowered);
return matchKey ? groups[matchKey] : undefined;
```
**重写方案**: 修改 `extensions/feishu/src/policy.ts`，在 `return matchKey ? ...` 后追加 `?? groups["*"]`。

### Patch 6: fix-feishu-mention-stripped.py 🔴 仍需要，需重写

**原问题**: 所有 @mention 被完全删除，丢失了"谁被@了"的信息  
**新版状态**: `bot.ts` 中 `stripBotMention()` 仍然删除**所有** mention（不只是 bot mention），包括 `@mention.name` 和 `mention.key` 占位符。虽然新版有 `mentionTargets` 机制来处理 @转发 场景，但基础 mention 信息仍然丢失。  
**重写方案**: 修改 `extensions/feishu/src/bot.ts` 的 `stripBotMention()`，只删除 bot 自身的 mention，保留其他用户的 @Name。

### Patch 7: fix-lane-concurrency.py 🔴 仍需要，需重写

**原问题**: 全局 lane `maxConcurrent=1`，不同 session 互相阻塞  
**新版状态**: `getLaneState()` 默认仍是 `maxConcurrent: 1`。但新版提供了 `setCommandLaneConcurrency(lane, maxConcurrent)` API，代码位于 `loader-*.js`（文件名含 hash）。  
**重写方案**: 
- 方案 A: 在启动脚本或 hook 中调用 `setCommandLaneConcurrency("main", 4)` 等 API
- 方案 B: 直接 patch `loader-*.js` 中的 `getLaneState()` 默认值（但文件名含 hash，每次升级都变）
- 方案 C: 检查是否有配置项控制 lane 并发（`agents.defaults.maxConcurrent` 可能相关）

### Patch 12: fix-feishu-command-authorized.py ✅ 已被官方修复

**原问题**: Feishu 插件未显式设置 `CommandAuthorized`，normalizer 中 `normalized.CommandAuthorized = normalized.CommandAuthorized === true` 将 `undefined` 转为 `false`，导致 `/new` 和 `/reset` 命令不可用  
**新版状态**: 已修复。新版 Feishu 扩展（`extensions/feishu/src/bot.ts`）在消息处理的两个关键位置（第 754 行和第 830 行）都硬编码了 `CommandAuthorized: true`。normalizer 中虽然仍保留 `=== true` 严格检查（`loader-Ds3or8QX.js:31200`），但由于 Feishu 扩展已显式设置 `true`，该检查不再产生问题。  
**补充说明**: normalizer 的 `=== true` 严格检查仍然存在，理论上其他未显式设置 `CommandAuthorized` 的第三方扩展仍可能受影响。但对 Feishu 场景而言，此 patch 已不再需要。

---

## 升级风险评估

### 🔴 高风险

1. **Feishu 插件完全重写** — 所有 patch 的目标文件、代码结构都变了。不能直接应用现有 patch。
2. **Feishu 流式卡片功能消失** — 如果依赖流式卡片的实时反馈体验，升级后会回退到分段文本回复。
3. **TypeScript 源码 patch** — 新版 Feishu 扩展是 `.ts` 源码，patch 需要修改 TypeScript 文件并确保运行时编译兼容。

### 🟡 中等风险

1. **Lane 并发** — 仍需解决，否则群聊和私聊消息会互相阻塞。
2. **Mention 丢失** — 仍然存在，影响群聊中 @其他人 的场景。
3. **Wildcard 群配** — 仍然需要，否则 `groups: { "*": { ... } }` 不生效。

### 🟢 低风险

1. **Session key 路由** — 已被官方修复。
2. **Queue 通知** — 已被移除。
3. **流式卡片相关 bug** — 随功能删除而消失。

---

## 推荐升级步骤

### 阶段 1: 准备（升级前）

```bash
# 1. 备份当前版本
cp -r /home/ubuntu/.npm-global/lib/node_modules/openclaw /tmp/openclaw-backup-2.3-1

# 2. 备份配置
cp -r ~/.openclaw/config ~/.openclaw/config.bak-2.3-1

# 3. 准备新版 patch（在升级前就写好，升级后直接应用）
# 需要新写的 patch:
#   - fix-feishu-group-wildcard-v2.py (target: extensions/feishu/src/policy.ts)
#   - fix-feishu-mention-stripped-v2.py (target: extensions/feishu/src/bot.ts)  
#   - fix-lane-concurrency-v2.py (target: loader-*.js 或使用配置/API)
```

### 阶段 2: 升级

```bash
# 停止网关
openclaw gateway stop

# 升级到 2.9
npm update -g openclaw@2026.2.9

# 或使用内置升级命令
openclaw update --tag 2026.2.9
```

### 阶段 3: 应用新 Patch

```bash
# 1. 应用群组通配符修复
python3 patches/fix-feishu-group-wildcard-v2.py

# 2. 应用 mention 保留修复
python3 patches/fix-feishu-mention-stripped-v2.py

# 3. 应用 lane 并发修复
python3 patches/fix-lane-concurrency-v2.py
```

### 阶段 4: 验证

```bash
# 启动并检查
openclaw gateway start

# 验证:
# - 群聊消息正常响应（session 路由正确）
# - groups["*"] 配置生效
# - @mention 信息保留
# - 多 session 并发不阻塞
# - subagent NO_REPLY 不触发多余 announce
```

### 旧 Patch 清理

以下 8 个 patch 可以安全删除：
- `apply-feishu-streaming-fix.py`
- `disable-queue-notification.py`
- `fix-feishu-group-session-key.py`
- `fix-streaming-card-ux.py`
- `fix-streaming-cross-session.py`
- `fix-streaming-race-condition.py`
- `fix-streaming-silent-reply.py`
- `fix-announce-cross-session.py`（在验证 NO_REPLY 行为后可删除）
- `fix-feishu-command-authorized.py`

---

## 注意事项

1. **流式卡片体验降级**: 2.9 的 Feishu 不再有实时流式卡片。消息会在生成完毕后一次性发送。这是一个**用户体验降级**，但消除了流式卡片带来的所有 bug（竞态、串台、重复、泄露）。考虑是否可接受。

2. **Feishu 扩展是 TS 源码**: patch 需要修改 `.ts` 文件。OpenClaw 会在运行时编译这些文件。这意味着 patch 后需要确保 TypeScript 语法正确。

3. **Loader 文件名含 hash**: `loader-Ds3or8QX.js` 的文件名在不同版本可能变化。lane patch 需要动态查找文件名。

4. **`setCommandLaneConcurrency` API**: 新版提供了公开 API 设置 lane 并发，可能可以通过 hook 或配置实现而不需要 patch 源码。
