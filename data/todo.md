# Todo - 待修复问题

## 待办

### 1. API 代理层 Fallback（替代 OpenClaw 内置 fallback）
- **问题**：OpenClaw 内置 fallback 机制有严重问题
  - 切换慢：额度用完后反复聊天仍用旧模型
  - 状态不稳定：成功切到备用模型后又会自动切回去
- **方案**：在 api-proxy 层实现 fallback
  - 代理收到 429/额度用尽错误 → 自动切备用 key/endpoint → 重试
  - 对 OpenClaw 完全透明，无需感知
- **位置**：`/home/ubuntu/api-proxy/server.py`
- **状态**：待实现
- **记录日期**：2026-02-09

### 2. 重启来源追踪 & 回复路由
- **问题**：重启可能从任何 session 触发（主 session、群聊 session 等），但重启后的汇报只回到主 session，触发重启的 session 不知道结果
- **方案**：
  - `mark-restart.sh` 记录触发来源（session key、chat_id）
  - 重启后由正确的 session 识别并返回消息，避免串台
  - 所有 session 都应走统一的重启流程（不只是主 session）
- **状态**：待实现
- **记录日期**：2026-02-09
