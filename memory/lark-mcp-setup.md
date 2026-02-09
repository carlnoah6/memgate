# Lark OpenAPI MCP 配置指南

## 官方 MCP Server
**包名**: `@larksuiteoapi/lark-mcp`
**文档**: https://github.com/larksuite/lark-openapi-mcp

---

## 配置步骤

### 步骤 1: 创建 Lark 应用

1. 访问 https://open.larksuite.com (国际版) 或 https://open.feishu.cn (国内版)
2. 点击「Console」→「Create App」
3. 选择「Internal App」
4. 记录 **App ID** 和 **App Secret**
5. 添加所需权限：
   - `im:chat:readonly` (读取会话)
   - `im:message:send` (发送消息)
   - `im:message:receive` (接收消息)
   - `contact:user:readonly` (读取用户信息)
6. 发布应用（Release → Create Version → Submit）

### 步骤 2: 安装 MCP Server

```bash
npm install -g @larksuiteoapi/lark-mcp
```

### 步骤 3: 配置 OpenClaw

在 `clawdbot config` 中添加 MCP server：

```json
{
  "mcpServers": {
    "lark": {
      "command": "npx",
      "args": ["-y", "@larksuiteoapi/lark-mcp"],
      "env": {
        "LARK_APP_ID": "your-app-id",
        "LARK_APP_SECRET": "your-app-secret",
        "LARK_BASE_URL": "https://open.larksuite.com/open-apis"  // 或 feishu.cn
      }
    }
  }
}
```

### 步骤 4: 获取 User ID

要让机器人发送消息给特定用户，需要获取 Open ID：

```bash
# 通过 Lark API 获取
# 或在 Lark 客户端中查看用户资料 → 复制用户 ID
```

---

## 支持的 MCP 工具

| 工具名 | 功能 |
|--------|------|
| `lark_send_message` | 发送消息 |
| `lark_receive_message` | 接收消息 |
| `lark_create_chat` | 创建群聊 |
| `lark_get_chat_history` | 获取聊天记录 |
| `lark_upload_file` | 上传文件 |
| `lark_create_calendar_event` | 创建日程 |
| ... | ... |

---

## Webhook 接收消息（可选）

如需实时接收消息：

1. 在 Lark 应用后台设置「Event Subscription」
2. 配置回调 URL: `https://your-openclaw-server/webhook/lark`
3. 订阅 `im.message.receive_v1` 事件

---

## 下一步

1. 我需要你提供 **App ID** 和 **App Secret**
2. 或者指导你完成创建应用的全过程
3. 配置完成后测试发送/接收消息

**准备好了吗？** 你可以：
- A. 直接给我 App ID 和 App Secret
- B. 我指导你一步步创建应用
