# Luna OS — Task Management System

Luna OS is an async task orchestration layer built on top of OpenClaw. It turns Luna from a chatbot into an operating system: the main session stays responsive for conversation while all heavy work runs in background subagents.

## Architecture Overview

```
Carl (Lark chat)
  ↓
Main Session (dispatcher, <10s response time)
  ↓
┌─────────────────────────────────────────────┐
│              Task Engine                     │
│  task_engine.py — single source of truth     │
│                                              │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Board   │  │ Priority │  │ Dependency  │  │
│  │ State   │  │ Queue    │  │ Graph (DAG) │  │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘  │
│       └────────────┴──────────────┘          │
└──────────────────┬──────────────────────────┘
                   ↓
    ┌──────────────┼──────────────┐
    ↓              ↓              ↓
 Subagent 1    Subagent 2    Subagent 3
 (session)     (session)     (session)
    ↓              ↓              ↓
 Task Group    Task Group    (no group
  Chat          Chat          for routine)
```

## Core Modules

### task_engine.py (885 lines) — The Brain

Unified engine that manages all task state. Every other script imports from here.

**Key concepts:**
- **Task** = logical unit of work, identified by `tid-MMDD-N` (e.g. `tid-0211-3` = Feb 11, task 3)
- **Session** = execution carrier (OpenClaw subagent), can change on retry
- **Board** = `data/task-board.json`, persistent state for all tasks

**Task ID format:** `tid-MMDD-N`
- `MMDD` = month+day of creation (e.g. `0211` = Feb 11)
- `N` = daily sequence number, no zero-padding (1, 2, ... 42, not 001)
- Resets to 1 each day
- Examples: `tid-0211-1`, `tid-0315-42`, `tid-1225-7`
- Why: readable at a glance ("Feb 11, task 3"), short enough for chat ("kill tid-0211-3"), no growing numbers

**State machine:**
```
queued → running → done
                 → failed → (retry) → queued
                          → (cascade) stays failed, dependents wait
       → cancelled (cascade cancels all downstream dependents)
```

**Features:**
| Feature | Method | Description |
|---------|--------|-------------|
| Add | `add()` | Create task, auto-create group chat, dedup check, cycle detection |
| Start | `start()` | Mark running, enforce `MAX_CONCURRENT=3` |
| Complete | `complete()` | Mark done, notify source chat, notify task group, unblock dependents |
| Fail | `fail()` | Mark failed, notify, report `waiting_dependents` (no cascade) |
| Cancel | `cancel()` | Mark cancelled, **cascade cancel** all downstream dependents |
| Retry | `retry()` | Reset to queued, **preserve session_key** for context resumption |
| Priority | `set_priority()` | critical > high > normal > low, with aging boost |
| Health | `health_check()` | Detect stalled/dead sessions, auto-fail, priority aging |

**Design decisions:**

1. **Auto group chat on add** — Every non-routine task automatically gets a Lark group chat. Carl sees progress without asking. Routine tasks (periodic checks, daily reports) are auto-detected via `ROUTINE_TASK_PATTERNS` and skip chat creation.

2. **Retry preserves session** — When retrying a failed task, `session_key` is kept. The dispatcher tries `sessions_send` first (agent resumes with full context), only falls back to `sessions_spawn` if the session is dead. This avoids wasting work already done.

3. **Cancel cascades, fail doesn't** — If Carl explicitly cancels a task, downstream dependents are cancelled too (intentional abandonment). But failure doesn't cascade because the task might be retried — dependents just wait.

4. **Dedup and cycle detection** — `add()` rejects duplicate descriptions (same running/queued task) and detects dependency cycles via DFS before creating the task.

5. **Code guarantees over prompt instructions** — Notifications, chat creation, cascade logic are all in code. Never rely on LLM "remembering" to do something.

### task-manager.py (265 lines) — CLI Interface

```bash
# Task lifecycle
task-manager.py add "description" [chat_id] [--after tid-001] [--priority high] [--no-chat]
task-manager.py start <id> [session_key]
task-manager.py complete <id> "result summary"
task-manager.py fail <id> "error message"
task-manager.py retry <id>                    # Reset to queued, preserve session
task-manager.py cancel <id>                   # Cascade cancel dependents
task-manager.py priority <id> <level>         # critical/high/normal/low

# Queries
task-manager.py list [status]                 # Human-readable task list
task-manager.py status                        # JSON summary
task-manager.py active                        # Running + queued with SysMonitor data
task-manager.py ready                         # Tasks ready to spawn (deps met)

# Maintenance
task-manager.py cleanup [days]                # Remove old completed tasks
task-manager.py check-cycle                   # Detect dependency cycles
task-manager.py graph [output_path]           # Render dependency graph (Graphviz)
```

### heartbeat-scheduler.py (95 lines) — The Clock

Runs every heartbeat (~5 min). Outputs which tasks are due as JSON.

**Task types:**
| Key | Interval | Night skip | Description |
|-----|----------|------------|-------------|
| `periodic` | 5 min | Yes (23-07) | Email + calendar + TODO + doc comments |
| `research` | 5 min | No | Pick next item from `data/backlog.md` |
| `wikiSync` | 30 min | No | Sync changed files to Lark Wiki |
| `dailyReport` | Daily 04:00 | — | Generate yesterday's report |
| `morningGreeting` | Daily 07:00 | — | Today's schedule reminder |
| `weeklyReview` | Sunday 10:00 | — | Next week planning |

