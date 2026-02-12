# OS Mode 稳定性与监控

> 目标：确保 Luna OS 能够 7x24 小时稳定运行，任务不丢失、不卡死，且状态实时可见。

## 核心架构

OS Mode 的稳定性依赖于以下几个核心组件的协同工作：

1. **Heartbeat (心跳驱动)**
   - 频率：每 5 分钟
   - 作用：作为系统的"脉搏"，驱动所有定时检查、任务调度和状态刷新。
   - 机制：不依赖传统的 cron job (不稳定)，而是由主进程的心跳事件触发 `HEARTBEAT.md` 流程。

2. **Watchdog (看门狗)**
   - 脚本：`scripts/watchdog-log.py`
   - 作用：防止 LLM "Thinking" 过程卡死。
   - 逻辑：如果系统处于 busy 状态但日志超过 3 分钟无输出，判定为僵死进程，自动触发重启。

3. **Task Health Check (任务健康检查)**
   - 脚本：`scripts/task-health-check.py`
   - 作用：监控后台异步任务的状态。
   - 逻辑：
     - 检查是否有运行超过 35 分钟的任务（`stale`）。
     - 自动将卡死任务标记为 `failed`。
     - 清理过期的旧任务记录。

4. **Live Status Dashboard (实时状态看板)**
   - 脚本：`scripts/task-dashboard.py`
   - 作用：在 Lark 群聊中维护一个持久化的状态卡片。
   - 特性：
     - **持久化**：不是发送新消息，而是通过 `message_id` 不断更新同一个卡片，避免刷屏。
     - **实时性**：每次心跳检查状态，有变化立即刷新。
     - **视觉反馈**：
       - 🟢 **Green**: 系统空闲/正常
       - 🔵 **Blue**: 有任务正在运行
       - 🔴 **Red**: 今日有失败任务（需关注）

## 实时看板 (Live Dashboard)

看板部署在「Luna 任务板」群聊中，提供以下视图：

- **🏃 In Progress**: 当前正在运行的任务（显示开始时间）。
- **💤 Queued**: 等待执行的任务队列（显示依赖关系）。
- **⚠️ Failed Today**: 今日失败的任务及错误原因（高亮显示）。
- **✨ Done Today**: 今日完成的任务列表（最近 5 条）。

### 手动刷新
通常不需要手动刷新，心跳会自动处理。如需强制刷新：
```bash
python3 scripts/task-dashboard.py --force
```

## 重启与恢复

系统具备自动重启恢复能力：

- **触发**：Watchdog 发现卡死，或检测到关键 patch 更新。
- **流程**：
  1. `mark-restart.sh` 记录重启原因和来源 session。
  2. Gateway 重启。
  3. `check-restart.sh` 在启动时运行，读取标记。
  4. 自动路由汇报消息回原 session（如从群聊触发，则回群聊汇报）。

## 监控指标

| 指标 | 阈值 | 处理 |
|------|------|------|
| Thinking 超时 | > 3 min | Watchdog 重启 Gateway |
| 任务运行时间 | > 35 min | Health Check 标记失败 |
| 任务队列堆积 | > 3 个并发 | 调度器排队等待 (Queued) |
