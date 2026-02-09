# Lark Webhook via Tailscale 配置指南

## 当前状态

| 组件 | 状态 |
|------|------|
| Lark MCP (发送消息) | ✅ 已配置，工作正常 |
| Webhook 接收服务 | ✅ 已部署在 localhost:3000 |
| Tailscale | ⚠️ 需要登录 |
| 安全公网访问 | ❌ 待配置 |

---

## 方案选择

### 方案 A: Tailscale Funnel（推荐）

将本地 webhook 通过 Tailscale 安全暴露到公网，**无需开放 AWS 端口**。

**优点：**
- ✅ 加密连接（HTTPS）
- ✅ Tailscale 认证层
- ✅ 无需 AWS 安全组配置
- ✅ 稳定域名（如 `https://machine.tailnet.ts.net`）

**步骤：**

1. **登录 Tailscale**
   ```bash
   tailscale up
   ```
   访问输出的 URL 完成认证

2. **启用 Funnel**（需要 Tailscale 付费计划）
   ```bash
   tailscale funnel 3000
   ```

3. **获取公网 URL**
   ```bash
   tailscale status
   ```
   复制 `https://<machine-name>.<tailnet-name>.ts.net`

4. **配置 Lark**
   - 访问 https://open.larksuite.com
   - 应用 → Events → Event Subscription
   - Request URL: `https://<your-machine>.ts.net/webhook/lark`

---

### 方案 B: 纯 Tailscale 内网

如果 Lark 服务器也在同一个 Tailscale 网络内（企业部署）。

**Webhook URL:**
```
http://<tailscale-ip>:3000/webhook/lark
```

---

### 方案 C: 反向代理（使用 80/443 端口）

如果已有 Nginx/Apache 在 80/443 端口。

**Nginx 配置示例：**
```nginx
location /webhook/lark {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

---

## 快速开始

### 1. 启动 Webhook 服务

```bash
# 已经在运行
curl http://127.0.0.1:3000/webhook/lark \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test"}'
```

### 2. 选择你的方案

**如果你能访问 Tailscale 控制台**（有 admin 权限）：
- 选择方案 A（Funnel）

**如果你有企业 Lark + Tailscale**（同网络）：
- 选择方案 B（内网）

**如果你有 Nginx**：
- 选择方案 C（反向代理）

---

## 现在执行

请运行以下命令并告诉我结果：

```bash
# 1. 登录 Tailscale
tailscale up

# 2. 检查状态
tailscale status

# 3. 如果是付费账户，启用 funnel
tailscale funnel 3000
```

**或者**告诉我你有哪种基础设施：
- A. Tailscale 账户（可登录）
- B. Nginx/Apache（已配置）
- C. 其他方案
