# 重启来源追踪与回复路由方案

**日期**: 2026-02-10
**作者**: Luna Subagent

## 背景
此前 Gateway 重启后，无论是由谁（Main Session 或某个群聊）触发，重启完成后的汇报（"Gateway has restarted..."）总是出现在 Main Session。这导致在群聊中触发重启的用户无法得到反馈。

## 目标
实现 **"谁触发，汇报给谁"** 的路由机制。

## 实现方案

### 1. 状态持久化
修改了重启标记机制，使其不仅记录"重启原因"，还记录"来源 Session"。

- **文件**: `/tmp/luna-pending-restart.marker`
- **格式**: JSON
  ```json
  {
    "reason": "Upgrade config",
    "source_session": "session:group:12345",
    "timestamp": "2026-02-10T12:00:00Z"
  }
  ```

### 2. 脚本修改

#### `scripts/mark-restart.sh`
- **新增参数**: 接受第二个参数 `source_session`。
- **安全性**: 改用 Python 生成 JSON，防止 Shell 字符串拼接导致的 JSON 格式错误（如引号问题）。

#### `scripts/restart-gateway.sh`
- **透传参数**: 将调用时的第二个参数传给 `mark-restart.sh`。
- **默认值**: 若未指定，默认为 `main`。

#### `scripts/check-restart.sh`
- **读取输出**: 检测到标记文件时，输出包含 `source_session` 的完整 JSON 结构。
- **输出示例**:
  ```text
  RESTART_INFO: {"reason": "...", "source_session": "...", ...}
  ```

### 3. 路由逻辑 (Agent 侧)
主 Agent 在启动时运行 `check-restart.sh`。如果检测到 `RESTART_INFO`，应解析 JSON：
- 如果 `source_session` == `main` (或为空): 直接在当前 Session 汇报。
- 如果 `source_session` != `main`: 使用 `message` 工具向该 `source_session` 发送汇报消息。

## 验证
已通过手动运行 `mark-restart.sh` 和 `check-restart.sh` 验证了数据流的完整性和 JSON 格式的正确性。
