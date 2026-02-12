# Code Review: 任务管理系统

**Date**: 2026-02-12  
**Reviewer**: Luna (subagent t025)  
**Scope**: 11 scripts, 3873 total lines  
**Severity levels**: 🔴 Critical / 🟡 Important / 🟢 Suggestion

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     调用方 (主 session / 心跳 / 子任务)         │
└──────┬──────────┬──────────┬───────────┬───────────┬────────┘
       │          │          │           │           │
  task-manager.py │   spawn-task.py  planner.py  子任务 prompt
  (CLI 直接操作)  │   (统一入口)   (编排层)    (task-manager complete)
       │          │          │           │           │
       │    task_engine.py   │     task-manager.py   │
       │    (Python API)     │     (subprocess)      │
       │          │          │           │           │
       └──────────┴──────────┴───────────┴───────────┘
                            │
                    data/task-board.json
                            │
       ┌────────────────────┼────────────────────────┐
       │                    │                        │
 task-health-check.py  task-board-notify.py   task-dashboard.py
 (心跳健康检查)         (Lark 推送)            (控制台看板)

 辅助:
   task-chat.py          — Lark 群聊 CRUD
   cleanup-task-chats.py — 批量清理过期群聊
   task-recovery.py      — 重启后恢复中断任务
   archive-backlog.py    — backlog.md 归档
```

---

## 2. task-manager.py vs task_engine.py 的边界和重叠

### 现状

| 维度 | task-manager.py (348行) | task_engine.py (938行) |
|------|------------------------|----------------------|
| 定位 | 最早的 CLI 工具 | 后来的统一引擎 |
| ID 格式 | `t{N:03d}` (递增，`next_id`) | `tid-{MMDD}-{N}` (每日计数) |
| 默认数据 | `{"tasks":[], "next_id":1}` | `{"tasks":[], "daily_date":"", "daily_seq":0}` |
| Lark 群聊 | 无 | 内建 `_create_task_chat()` |
| 优先级 | 无 | 有（critical/high/normal/low + aging） |
| 去重/环检测 | 无 | 有 |
| 并发限制 | 无 | `MAX_CONCURRENT=3` |
| SysMonitor | 无 | 有 `_enrich_task()` |
| 谁在用它 | **planner.py** (subprocess), **SOUL.md**, **AGENTS.md**, **spawn-task-footer.md**, 子任务 prompt | **spawn-task.py**, **task-dashboard.py**, **task-recovery.py**, **lark-task-card.py** |

### 🔴 Critical: 双写冲突

**task-manager.py 和 task_engine.py 各自有独立的 `load_board()` / `save_board()`**，都直接读写同一个 `task-board.json`。没有文件锁。

- task-manager.py 生成 `t{N}` ID，用 `next_id` 字段
- task_engine.py 生成 `tid-MMDD-N` ID，用 `daily_date` + `daily_seq` 字段
- 当前 task-board.json 中有 `next_id: 27`，说明实际在用 task-manager.py 的路径

当两个进程几乎同时读-改-写时，后写者会覆盖前写者的改动。

### 🔴 Critical: planner.py 调用 task-manager.py，绕过 task_engine

planner.py 通过 `subprocess.run(["python3", task-manager.py, ...])` 调用任务管理，意味着：
- 不走 task_engine 的去重检查
- 不走环检测
- 不走并发限制
- 不创建任务群聊
- ID 格式不一致（`t{N}` vs `tid-MMDD-N`）

而 planner.py 传了 `--no-chat` 给 task-manager.py，但 **task-manager.py 不支持 `--no-chat` 参数**！它的 `add` 命令只识别 `--after` flag。这意味着 `--no-chat` 会被当成 `source_chat_id`，产生错误数据。

### 🟡 建议

1. **废弃 task-manager.py 的 Python 逻辑，保留为 task_engine 的 CLI 薄壳**：
   ```python
   # task-manager.py → 改为调用 TaskEngine
   from task_engine import TaskEngine
   engine = TaskEngine()
   if cmd == "add": engine.add(desc, source_chat)
   if cmd == "complete": engine.complete(task_id, result)
   # ...
   ```
2. **planner.py 直接 import TaskEngine** 而非 subprocess 调用
3. 统一 ID 格式，迁移 `next_id` → `daily_date/daily_seq`

---

## 3. planner.py 是否应该拆分

### 现状分析 (1067行)

| 模块 | 行数估算 | 职责 |
|------|---------|------|
| 常量+helpers | ~80 | SGT, paths, now_iso, chat_id_short |
| IO (load/save/find) | ~50 | planner JSON 读写 |
| task-manager 集成 | ~80 | tm_add/complete/fail/cancel/start (subprocess) |
| Lark 消息 | ~15 | send_lark |
| Cron/调度 | ~40 | schedule_advance |
| 显示/格式化 | ~70 | format_plan, _format_time |
| Prompt 构建 | ~25 | build_spawn_prompt |
| 子命令实现 | ~500 | cmd_init/show/step_done/step_fail/replan/cancel/advance/check_advances/list/find_by_task |
| main CLI | ~60 | argv 解析 |

### 🟢 结论：不需要拆分

planner.py 虽然 1067 行，但结构清晰：
- 每个 `cmd_*` 函数职责单一，有完整 docstring
- 没有循环依赖
- 一个文件便于理解完整的 plan lifecycle

但可以做的优化：
1. **提取 tm_* 函数为直接 Python 调用**（去掉 subprocess wrapper），减 ~80 行
2. **提取 `PlannerStore` 类** 封装 load/save/find，使测试更容易

---

## 4. 哪些脚本已过时可删除

### 🔴 task-health-check.py — 可删除（已被 task_engine.py 取代）

| 证据 | |
|------|---|
| task_engine.py 第 742 行 | `# ─── Health Check (原 task-health-check) ──────────────` |
| 功能完全重复 | load_board, 超时检测, 自动清理, dissolve 群聊 |
| 更弱 | 没有 SysMonitor 集成、没有 priority aging |
| 超时阈值不同 | 35min vs task_engine 的 60min（不一致是 bug 来源） |
| 仍然会解散群聊 | 遍历所有 done/failed 任务调用 dissolve（与 task_engine 的「不解散」策略矛盾） |

