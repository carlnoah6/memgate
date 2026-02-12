# 流式卡片升级方案

## 调查结果

### 版本流式卡片支持情况

| 版本 | FeishuStreamingSession | CardKit API 调用 | 流式卡片 |
|------|----------------------|-----------------|---------|
| 2026.2.3 | ✅ 在 `plugin-sdk/index.js` 核心中 | ✅ | ✅ 原生支持 |
| 2026.2.3-1 | ✅ 同上（当前安装 + 5 个 patch） | ✅ | ✅ 完善版 |
| 2026.2.6-1 | ❌ 已移除 | ❌ | ❌ |
| 2026.2.6-2 | ❌ | ❌ | ❌ |
| 2026.2.6-3 | ❌ | ❌ | ❌ |
| 2026.2.6 | ❌ | ❌ | ❌ |
| 2026.2.9 | ❌ | ❌ | ❌ |

**结论：流式卡片从 2.6-1 开始被完全移除，所有 2.6+ 版本都没有。**

### 2.9 架构分析

2.9 对飞书做了重大架构变更：
- **飞书从核心代码移到独立扩展** (`extensions/feishu/src/`)
- **扩展是 TypeScript 源码**，运行时编译，修改 `.ts` 文件即可生效
- **核心 API 仍然支持 `onPartialReply` 回调** — 这是流式卡片的关键 hook
- 当前飞书扩展**没有使用** `onPartialReply`，仅用了 Typing emoji 反应作为"正在输入"指示器
- `send.ts` 已有 `sendCardFeishu()` 和 `updateCardFeishu()` — 卡片发送/更新基础设施已就绪

### 2.9 重新实现流式卡片的可行性：🟢 高

**理由：**

1. **`onPartialReply` 回调完好** — `GetReplyOptions.onPartialReply` 接口未变，可以在 `reply-dispatcher.ts` 返回的 `replyOptions` 中注入
2. **扩展可直接修改** — TypeScript 源码，改完重启即可，无需 Python patch
3. **CardKit API 不依赖 SDK 版本** — 流式卡片用的是飞书 REST API (`/cardkit/v1/cards`)，不受 OpenClaw 版本影响
4. **现有代码可参考** — 当前 2.3-1 的 `FeishuStreamingSession` 类 ~80 行，逻辑清晰
5. **`send.ts` 已有卡片基础** — `sendCardFeishu`, `updateCardFeishu`, `buildMarkdownCard` 已实现

## 具体代码修改方案

### 需要修改/新增的文件

#### 1. 新增 `extensions/feishu/src/streaming.ts`（~120 行）

```typescript
// 实现 FeishuStreamingSession 类
// 包含：
// - getTenantAccessToken() — 获取应用令牌（带缓存）
// - createStreamingCard() — 创建流式卡片
// - sendStreamingCard() — 发送卡片消息
// - updateStreamingCardText() — 更新卡片内容
// - closeStreamingMode() — 关闭流式模式
// - FeishuStreamingSession class — 高级会话管理器
//
// 直接从当前 2.3-1 的 plugin-sdk/index.js 中提取，
// 仅需将 credentials 参数改为使用 ResolvedFeishuAccount 类型
```

CardKit API 端点（不依赖 SDK，直接 fetch）：
- `POST /open-apis/cardkit/v1/cards` — 创建卡片
- `PUT /open-apis/cardkit/v1/cards/{card_id}/elements/{element_id}/content` — 更新元素
- `PATCH /open-apis/cardkit/v1/cards/{card_id}/settings` — 关闭流式模式
- `POST /open-apis/auth/v3/tenant_access_token/internal` — 获取令牌

#### 2. 修改 `extensions/feishu/src/reply-dispatcher.ts`

关键修改点：

