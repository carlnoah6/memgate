# Luna 主对话卡死排查报告

**日期**: 2026-02-12  
**事件**: Luna 机器人在「Luna 机器人主对话」群聊中完全不响应  
**报告时间**: ~05:55 SGT (21:55 UTC)  
**恢复时间**: ~06:29 SGT (22:29 UTC) — Carl 手动重启 gateway  

---

## 一、事件时间线（关键节点）

| 时间 (UTC) | 时间 (SGT) | 事件 |
|---|---|---|
| 16:34:27 | 00:34 | 旧 gateway (PID 31195) 停止 |
| 16:34:28 | 00:34 | 临时 gateway (PID 42571) 启动 |
| 16:34:44 | 00:34 | PID 42571 立即被停止（仅运行 12 秒） |
| 16:48:17 | 00:48 | **PID 43765 启动**（故障进程） |
| 16:48:31 | 00:48 | 正常接收 Feishu webhook，开始处理消息 |
| 16:49-17:12 | 00:49-01:12 | 正常工作：agent run、tool calls、streaming 回复 |
| **17:16:56** | **01:16** | **🔴 关键事件：`embedded run timeout` — runId=ff40afb6, sessionId=126f4a5f, timeoutMs=600000 (10分钟超时)** |
| 17:17-18:07 | 01:17-02:07 | 仅 `sessions.delete` 操作（来自 UI），**无 Feishu 消息处理** |
| 18:29:15 | 02:29 | 最后一次有意义的活动 (node.list) |
| 18:29-21:53 | 02:29-05:53 | **死区：~3.5 小时完全无活动**（仅每分钟 Config warnings） |
| 21:53:42 | 05:53 | Carl 开始向主对话发消息 → 无回复 |
| 21:55:19-58 | 05:55 | Carl 密集发送 5 条消息 → 均无回复 |
| 22:12-22:29 | 06:12-06:29 | 继续收到 webhook，但所有消息无回复 |
| **22:29:37** | **06:29** | **Carl 手动 `openclaw gateway restart` → PID 63601 启动，恢复正常** |

---

## 二、根因分析

### 主因：Agent 运行超时导致 Lane 阻塞

**直接原因**：在 `17:16:56 UTC` (01:16 SGT)，一个 embedded agent run 触发了 10 分钟超时：

```
[agent/embedded] embedded run timeout: runId=ff40afb6-5398-4463-a83b-e5985f728cc5 
  sessionId=126f4a5f-f75f-49e8-a130-6d79682e0d0b timeoutMs=600000
```

这个超时后，**`main` lane（全局消息处理队列）进入了阻塞状态**。所有后续消息虽然通过 Feishu webhook 正常接收，但被排入 lane 队列后永远无法被消费。

**证据**：
1. 超时前：有正常的 `lane enqueue → lane dequeue → run start → run end` 循环
2. 超时后：再也看不到任何 `lane dequeue` 或 `run start` 日志
3. Feishu webhook 持续接收消息（`Received Feishu webhook event: type=im.message.receive_v1` 持续出现）
4. 但没有任何新的 agent run 被触发

**推测机制**：超时处理可能没有正确释放 lane 锁，或者 session 状态从 `processing` 没有回退到 `idle`，导致 lane 认为有活跃 run 在执行，拒绝 dequeue 新任务。

### 附因 1：看门狗 Python Bug 导致自动恢复失败

看门狗 (`independent-watchdog.py`) 每 3 分钟运行一次，它**检测到了问题**但**因 Python 语法错误而崩溃**，无法执行重启操作：

```python
ValueError: Invalid format specifier '.0f if hb_minutes else '?'' for object of type 'float'
```

**错误代码位置**: `independent-watchdog.py` 第 450 行：
```python
f"心跳停止 {hb_minutes:.0f if hb_minutes else '?'}分钟，"
```

这是 **Python f-string 格式化语法错误** — 三元表达式不能直接放在 format spec 里。应改为：
```python
f"心跳停止 {hb_minutes:.0f}分钟，" if hb_minutes else f"心跳停止 ?分钟，"
```

**影响**：看门狗在 06:12-06:27 SGT 期间报告"心跳停止 2628-2643 分钟前"，但每次都在执行重启逻辑前崩溃。如果看门狗正常工作，它应该在心跳停止后自动重启 gateway。

### 附因 2：心跳机制长期失效

`heartbeat-state.json` 显示：
```json
{
  "lastCheckISO": "2026-02-10T08:30+08:00"
}
```

心跳最后一次成功更新在 **2 月 10 日 08:30 SGT**，距事件发生已超过 **21 小时**。这意味着心跳机制在更早之前就已经不正常工作了（可能因为主 session 的 lane 也被阻塞，心跳 poll 无法被处理）。

---

## 三、看门狗为何未捕获

