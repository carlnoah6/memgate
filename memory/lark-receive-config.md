# Lark 消息接收配置

## 当前状态

### ✅ 已配置
- MCP server 可以**发送**消息 (`im_v1_message_create`)
- 可以获取聊天记录 (`im_v1_message_list`)

### ❌ 未配置
- Webhook 接收实时消息推送
- 需要配置回调 URL

---

## 接收消息的两种方式

### 方式 1: Webhook 推送（实时）

**Lark 后台配置：**
1. 进入 https://open.larksuite.com
2. 应用 → Events → 开启事件订阅
3. 配置回调 URL: `https://your-server/webhook/lark`
4. 订阅事件: `im.message.receive_v1`
5. 验证回调地址（Lark 会发送 challenge 验证）

**OpenClaw 配置：**
需要设置 webhook 接收端点

### 方式 2: 轮询获取（定时检查）

使用 `im_v1_message_list` 工具定期获取消息：

```json
{
  "container_id_type": "chat",
  "container_id": "chat_id_here",
  "start_time": "1700000000"
}
```

---

## 当前可行方案

由于我们没有公网 webhook 地址，可以使用**轮询方式**：

1. 用户告诉我一个 chat_id
2. 我定期调用 `im_v1_message_list` 获取新消息
3. 回复到该对话

---

## 如何获取 Chat ID

**方法 1: 通过 API 查询**
```bash
curl "https://open.larksuite.com/open-apis/im/v1/chats" \
  -H "Authorization: Bearer $TOKEN"
```

**方法 2: 从 Lark 客户端获取**
- 电脑端 Lark → 右键群聊 → 群信息 → 复制群 ID

---

## 下一步

**选项 A**: 提供一个 **chat_id**，我开始轮询获取消息
**选项 B**: 配置 webhook（需要公网服务器或内网穿透）
**选项 C**: 先测试发送消息，确认发送功能正常

你想选哪个？