```typescript
// 1. 导入流式会话
import { FeishuStreamingSession } from "./streaming.js";

// 2. 在 createFeishuReplyDispatcher 中：
//    a. 创建 streamingSession 实例
//    b. 在 deliver 中处理流式卡片的关闭
//    c. 返回的 replyOptions 中注入 onPartialReply

// 伪代码：
const streamingSession = new FeishuStreamingSession(account);
let streamingStarted = false;

// deliver 回调中添加：关闭流式卡片，然后发送最终消息
// onPartialReply 回调：创建/更新流式卡片

return {
  dispatcher,
  replyOptions: {
    ...replyOptions,
    onModelSelected: prefixContext.onModelSelected,
    onPartialReply: async (payload) => {
      if (!payload.text) return;
      if (!streamingSession.isActive() && !streamingStarted) {
        await streamingSession.start(chatId);
        streamingStarted = true;
      }
      if (streamingSession.isActive()) {
        await streamingSession.update(payload.text);
      }
    },
  },
};
```

#### 3. 可选：添加配置项

在 `config-schema.ts` 中添加 `streaming` 配置选项：
```typescript
streaming: z.boolean().optional(), // 默认 true，可通过配置关闭
```

### 当前 patch 逻辑的移植

| 当前 Patch | 2.9 扩展中的处理 |
|-----------|----------------|
| `apply-feishu-streaming-fix.py` — 跨 turn 文本重复修复 | 在 `onPartialReply` handler 中用 `lastRawPayloadText` 检测 turn 切换 |
| `fix-streaming-card-ux.py` — 工具状态显示 | 通过 `onAgentEvent` 监听 tool 事件，更新卡片显示工具状态 |
| `fix-streaming-race-condition.py` — 竞态条件 | `FeishuStreamingSession.start()` 中添加 `_starting` 守卫 |
| `fix-streaming-cross-session.py` — 跨会话问题 | 在 session key 匹配逻辑中处理 |
| `fix-streaming-silent-reply.py` — 静默回复 | deliver 回调中处理空回复场景 |

## 推荐方案

### 🏆 方案 A：升级到 2.9 + 在扩展中重新实现流式卡片（推荐）

**步骤：**
1. 升级 OpenClaw 到 2.9
2. 创建 `extensions/feishu/src/streaming.ts`（从 2.3-1 提取 CardKit API 代码）
3. 修改 `extensions/feishu/src/reply-dispatcher.ts`（注入 `onPartialReply`）
4. 将当前 5 个 patch 的逻辑内化到 TypeScript 代码中
5. 删除所有 Python patch 脚本（不再需要）

**优势：**
- 获得 2.9 所有新功能和修复
- TypeScript 源码比 Python patch 更易维护
- 未来升级不需要重新适配 patch
- 扩展代码独立于核心，不会被升级覆盖

**工作量：** ~2-3 小时编码 + 测试

### 方案 B：留在 2.3-1

**优势：** 零风险，当前已完美工作
**劣势：** 错过 6 个版本的改进，越来越难升级

### ~~方案 C：升级到 2.6~~

**不推荐：** 2.6 没有流式卡片，且 2.6 的飞书代码仍在核心中（不是扩展），修改同样需要 patch，没有比 2.9 更好。

## 风险评估

### 方案 A 风险

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| CardKit API 行为变化 | 🟢 低 | API 是飞书的，与 OC 版本无关 |
| `onPartialReply` 时序不同 | 🟡 中 | 需要测试 partial reply 触发频率和顺序 |
| 扩展加载顺序问题 | 🟢 低 | 飞书扩展已是标准配置 |
| 工具状态显示 | 🟡 中 | 需要确认 2.9 的 `onAgentEvent` 是否还在扩展可用范围内 |
| 配置格式变化 | 🟢 低 | 2.9 的飞书配置向后兼容 |

### 关键验证点
1. 确认 `onPartialReply` 在 2.9 中的 partial text 增长模式与 2.3-1 一致
2. 确认扩展中可以使用 `fetch()` 直接调用飞书 API
3. 确认 `disableBlockStreaming` 设为 true 时 `onPartialReply` 会被调用
4. 测试 streaming card 创建 → 更新 → 关闭的完整流程

## 下一步

如果选择方案 A：
1. 先在测试环境安装 2.9：`npm install -g openclaw@2026.2.9`
2. 编写 `streaming.ts` 并修改 `reply-dispatcher.ts`
3. 用一个测试群验证流式卡片效果
4. 确认无误后切换生产环境
