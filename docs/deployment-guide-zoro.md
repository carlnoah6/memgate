# OpenClaw 独立实例部署复盘 (Zoro)

**目标**: 为用户 Junyi 部署一个独立的 OpenClaw 实例 "Zoro"，连接 Lark (国际版)，环境隔离。

## 1. 基础设施
- **服务器**: AWS EC2 `18.141.174.141` (Ubuntu 24.04 LTS)
- **网络**: Tailscale Funnel (无入站端口开放)
  - Tailnet: `carlnoah6@` (隔离于 Luna 的 `adam429.lee@`)
  - 公网 URL: `https://junyi-zoro.tail53a6e0.ts.net`
  - 机器名: `junyi-zoro`
- **安全**:
  - AWS Security Group: 仅开放 SSH (22)
  - Webhook: 走 Funnel HTTPS -> localhost:18789

## 2. 软件栈
- **Node.js**: v22.22.0 (通过 nvm 安装)
- **OpenClaw**: v2026.2.3-1 (npm install -g)
  - **重要**: 必须降级到此版本，2026.2.9 内置的 `feishu` 扩展不支持 Webhook 模式，会强制走 WebSocket (Lark 不支持) 导致崩溃。
- **Plugin**: 自定义 `feishu-webhook` (从 Luna 复制)
  - 路径: `/home/ubuntu/.openclaw/plugins/feishu-webhook`
  - 补丁: 支持富文本 (`post`) 消息类型

## 3. 关键配置与补丁

### 3.1 避免内置扩展冲突
2026.2.9+ 版本内置 `feishu` 扩展会覆盖自定义插件。
**操作**: 将内置扩展移走备份。
```bash
mv /usr/lib/node_modules/openclaw/extensions/feishu /tmp/openclaw-feishu-builtin-backup
```

### 3.2 修复 WebSocket 崩溃 (WSClient)
Lark (国际版) 不支持 WebSocket，但 `monitorFeishuProvider` 默认尝试连接 WS，导致 404 错误并使 Gateway 崩溃。
**补丁**: 修改 `/usr/lib/node_modules/openclaw/dist/plugin-sdk/index.js`
- 强制使用 `onEventDispatcher` 回调
- 跳过 WSClient 初始化
- 详见 `patches/fix-zoro-ws.py` (已删除，代码逻辑见 Luna 记忆)

### 3.3 支持富文本消息 (Post)
Lark 客户端发送的消息常为 `post` 类型（富文本），默认插件只支持 `text`，会导致消息被忽略。
**补丁**: 修改 `/usr/lib/node_modules/openclaw/dist/plugin-sdk/index.js`
- `SUPPORTED_MSG_TYPES` 添加 `"post"`
- `processFeishuMessage` 添加 `post` 内容解析逻辑 (提取纯文本)

### 3.4 保持服务运行 (Linger)
SSH 断开后 Systemd 用户服务会被杀掉。
**操作**: 启用 linger。
```bash
loginctl enable-linger ubuntu
```

### 3.5 Systemd 服务
创建 `~/.config/systemd/user/openclaw-gateway.service`
```ini
[Unit]
Description=OpenClaw Gateway
After=network.target

[Service]
ExecStart=/usr/bin/node /usr/lib/node_modules/openclaw/dist/gateway-cli-c_8Yf5s6.js gateway start
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin
Environment=NODE_ENV=production

[Install]
WantedBy=default.target
```
启用: `systemctl --user enable --now openclaw-gateway`

## 4. Lark 配置
- **App ID**: `cli_a90632d51b789eee`
- **App Secret**: `WzJXr87GM5uzNmGGPtUSGbPSj8ne5tkO`
- **权限 Scopes**:
  - `im:message`
  - `im:message:send_as_bot`
  - `im:message.p2p_msg:readonly`
  - `im:message.group_at_msg:readonly`
  - `im:chat:readonly`
  - `im:resource`
  - **`cardkit:card:write`** (关键：用于流式卡片回复)
- **事件订阅**:
  - 请求地址: `https://junyi-zoro.tail53a6e0.ts.net/webhook/lark`
  - 事件: `im.message.receive_v1`

## 5. 验证清单
1. **Webhook**: Lark 后台 "请求地址" 保存成功 (返回 challenge)
2. **消息接收**: 给 Bot 发消息，日志显示 `Received Feishu webhook event`
3. **LLM 调用**: 日志显示 `embedded run start`
4. **消息回复**: 日志显示 `Sent streaming card message`
5. **流式效果**: Bot 回复时有打字机效果 (需 `cardkit:card:write`)

## 6. 遗留/注意事项
- **Funnel 稳定性**: 曾出现间歇性 502，启用 linger 后解决。需观察。
- **OpenClaw 升级**: 升级后需重新应用 Patch (WSClient + Post Support) 并移除内置 feishu 扩展。
- **API Key**: 使用 Luna 的 API Proxy (`sk-zoro-2026-openclaw`)，额度共享但可独立统计。