### task-chat.py (187 lines) — Group Chat Management

Creates/dissolves Lark group chats for tasks.

```bash
task-chat.py create <task_id> "task name"     # Create group, add Carl, send welcome
task-chat.py dissolve <chat_id>               # Delete group
task-chat.py dissolve-task <task_id>          # Find and dissolve by task ID
```

**Note:** Chat creation is now integrated into `task_engine.add()` — you don't need to call this directly. The engine calls Lark API inline (not via subprocess) to avoid timeout issues.

### spawn-task.py (434 lines) — Spawn Helper

Unified entry point for spawning subagents. Handles:
- Reading task prompt from `data/` files
- Injecting `spawn-task-footer.md` template
- Creating task board entry
- Starting the session

### task-health-check.py (31 lines) — Watchdog

Thin wrapper around `TaskEngine.health_check()`. Called every heartbeat.

**What it detects:**
- Session dead (transcript file missing, inspect fails)
- Session stalled (no activity > 10 min)
- Session timeout (running > 60 min)

**What it does:**
- Auto-marks dead tasks as failed
- Sends failure notification to task group chat
- Priority aging: queued tasks waiting > 30 min get priority boost

### task-recovery.py (123 lines) — Restart Recovery

Runs after gateway restart. Scans running tasks and attempts recovery:
1. **Session alive** → `sessions_send` with resume message
2. **Session dead, transcript exists** → Report as lost (manual retry needed)
3. **No session key** → Report as unrecoverable

### inspect_session.py (148 lines) — Session Inspector

Analyzes OpenClaw session files to determine status:
- Last activity time and age
- Total tokens consumed
- Last tool call / action
- Status classification (Running / Stalled / Dead)

### watchdog-log.py (71 lines) — Deadlock Detector

Checks gateway logs for "stuck processing" state (log silent > 3 min while marked as processing). Auto-triggers restart if detected.

### lark-send-message.sh (143 lines) — Message Sender

Sends messages to Lark chats. Used by subagents for progress updates.

```bash
lark-send-message.sh <chat_id> "message"           # Plain text
echo "content" | lark-send-message.sh <chat_id> -   # From stdin
cat report.md | lark-send-message.sh <chat_id> --post  # Markdown → rich text
```

### restart-gateway.sh (50 lines) — Safe Restart

Unified restart script that handles the full restart sequence:
1. Write restart marker (for post-restart detection)
2. Create cron wake job (triggers heartbeat 15s after restart)
3. Wait 5s (let streaming cards close)
4. Execute `openclaw gateway restart`

## Data Files

| File | Purpose |
|------|---------|
| `data/task-board.json` | All task state (the single source of truth) |
| `data/heartbeat-state.json` | Last check timestamps for scheduler |
| `data/spawn-task-footer.md` | Template injected into every subagent prompt |
| `data/periodic-check-prompt.md` | Prompt for periodic check subagents |
| `data/backlog.md` | Research task queue |

## Anti-Patterns & Lessons Learned

### ❌ Disable features by editing documentation
**Wrong:** Mark something as "disabled" in HEARTBEAT.md with strikethrough.
**Right:** Replace the script code with `sys.exit(0)`.
**Why:** HEARTBEAT.md is a prompt for the LLM, not executable code. The LLM can ignore it.

### ❌ Rely on LLM to remember steps
**Wrong:** Tell the LLM to "remember to create a group chat when spawning tasks."
**Right:** Put chat creation inside `task_engine.add()` so it happens automatically.
**Why:** LLMs forget. Code doesn't.

### ❌ Send results from multiple paths
**Wrong:** Subagent sends result via script AND `complete()` also sends AND `sessions_spawn` announce delivers.
**Right:** `complete()` is the single notification path. Subagent ends with `NO_REPLY`.
**Why:** Multiple paths = duplicate messages + cross-posting to wrong chats.

### ❌ Create new task ID on retry
**Wrong:** Retry a failed task by creating a new `tid-XXX`.
**Right:** Reset the same task to queued, preserve session for context.
**Why:** New ID breaks dependency chains. Old session has valuable context.

### ❌ Cascade cancel on failure
**Wrong:** When task A fails, auto-cancel all tasks depending on A.
**Right:** Report `waiting_dependents` but don't cancel. Task A might be retried.
**Why:** Failure is often temporary (restart, timeout). Cancel is permanent intent.

## Priority System

Four levels with automatic aging:

| Level | Icon | Value | Use case |
|-------|------|-------|----------|
| critical | 🔴 | 4 | Drop everything |
| high | 🟡 | 3 | Do soon |
| normal | 🟢 | 2 | Default (icon hidden to reduce noise) |
| low | 🔵 | 1 | When free |

**Aging:** Tasks queued > 30 min (6 heartbeats) auto-boost by one level (max → high). Prevents starvation.

**Scheduling order:** Higher priority first, then FIFO within same level.

## Concurrency

- `MAX_CONCURRENT = 3` subagents running simultaneously
- Excess tasks queue and wait for a slot
- Priority determines who gets the next slot