1. **检测到了问题** ✅：看门狗正确报告了"心跳停止 2628 分钟"
2. **但执行恢复失败** ❌：Python 语法 bug 导致每次执行到报警逻辑时就崩溃
3. **连续失败至少 6 次**（06:12-06:27 SGT 每 3 分钟一次，均 crash）
4. **根本原因**：看门狗代码的报警路径从未被真正测试过（之前可能恰好没触发心跳超时条件）

---

## 四、改进建议

### P0 - 立即修复

1. **修复看门狗 Python Bug**
   ```python
   # 修复前（有 bug）：
   f"心跳停止 {hb_minutes:.0f if hb_minutes else '?'}分钟，"
   
   # 修复后：
   f"心跳停止 {int(hb_minutes)}分钟，" if hb_minutes else "心跳停止 ?分钟，"
   ```

2. **加看门狗自检测试**：在 watchdog 脚本中加入 try/except 包裹报警逻辑，确保 crash 也能发送通知。

### P1 - 短期改进

3. **Agent Run 超时后的 Lane 清理**：
   - 确认 OpenClaw 在 `embedded run timeout` 后是否正确执行了 `session state: ... new=idle`
   - 如果这是 OpenClaw 核心 bug，需要向上游报告
   - 临时方案：watchdog 在检测到"session 更新超过 N 分钟无变化"时直接重启 gateway

4. **看门狗健壮性**：
   - 用 `try/except` 包裹整个 `main()` 函数
   - 在 catch 中至少发一条错误通知（避免静默失败）
   - 加看门狗版本号，每次修改后记录

### P2 - 长期改进

5. **Lane 健康检查**：
   - 定期检查 lane 队列深度和等待时间
   - 如果某个 lane 的 queueSize > 0 超过 10 分钟无变化，触发告警

6. **Session 超时自动恢复**：
   - 当检测到 session 长时间处于 `processing` 状态（>15 分钟），自动将其标记为 `idle` 并释放 lane

7. **多维度存活检测**：
   - 除了心跳和进程存活，增加 "最后成功回复消息" 时间戳检测
   - 通过 Feishu API 检查是否有未回复的消息

---

## 五、关键日志证据

### 1. Agent Run 超时
```
Feb 11 17:16:56 node[43765]: [agent/embedded] embedded run timeout: 
  runId=ff40afb6-5398-4463-a83b-e5985f728cc5 
  sessionId=126f4a5f-f75f-49e8-a130-6d79682e0d0b 
  timeoutMs=600000
```

### 2. 超时后完全无处理活动（~4.5 小时）
```
# 17:16 ~ 21:53 UTC 之间只有 Config warnings 和 webchat disconnections
# 无任何 Feishu 消息处理、无 agent run、无 lane 活动
```

### 3. Webhook 持续正常接收但无处理
```
Feb 11 21:55:19 [feishu] Received Feishu webhook event: type=im.message.receive_v1
Feb 11 21:55:27 [feishu] Received Feishu webhook event: type=im.message.receive_v1
Feb 11 21:55:36 [feishu] Received Feishu webhook event: type=im.message.receive_v1
Feb 11 21:55:48 [feishu] Received Feishu webhook event: type=im.message.receive_v1
Feb 11 21:55:58 [feishu] Received Feishu webhook event: type=im.message.receive_v1
# → 全部无后续处理日志
```

### 4. 看门狗崩溃（连续多次）
```
[2026-02-12 06:12:01] 最后心跳: 2628.8 分钟前
ValueError: Invalid format specifier '.0f if hb_minutes else '?''

[2026-02-12 06:15:02] 最后心跳: 2631.8 分钟前
ValueError: Invalid format specifier ...（重复）
```

### 5. Gateway 重启恢复
```
Feb 11 22:29:37 systemd[726]: Stopping openclaw-gateway.service...
Feb 11 22:29:37 node[43765]: [gateway] received SIGTERM; shutting down
Feb 11 22:29:42 systemd[726]: Started openclaw-gateway.service (PID 63601)
Feb 11 22:29:46 node[63601]: [gateway] listening on ws://127.0.0.1:18789
# → 重启后立即恢复正常
```

---

## 六、总结

| 项目 | 详情 |
|---|---|
| **根因** | Agent run 超时后 `main` lane 阻塞，所有消息队列堆积无法处理 |
| **持续时间** | ~5 小时 13 分钟 (01:16 → 06:29 SGT) |
| **影响范围** | 所有 Feishu 群聊（不仅是主对话） |
| **为何未自动恢复** | 看门狗因 Python 语法 bug 崩溃，无法执行自动重启 |
| **恢复方式** | Carl 手动重启 gateway |
| **根本修复** | 1) 修看门狗 bug；2) 调查 OpenClaw 超时后 lane 释放逻辑 |