**risk**: task-health-check.py 还在 HEARTBEAT.md 引用吗？检查后安全删除。

### 🟡 task-chat.py — 可能过时

task_engine.py 的 `_create_task_chat()` 和 `dissolve_chat()` 已经内建了群聊创建和解散逻辑。但 spawn-task.py 的 `create_task_chat()` 仍然 subprocess 调用 task-chat.py。

- **如果 spawn-task.py 改为直接用 engine._create_task_chat()**，则 task-chat.py 可删除
- 但 task-chat.py 的 `dissolve-task` 命令被其他地方引用，需要确认

### 🟡 task-board-notify.py — 可能过时

已有 `lark-task-dashboard.py` 和 `lark-card-builder.py` 做更丰富的 Lark 卡片推送。task-board-notify.py 只发纯文本。如果两者都在运行，会重复通知。

检查是否有 cron/heartbeat 引用 task-board-notify.py，如果没有则可删除。

### 🟢 archive-backlog.py — 保留但需修复

独立功能（归档 backlog.md 的 `[x]` 项），与任务管理系统无直接依赖。保留。

### 保留列表

| 脚本 | 状态 | 理由 |
|------|------|------|
| task_engine.py | ✅ 核心 | 统一引擎 |
| task-manager.py | ⚠️ 需重构 | 改为 task_engine CLI 薄壳 |
| planner.py | ✅ 保留 | 编排层，结构清晰 |
| spawn-task.py | ✅ 保留 | 统一 spawn 入口 |
| task-recovery.py | ✅ 保留 | 重启恢复，已用 task_engine |
| task-dashboard.py | ✅ 保留 | 控制台看板，已用 task_engine |
| task-chat.py | ⚠️ 待合并 | 功能已在 task_engine 中 |
| cleanup-task-chats.py | ✅ 保留 | 独立批量清理，有独特逻辑 |
| task-health-check.py | ❌ 删除 | 完全被 task_engine.health_check() 取代 |
| task-board-notify.py | ⚠️ 待确认 | 可能已被 lark-task-dashboard.py 取代 |
| archive-backlog.py | ✅ 保留 | 独立功能 |

---

## 5. 错误处理和边界情况

