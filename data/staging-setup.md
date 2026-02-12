# OpenClaw 预发布（Staging）环境搭建指南

## 概述

- **生产版本**: 2026.2.3-1（端口 18789）
- **预发布版本**: 2026.2.9（端口 18790）
- **目的**: 验证 2.9 升级 + 流式卡片重新实现 + 3 个 patch 的效果

## 架构

```
~/.openclaw/           ← 生产环境 (2.3-1)
  openclaw.json         ← 生产配置 (port 18789)
  workspace/            ← 共享工作区

~/.openclaw-staging/    ← 预发布环境 (2.9)
  openclaw.json         ← 预发布配置 (port 18790)
  npm/                  ← 2.9 独立安装
  workspace → symlink   ← 指向生产工作区
  credentials/          ← 复制自生产（同一个 bot）
```

### ⚠️ 重要限制：飞书 WebSocket 连接

飞书 bot **同时只允许一个 WebSocket 连接**。生产和预发布使用相同的 bot（`cli_a90c3a6163785ed2`），因此：

- **不能同时运行两个 gateway** — 后启动的会抢占 WebSocket 连接
- **测试流程**: 停生产 → 启预发布 → 测试 → 停预发布 → 启生产
- 切换过程约 10-15 秒，对用户影响极小

## 配置差异

| 配置项 | 生产 | 预发布 |
|--------|------|--------|
| 版本 | 2026.2.3-1 | 2026.2.9 |
| 端口 | 18789 | 18790 |
| 二进制 | `~/.npm-global/lib/node_modules/openclaw/` | `~/.openclaw-staging/npm/lib/node_modules/openclaw/` |
| 配置 | `~/.openclaw/openclaw.json` | `~/.openclaw-staging/openclaw.json` |
| 状态 | `~/.openclaw/` | `~/.openclaw-staging/` |
| Tailscale | `/` → 18789 | `/staging` → 18790 |
| systemd | `openclaw-gateway.service` | `openclaw-staging.service` |
| 工作区 | `~/.openclaw/workspace/` | symlink → 同一个 |

## 快速操作

### 切换到预发布

```bash
# 1. 停止生产
systemctl --user stop openclaw-gateway.service

# 2. 启动预发布
systemctl --user start openclaw-staging.service

# 3. 验证
~/.openclaw-staging/openclaw-staging.sh gateway status
```

### 切换回生产

```bash
# 1. 停止预发布
systemctl --user stop openclaw-staging.service

# 2. 启动生产
systemctl --user start openclaw-gateway.service

# 3. 验证
openclaw gateway status
```

### 查看日志

```bash
# 预发布日志
journalctl --user -u openclaw-staging -f

# 生产日志
journalctl --user -u openclaw-gateway -f
```

## 已实现的修改（2.9 扩展）

### 1. 流式卡片 (`streaming.ts`)

新增文件 `extensions/feishu/src/streaming.ts`：
- 完整的 `FeishuStreamingSession` 类
- CardKit API 直接调用（不依赖 SDK 版本）
- 包含所有 5 个 streaming patch 的修复逻辑：
  - 竞态条件守卫（`_starting` flag）
  - 跨 turn 文本重复检测（`lastRawPayloadText` 长度比较）
  - 静默/短内容自动删除卡片
  - 长内容保留卡片并正常关闭
  - 更新队列序列化

### 2. 流式卡片集成 (`reply-dispatcher.ts`)

修改文件 `extensions/feishu/src/reply-dispatcher.ts`：
- 导入 `FeishuStreamingSession`
- 根据配置 `streaming` 和 `blockStreaming` 判断是否启用
- 在 `replyOptions` 中注入 `onPartialReply` 回调
- `deliver()` 中处理流式卡片关闭：
  - 长内容：卡片保留，跳过 deliver
  - 短内容/静默：卡片删除，正常 deliver

### 3. 群组通配符 (`policy.ts`)

修改 `resolveFeishuGroupConfig()`：
```typescript
// 添加 wildcard 回退
return matchKey ? groups[matchKey] : groups["*"];
```

### 4. @mention 保留 (`bot.ts`)

修改 `stripBotMention()`：
- 只删除 bot 自身的 `@mention`
- 其他用户的 `@mention` 替换为 `@Name` 文本保留

