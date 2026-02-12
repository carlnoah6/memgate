# Lark 卡片更新技术参考

> 2026-02-12 调试仪表盘刷新按钮时的完整记录

## 核心结论

**更新 Lark 交互式卡片（interactive message）有且仅有一种正确方式：**

```
POST /open-apis/interactive/v1/card/update
Authorization: Bearer <tenant_access_token>

{
  "token": "<card_action_token>",    // 来自回调 event.token
  "card": {
    "open_ids": ["ou_xxx"],          // 必须在 card 内部
    "header": {...},
    "elements": [...]
  }
}
```

## ❌ 错误方式（全部踩过的坑）

### 1. PATCH /im/v1/messages/{message_id}
- **现象**：API 返回 `code: 0 success`，服务端内容确实更新
- **问题**：Lark 客户端**不会重新渲染**交互式卡片
- **结论**：PATCH 只适用于 text/post 消息，不适用于 interactive cards

### 2. 回调直接返回卡片 JSON
- **尝试**：在回调响应中返回 `{"header":...,"elements":...}` 
- **结果**：Lark 报错 `200341`
- **原因**：v1 卡片的回调响应格式不支持直接返回卡片内容

### 3. 回调返回 `{}`
- **现象**：Lark 报错 `200341`
- **结论**：空 JSON 不是合法的回调响应

### 4. card/update 不带 Authorization
- **结果**：`99991661 "Missing access token for authorization"`
- **修复**：必须带 `Authorization: Bearer <tenant_access_token>`

### 5. open_ids 放在顶层
- **尝试**：`{"token":"...", "card":{...}, "open_ids":["ou_xxx"]}`
- **结果**：`300090 "openid empty err"`
- **修复**：`open_ids` 必须在 `card` 对象内部

## ✅ 正确流程

1. 用户点击卡片按钮
2. Lark 发送回调到 webhook-gateway（POST /webhook/lark）
3. webhook-gateway 从回调体提取：
   - `event.token` → card_action_token（用于 card/update API）
   - `event.operator.open_id` → 操作者 ID（放入 card.open_ids）
4. 运行 `lark-card-builder.py` 构建新卡片 JSON
5. 将 `open_ids` 插入 card 对象内部
6. 调用 `POST /interactive/v1/card/update`（带 tenant_access_token）
7. **回调响应返回 toast**（不是 `{}`）：
   ```json
   {"toast": {"type": "success", "content": "✅ 已刷新"}}
   ```

## 回调体结构（v2 schema）

```json
{
  "schema": "2.0",
  "header": {
    "event_type": "card.action.trigger",
    "token": "8k6S...",           // 事件验证 token（不是 card token）
    "app_id": "cli_xxx"
  },
  "event": {
    "operator": {
      "open_id": "ou_xxx",        // 点击者
      "tenant_key": "xxx"
    },
    "token": "c-7ec7a...",        // ← 这个才是 card_action_token
    "action": {
      "value": {"action": "refresh_dashboard"},
      "tag": "button"
    },
    "context": {
      "open_message_id": "om_xxx",
      "open_chat_id": "oc_xxx"
    }
  }
}
```

**注意区分两个 token：**
- `header.token` = 事件验证 token（用于验证回调来源）
- `event.token` = card action token（用于 card/update API）

## 文件位置

| 文件 | 用途 |
|------|------|
| `webhook-gateway/src/webhook/lark.py` | 回调处理 + card/update 调用 |
| `scripts/lark-card-builder.py` | 构建卡片 JSON（stdout 输出） |
| `scripts/lark-task-dashboard.py` | 发送/PATCH 仪表盘（心跳用） |
| `scripts/session-overview.py` | 收集 session 数据 |
| `data/dashboard-state.json` | 记录当前卡片 message_id |

## 两种更新场景

| 场景 | 方式 | 触发 |
|------|------|------|
| 用户点「刷新」按钮 | card/update API（通过 webhook-gateway） | 按钮回调 |
| 心跳/定时刷新 | lark-task-dashboard.py（发新卡片或 PATCH） | 心跳调度 |

> PATCH 方式虽然不触发客户端刷新，但在心跳场景下是可接受的——
> 下次用户点「刷新」时会通过 card/update 获得最新数据。