### 🔴 task_engine.py: 双重 raise（第 622-623 行）

```python
def fail(self, task_id: str, error: str = "") -> dict:
    ...
        raise ValueError(f"Task {task_id} not found")
        raise ValueError(f"Task {task_id} not found")  # ← 死代码！
```

第 623 行是复制粘贴错误，永远不会执行。

### 🔴 planner.py: `--no-chat` 传给不支持的脚本

```python
# planner.py line 137
cmd = ["python3", str(TASK_MANAGER), "add", description, "--no-chat"]
```

task-manager.py 的 `add` 命令只识别 `--after` 参数。`--no-chat` 会被当作位置参数：
- 如果没有 source_chat：`--no-chat` 成为 `source_chat`
- 如果有 source_chat：`--no-chat` 被 `filtered.append()` 收集，可能导致错误

### 🟡 task-health-check.py: fromisoformat 无 try/except

```python
# line 74 (cleanup 部分)
or datetime.fromisoformat(t["completed"]) > cutoff
```

如果 `completed` 字段格式异常（如带 Z 后缀），会抛 ValueError 导致整个清理失败。task_engine.py 有 `parse_datetime()` 正确处理了这个问题。

### 🟡 task-manager.py: 无任何输入校验

- `add_task("")` 允许空描述
- `start_task("nonexistent")` 返回 `sys.exit(1)` 但不是 JSON 格式
- `cleanup(-1)` 允许负数天数（会清理所有任务）

### 🟡 task_engine.py: send_notification 吞掉所有异常

```python
@staticmethod
def send_notification(chat_id: str, message: str):
    ...
    except Exception:
        pass  # 完全静默
```

建议至少 `print(..., file=sys.stderr)` 记录失败，否则消息丢失无法排查。

### 🟡 cleanup-task-chats.py: API secret 硬编码

```python
APP_SECRET = "***LARK_SECRET_REMOVED***"
```

task-chat.py、task-board-notify.py、task_engine.py 都各自硬编码了相同的 APP_ID 和 APP_SECRET。至少 4 处重复。应提取到一个共享常量文件或环境变量。

### 🟢 archive-backlog.py: 潜在数据丢失

`main()` 中使用索引遍历 `lines` 但有一个未使用的 `iterator = iter(lines)`（第 31 行）。更重要的是，如果 `## 已完成` header 存在于 TODO section 内部，逻辑会有问题——它会触发 `in_todo_section = False` 但归档内容插入位置可能不对。

---

## 6. 数据一致性（task-board.json 的读写安全）

### 🔴 无文件锁 — 竞态条件

当前 **6 个脚本** 独立读写 task-board.json：

1. task-manager.py (`load_board` / `save_board`)
2. task_engine.py (`load_board` / `save_board`)
3. task-health-check.py (`load_board` / `save_board`)
4. task-chat.py (`json.load` / `json.dump` — 直接操作)
5. cleanup-task-chats.py (`update_task_board`)
6. task-board-notify.py (`load_board` — 只读)
7. spawn-task.py (`update_task_board` — 直接操作)

典型竞态场景：
```
T1: task-manager.py complete t005  →  load()  →  修改  →  save()
T2: task-health-check.py           →  load()  →  修改  →  save()  ← 覆盖 T1 的改动!
```

### 🟡 建议方案

**短期**：使用 `fcntl.flock()` 文件锁：

```python
import fcntl

def load_board_locked():
    fd = open(TASK_BOARD, "r+")
    fcntl.flock(fd, fcntl.LOCK_EX)  # 排他锁
    board = json.load(fd)
    return board, fd  # 持有锁直到 save

def save_board_locked(board, fd):
    fd.seek(0)
    fd.truncate()
    json.dump(board, fd, indent=2, ensure_ascii=False)
    fd.flush()
    fcntl.flock(fd, fcntl.LOCK_UN)
    fd.close()
```

**长期**：所有读写集中到 TaskEngine，其他脚本不直接操作 JSON 文件。

### 🟡 ID 格式不兼容

当前 task-board.json 中有两种 ID 格式：
- `t002`, `t003` ... `t026` — 来自 task-manager.py
- `tid-0212-1` — 来自 task_engine.py（如果被使用）