### 5. Lane 并发 (JS patch)

直接修改编译后的 JS 文件：
- `loader-Ds3or8QX.js`: `maxConcurrent: 1` → `maxConcurrent: 4`
- `extensionAPI.js`: 同上
- （注意：这个 patch 在重新安装 2.9 后需要重新应用）

## 测试清单

### 基本功能
- [ ] 私聊消息正常响应
- [ ] 群聊消息正常响应（使用 `*` 通配符配置）
- [ ] `requireMention: false` 生效
- [ ] 多 session 并发不阻塞（maxConcurrent: 4）

### 流式卡片
- [ ] 收到消息后出现 ⏳ Thinking... 卡片
- [ ] 卡片内容实时更新（打字机效果）
- [ ] 长回复：卡片保留并正常关闭（显示 summary）
- [ ] 短回复（<100 字）：卡片删除，发送正常消息
- [ ] NO_REPLY / HEARTBEAT_OK：卡片静默删除
- [ ] 多 turn 对话：新 turn 开始新卡片

### @mention
- [ ] 群聊中 @Luna 后，bot 的 @mention 被正确移除
- [ ] @其他用户 的 mention 保留为 `@Name` 文本

### 回归测试
- [ ] /new 和 /reset 命令正常工作
- [ ] 子任务 NO_REPLY 不触发多余 announce
- [ ] 图片/文件消息正常处理
- [ ] 心跳正常运行

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `~/.openclaw-staging/openclaw.json` | 新建 | 预发布配置 |
| `~/.openclaw-staging/openclaw-staging.sh` | 新建 | 便捷启动脚本 |
| `~/.config/systemd/user/openclaw-staging.service` | 新建 | systemd 服务 |
| `extensions/feishu/src/streaming.ts` | 新增 | 流式卡片实现 |
| `extensions/feishu/src/reply-dispatcher.ts` | 修改 | 注入 onPartialReply |
| `extensions/feishu/src/policy.ts` | 修改 | 添加 `*` 通配符 |
| `extensions/feishu/src/bot.ts` | 修改 | 保留非 bot @mention |
| `dist/loader-Ds3or8QX.js` | 修改 | maxConcurrent: 4 |
| `dist/extensionAPI.js` | 修改 | maxConcurrent: 4 |

## 升级生产的步骤（验证通过后）

```bash
# 1. 停止生产
systemctl --user stop openclaw-gateway.service

# 2. 升级
npm update -g openclaw@2026.2.9

# 3. 复制扩展修改
cp ~/.openclaw-staging/npm/lib/node_modules/openclaw/extensions/feishu/src/streaming.ts \
   ~/.npm-global/lib/node_modules/openclaw/extensions/feishu/src/

cp ~/.openclaw-staging/npm/lib/node_modules/openclaw/extensions/feishu/src/reply-dispatcher.ts \
   ~/.npm-global/lib/node_modules/openclaw/extensions/feishu/src/

cp ~/.openclaw-staging/npm/lib/node_modules/openclaw/extensions/feishu/src/policy.ts \
   ~/.npm-global/lib/node_modules/openclaw/extensions/feishu/src/

cp ~/.openclaw-staging/npm/lib/node_modules/openclaw/extensions/feishu/src/bot.ts \
   ~/.npm-global/lib/node_modules/openclaw/extensions/feishu/src/

# 4. 应用 lane patch
LOADER=$(ls ~/.npm-global/lib/node_modules/openclaw/dist/loader-*.js)
sed -i 's/maxConcurrent: 1,/maxConcurrent: 4,/' "$LOADER"
EXTAPI=~/.npm-global/lib/node_modules/openclaw/dist/extensionAPI.js
sed -i 's/maxConcurrent: 1,/maxConcurrent: 4,/' "$EXTAPI"

# 5. 清理旧 plugin 配置
# 编辑 ~/.openclaw/openclaw.json，移除 plugins.load.paths 中的 feishu-webhook
# 移除 plugins.entries.feishu

# 6. 启动生产
systemctl --user start openclaw-gateway.service
```

## Tailscale Funnel 配置

已添加：
```
https://anz-luna.grolar-wage.ts.net/staging → http://127.0.0.1:18790
```

清理（升级完成后）：
```bash
sudo tailscale funnel --set-path /staging off
```
