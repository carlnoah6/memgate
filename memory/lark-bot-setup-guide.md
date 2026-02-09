# Lark 机器人添加到对话指南

## 前提条件

在 https://open.larksuite.com 完成以下配置：

### 1. 开启机器人能力

进入应用后台 → **Bot** → 开启 **Enable Bot**

### 2. 添加权限

进入 **Permissions** → 添加以下权限：
- ✅ `im:chat:readonly` - 读取会话信息
- ✅ `im:message:send` - 发送消息
- ✅ `im:message:receive` - 接收消息
- ✅ `contact:user:readonly` - 读取用户信息（获取用户 ID）

### 3. 配置事件订阅（接收消息需要）

进入 **Events** → 开启事件订阅：
- 订阅事件: `im.message.receive_v1`
- 回调地址: 需要配置 webhook（可选，用于自动接收）

### 4. 发布应用

进入 **Release** → **Create Version** → 提交审核
- 选择 "Make available to members under your organization only"
- 无需审核，立即生效

---

## 添加机器人到对话

### 方式 A: 私聊（1对1）

在 Lark 客户端搜索你的机器人名称 → 点击开始聊天

### 方式 B: 群聊

1. 进入目标群聊
2. 点击右上角 **Settings** → **Apps**
3. 搜索你的应用名称 → 添加
4. 或在群里 @机器人 直接添加

---

## 获取会话 ID (Chat ID)

发送消息需要 Chat ID，获取方式：

### 方法 1: 通过 Lark API

```bash
curl -X GET "https://open.larksuite.com/open-apis/im/v1/chats" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### 方法 2: 通过 webhook 事件

当用户首次给机器人发消息时，webhook 会推送包含 chat_id 的事件

### 方法 3: 在 Lark 客户端查看

电脑端 Lark → 右键点击群聊 → 查看群信息 → 复制群 ID

---

## 测试发送消息

有了 Chat ID 后，可以通过 API 发送消息：

```bash
curl -X POST "https://open.larksuite.com/open-apis/im/v1/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "receive_id": "chat_id_here",
    "msg_type": "text",
    "content": "{\"text\":\"Hello from Luna!\"}"
  }'
```

---

## 下一步

1. 确认已在 Lark 后台发布应用
2. 将机器人添加到测试群聊
3. 获取 Chat ID
4. 通过 MCP 工具发送测试消息