两种格式的任务共存于同一个 board，但 `next_id` 和 `daily_date/daily_seq` 互不感知。如果同时走两条路径，ID 可能冲突。

### 🟡 默认值不一致

| 字段 | task-manager.py | task_engine.py |
|------|----------------|---------------|
| `depends_on` | `[]` | `[]` |
| `priority` | 不存在 | `"normal"` |
| `priority_value` | 不存在 | `2` |
| `task_chat_id` | 不存在 | 可能存在 |

task_engine.py 的 `load_board()` 会用 `setdefault()` 补全老任务的字段，但 task-manager.py 创建的任务没有 priority 字段，在 task_engine 以外的脚本中可能引发 KeyError。

---

## 7. 具体 Bug 列表

| # | 严重性 | 文件 | 行号 | 问题 |
|---|--------|------|------|------|
| 1 | 🔴 | task_engine.py | 622-623 | 双重 `raise ValueError`（复制粘贴错误，死代码） |
| 2 | 🔴 | planner.py | 137-139 | 传 `--no-chat` 给 task-manager.py，但后者不支持此参数 |
| 3 | 🔴 | task-health-check.py | 56-70 | 遍历所有 done/failed 任务执行 dissolve，与 task_engine「不自动解散」策略矛盾 |
| 4 | 🟡 | task-health-check.py | 74 | `fromisoformat` 无 try/except，Z 后缀日期会崩溃 |
| 5 | 🟡 | task_engine.py | 全局 | `send_notification` 静默吞异常，消息丢失无法排查 |
| 6 | 🟡 | 多个文件 | — | APP_ID/APP_SECRET 硬编码在 4+ 个文件中 |
| 7 | 🟡 | spawn-task.py | 269-279 | 在 `engine.add()` 已建群后，又尝试用 `task-chat.py` 建群（双重建群） |
| 8 | 🟢 | archive-backlog.py | 31 | 未使用的 `iterator = iter(lines)` |
| 9 | 🟢 | task-manager.py | 50-51 | `next_id` 可能与 task_engine 的 daily_seq 产生 ID 冲突 |

### Bug #7 详解：spawn-task.py 的双重建群

```python
# spawn-task.py cmd_create():
task = engine.add(description, source_chat)  # engine.add() 内部已调用 _create_task_chat()
# ...
if not parsed.no_chat:
    task_chat_id = create_task_chat(task_id, description)  # 又用 task-chat.py 建群!
```

`engine.add()` 默认 `create_chat=True`，会调用 `_create_task_chat()`。然后 spawn-task.py 又通过 subprocess 调 `task-chat.py create` 再建一个群。结果：**同一个任务会有两个群聊**。

修复：spawn-task.py 应该传 `create_chat=False` 给 `engine.add()`，或者删掉后面的手动建群逻辑。

---

## 8. 重构路线图

### Phase 1: 修 Bug（立即可做）
- [ ] 删除 task_engine.py 第 623 行的重复 raise
- [ ] 修复 spawn-task.py 的双重建群（传 `create_chat=False`）
- [ ] planner.py 改为直接 import TaskEngine，不 subprocess 调 task-manager.py

### Phase 2: 收敛入口（1-2天）
- [ ] task-manager.py 改为 TaskEngine 的 CLI 薄壳
- [ ] 统一 ID 格式为 `tid-MMDD-N`
- [ ] 删除 task-health-check.py（被 task_engine.health_check() 取代）
- [ ] 提取 Lark API credentials 到 `scripts/lark_config.py`

### Phase 3: 数据安全（可选）
- [ ] 为 task-board.json 添加文件锁 (`fcntl.flock`)
- [ ] 合并 task-chat.py 到 task_engine.py
- [ ] 确认并删除 task-board-notify.py（如已被 lark-task-dashboard.py 取代）

---

## 9. 优先级建议

如果只做三件事：

1. **🔴 让 planner.py 直接用 TaskEngine**（消除最大的架构分裂）
2. **🔴 修复 spawn-task.py 双重建群**（当前每个任务浪费一个 Lark 群聊）
3. **🔴 删除 task-health-check.py**（与 task_engine 策略矛盾，会误解散群聊）

---

*Review complete. 3873 lines across 11 files, found 9 issues (3 critical, 4 important, 2 suggestions).*
