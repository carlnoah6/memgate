# Luna OS — Task Management System

Luna OS is an async task scheduling architecture that turns Luna from a chatbot into an operating system. The main session stays responsive (< 10s), all heavy work runs as background subagents.

## Architecture

```
Carl 说话 → Luna (main session) 理解意图
  │
  ├── 简单问题 → 直接回复
  │
  └── 需要干活 → task_engine.add() ──→ 自动建群（Lark）
                       │                    │
                       ▼                    ▼
                  task-board.json      🤖 tid-xxx 群聊
                       │                    │
                       ▼                    │
                  sessions_spawn ──────────→│ 子任务发进度到群
                       │                    │
                       ▼                    ▼
                  子任务完成 → complete() → 通知源聊天 + 群聊
```

## Core Design Principles

### 1. 任务 = 逻辑单元，Session = 执行载体

- 每个任务有唯一的 `tid-xxx`，从创建到完成不变
- Session 可以死、可以换，但 tid 不变
- **retry 不改 ID** → 依赖关系天然不会断
- **retry 保留 session_key** → 优先 `sessions_send` 恢复上下文，agent 知道之前做到哪了

### 2. 代码保证，不靠 LLM 记

| 行为 | 保证方式 |
|------|----------|
| 新任务自动建群 | `add()` 内置 Lark API |
| 例行任务跳过建群 | `ROUTINE_TASK_PATTERNS` 自动匹配 |
| 完成后通知源聊天 | `complete()` 调 `_notify_source_chat()` |
| 完成后通知任务群 | `complete()` 调 `_dissolve_task_chat()` |
| cancel 级联取消下游 | `cancel()` 调 `_cascade_cancel()` |
| 去重 | `add()` 调 `find_duplicate()` |
| 环检测 | `add()` 调 `_detect_cycle()` |

### 3. Fail ≠ Cancel

| 操作 | 语义 | 下游处理 |
|------|------|----------|
| **fail** | 执行出错，可能重试 | 不动下游，提示 `waiting_dependents` |
| **cancel** | 用户主动放弃 | 级联取消所有下游 |
| **retry** | 重新尝试 | 恢复到 queued，保留 session |

### 4. 防串台

- 子任务不发结果到源聊天（`complete()` 代码保证）
- 子任务最终回复 `NO_REPLY`（压制 `sessions_spawn` announce）
- 进度只发到任务群（不会污染其他聊天窗口）

## File Structure

### Core Engine
| File | Role |
|------|------|
| `scripts/task_engine.py` | **核心引擎** — 所有任务管理逻辑的单一入口 |
| `scripts/task-manager.py` | **CLI** — 人和脚本调用的命令行接口 |
| `data/task-board.json` | **状态存储** — 所有任务的持久化状态 |

### Scheduling & Monitoring
| File | Role |
|------|------|
| `scripts/heartbeat-scheduler.py` | **调度器** — 判断哪些定时任务到期 |
| `scripts/task-health-check.py` | **健康检查** — 检测卡死任务，自动标记失败 |
| `scripts/task-recovery.py` | **重启恢复** — 系统重启后恢复中断的任务 |
| `scripts/inspect_session.py` | **Session 探针** — 分析 session 实时状态 |

### Communication
| File | Role |
|------|------|
| `scripts/task-chat.py` | **群聊管理** — 创建/解散 Lark 任务群 |
| `scripts/lark-send-message.sh` | **消息发送** — 子任务用这个发进度到群 |
| `data/spawn-task-footer.md` | **Spawn 模板** — 注入到每个子任务的规则 |

### Disabled (code-level)
| File | Status |
|------|--------|
| `scripts/task-board-notify.py` | ⛔ 已禁用（代码清空） |
| `scripts/lark-task-dashboard.py` | ⛔ 已禁用（代码清空） |

## Task Lifecycle

```
queued ──spawn──→ running ──complete──→ done
  ▲                  │                    │
  │                  ├──fail──→ failed    │
  │                  │           │        │
  │                  │         retry      │
  │                  │           │        │
  └──────────────────┘←──────────┘        │
                                          │
  queued ←─────── unblocked ◄─────────────┘
  (下游任务)     (依赖满足)
```

## CLI Reference

```bash
# 创建
task-manager.py add "描述" [chat_id]                    # 创建任务（自动建群）
task-manager.py add "描述" --no-chat                    # 创建任务（不建群）
task-manager.py add "描述" --after tid-001              # 依赖 tid-001
task-manager.py add "描述" --priority high              # 高优先级

# 状态管理
task-manager.py start <id> [session_key]                # 标记运行中
task-manager.py complete <id> "结果"                    # 标记完成（通知源聊天）
task-manager.py fail <id> "错误"                        # 标记失败（不级联）
task-manager.py retry <id>                              # 重试（保留 tid + session）
task-manager.py cancel <id>                             # 取消（级联取消下游）

# 查询
task-manager.py list [status]                           # 列出任务
task-manager.py status                                  # 状态概览 (JSON)
task-manager.py active                                  # 活跃任务 (JSON)
task-manager.py ready                                   # 可调度任务

# 其他
task-manager.py priority <id> <level>                   # 改优先级
task-manager.py check-cycle                             # 检测依赖环
task-manager.py cleanup [days]                          # 清理旧任务
```

## Priority System

| Level | Icon | Value | 用途 |
|-------|------|-------|------|
| critical | 🔴 | 4 | 紧急任务 |
| high | 🟡 | 3 | 重要任务 |
| normal | 🟢 | 2 | 默认（不显示图标） |
| low | 🔵 | 1 | 后台低优先级 |

- 调度时高优先级先 spawn
- 排队超过 ~30 分钟（6 次心跳）自动提升一级
- `MAX_CONCURRENT = 3`（最多同时跑 3 个子任务）

## Routine Task Auto-Detection

`ROUTINE_TASK_PATTERNS` 列表定义例行任务关键词：

```python
["定期检查", "每日日报", "早安提醒", "Wiki 同步", "periodic", ...]
```

匹配的任务自动跳过建群。代码保证，不靠 LLM 传 `--no-chat`。

## Lessons Learned

### 固化 = 写代码，不是写 prompt
HEARTBEAT.md / SOUL.md 是给 LLM 看的提示，LLM 可以无视。要永久改变行为，必须改代码/脚本。
> 教训：Carl 要求停止任务板推送，Luna 只在文档标删除线，LLM 无视，Carl 说了三遍。最终替换脚本为空壳才解决。

### 改复杂系统前先验证假设
不要连写 3 个 patch 才发现第一个假设就是错的。先加 debug log 确认数据流。

### 能跑的方案不要动
第一个方案验证可用后先交付，优化是后续的事。

### 防串台三原则
1. `complete()` 是唯一的结果通知路径（代码保证）
2. 子任务不自己发结果（防重复）
3. 最终回复 `NO_REPLY`（压制 announce 串台）
