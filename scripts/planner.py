#!/usr/bin/env python3
"""Luna OS — Planner (Orchestration Layer)

Sits on top of the task board (task-manager.py) and provides ordered
multi-step execution with automatic advancement.

Each group chat can have one active planner.  Steps map 1-to-1 to
task-board tasks (tid-xxx).

Usage:
  planner.py init <chat_id> <goal> <steps_json>          — Create a new plan
  planner.py show <chat_id>                               — Display plan status
  planner.py step-done <chat_id> <step_id> "<result>"     — Mark step done & advance
  planner.py step-fail <chat_id> <step_id> "<error>"      — Mark step failed
  planner.py replan <chat_id> <new_steps_json>            — Replace pending steps
  planner.py cancel <chat_id>                             — Cancel entire plan
  planner.py advance <chat_id>                            — Check & advance (heartbeat)
  planner.py check-advances                               — Check all active planners
  planner.py list                                         — List active planners
  planner.py find-by-task <task_id>                       — Find plan by task ID

Steps JSON format (both init and replan):
  [{"title": "...", "prompt": "..."}]   — preferred
  [{"desc": "...", "detail": "..."}]    — also supported (internal keys)

Flags:
  --dry-run    Skip Lark messaging and task-manager calls
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# === Constants ===
SGT = timezone(timedelta(hours=8))
BASE = Path("/home/ubuntu/.openclaw/workspace")
DATA_DIR = BASE / "data" / "planner"
TASK_MANAGER = BASE / "scripts" / "task-manager.py"
LARK_SEND = BASE / "scripts" / "lark-send-message.sh"

# Global dry-run flag (set from argv)
DRY_RUN = False

GET_SOURCE_CHAT = BASE / "scripts" / "get-source-chat.py"


def resolve_chat_id(chat_id_or_msgid: str) -> str:
    """Resolve a chat_id from either a direct chat_id or a Lark message_id.

    If the input starts with 'om_', treat it as a message_id and resolve
    the chat_id via get-source-chat.py.
    Otherwise, return it as-is (assumed to be a chat_id).
    """
    if chat_id_or_msgid.startswith("om_"):
        try:
            result = subprocess.run(
                ["python3", str(GET_SOURCE_CHAT), chat_id_or_msgid],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip().startswith("oc_"):
                resolved = result.stdout.strip()
                print(f"[planner] resolved message {chat_id_or_msgid} → chat {resolved}", file=sys.stderr)
                return resolved
        except Exception as e:
            print(f"[planner] resolve_chat_id error: {e}", file=sys.stderr)
        raise ValueError(f"Cannot resolve chat_id from message_id: {chat_id_or_msgid}")
    return chat_id_or_msgid


# === Helpers ===

def now_iso() -> str:
    """Return current time in SGT as ISO 8601 string."""
    return datetime.now(SGT).isoformat()


def chat_id_short(chat_id: str) -> str:
    """Derive a short, filesystem-safe identifier from chat_id.

    Uses the last 8 characters.  For typical Lark chat IDs like
    ``oc_0900e63860f8b6d1b08285262701817f`` this is unique enough.
    """
    return chat_id[-8:]


def planner_path(chat_id: str) -> Path:
    """Return the JSON file path for a planner by chat_id."""
    return DATA_DIR / f"{chat_id_short(chat_id)}.json"


def load_planner(chat_id: str) -> dict | None:
    """Load a planner from disk by chat_id.  Returns None if not found or corrupt."""
    p = planner_path(chat_id)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return None


def save_planner(plan: dict):
    """Save a planner to disk.  Auto-creates data directory."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    plan["updated_at"] = now_iso()
    with open(planner_path(plan["chat_id"]), "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)


def find_planner_by_chat(chat_id: str) -> dict | None:
    """Find planner by full or partial chat_id.

    Tries direct path first (fast), then scans all planners as fallback.
    """
    # Try direct path first
    plan = load_planner(chat_id)
    if plan:
        return plan
    # Fallback: scan all planners for matching chat_id
    if DATA_DIR.exists():
        for fp in DATA_DIR.glob("*.json"):
            try:
                with open(fp) as f:
                    p = json.load(f)
                if p.get("chat_id") == chat_id:
                    return p
            except Exception:
                continue
    return None


def normalize_step(raw: dict, step_id: int) -> dict:
    """Normalize a raw step dict into internal format.

    Supports both external keys (title/prompt) and internal keys (desc/detail).
    Priority: title > desc > "Step N" for description.
    Priority: prompt > detail > "" for detail.
    Risk: "high" | "medium" | "low" (default: "low").
      - high: step-done pauses for user confirmation before advancing
      - low/medium: auto-advance to next step
    """
    desc = raw.get("title") or raw.get("desc") or f"Step {step_id}"
    detail = raw.get("prompt") or raw.get("detail") or ""
    risk = raw.get("risk", "low")
    if risk not in ("low", "medium", "high"):
        risk = "low"
    step = {
        "id": step_id,
        "desc": desc,
        "detail": detail,
        "status": "pending",
    }
    if risk == "high":
        step["risk"] = "high"
    return step


# === Task Manager Integration ===

def tm_add(description: str, source_chat: str = None) -> str | None:
    """Call task-manager.py add, return task_id or None."""
    if DRY_RUN:
        import random
        tid = f"tid-dry-{random.randint(100, 999)}"
        print(f"[dry-run] task-manager add: {description!r} → {tid}", file=sys.stderr)
        return tid
    cmd = ["python3", str(TASK_MANAGER), "add", description, "--no-chat"]
    if source_chat:
        cmd.insert(4, source_chat)  # add <desc> <chat_id> --no-chat
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            print(f"[planner] task-manager add failed: {result.stderr.strip()}", file=sys.stderr)
            return None
        data = json.loads(result.stdout.strip())
        return data.get("id")
    except Exception as e:
        print(f"[planner] task-manager add error: {e}", file=sys.stderr)
        return None


def tm_complete(task_id: str, result: str = ""):
    """Call task-manager.py complete."""
    if DRY_RUN:
        print(f"[dry-run] task-manager complete: {task_id} {result!r}", file=sys.stderr)
        return
    try:
        subprocess.run(
            ["python3", str(TASK_MANAGER), "complete", task_id, result],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        print(f"[planner] task-manager complete error: {e}", file=sys.stderr)


def tm_fail(task_id: str, error: str = ""):
    """Call task-manager.py fail."""
    if DRY_RUN:
        print(f"[dry-run] task-manager fail: {task_id} {error!r}", file=sys.stderr)
        return
    try:
        subprocess.run(
            ["python3", str(TASK_MANAGER), "fail", task_id, error],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        print(f"[planner] task-manager fail error: {e}", file=sys.stderr)


def tm_cancel(task_id: str):
    """Call task-manager.py cancel."""
    if DRY_RUN:
        print(f"[dry-run] task-manager cancel: {task_id}", file=sys.stderr)
        return
    try:
        subprocess.run(
            ["python3", str(TASK_MANAGER), "cancel", task_id],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        print(f"[planner] task-manager cancel error: {e}", file=sys.stderr)


def tm_start(task_id: str, session_key: str = ""):
    """Call task-manager.py start."""
    if DRY_RUN:
        print(f"[dry-run] task-manager start: {task_id} {session_key!r}", file=sys.stderr)
        return
    try:
        subprocess.run(
            ["python3", str(TASK_MANAGER), "start", task_id, session_key],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        print(f"[planner] task-manager start error: {e}", file=sys.stderr)


# === Lark Messaging ===

def send_lark(chat_id: str, message: str):
    """Send a text message to a Lark chat."""
    if DRY_RUN:
        print(f"[dry-run] lark-send: {chat_id} → {message[:80]}...", file=sys.stderr)
        return
    try:
        subprocess.run(
            ["bash", str(LARK_SEND), chat_id, message],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        print(f"[planner] lark-send error: {e}", file=sys.stderr)


# === Cron Wake (best-effort) ===

def _spawn_via_cron(step: dict, prompt: str) -> bool:
    """Spawn the next planner step via openclaw cron (code-guaranteed execution).

    Creates an isolated agentTurn cron job that fires in ~30 seconds.
    The cron scheduler executes it — no LLM involvement, no heartbeat dependency.

    Falls back to writing a pending file if cron add fails.

    Returns True if spawn was successfully scheduled.
    """
    task_id = step.get("task_id", f"step-{step['id']}")

    if DRY_RUN:
        print(f"[dry-run] spawn via cron: {task_id}", file=sys.stderr)
        return True

    # Primary: use openclaw cron add to create an isolated agentTurn
    try:
        at_time = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cmd = [
            "openclaw", "cron", "add",
            "--name", f"planner-spawn-{task_id}",
            "--at", at_time,
            "--session", "isolated",
            "--message", prompt,
            "--timeout-seconds", "900",
            "--delete-after-run",
            "--no-deliver",
            "--wake", "now",
            "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                job = json.loads(result.stdout.strip().split('\n')[-1])
                job_id = job.get("id", "unknown")
                print(f"[planner] spawned {task_id} via cron job {job_id} (fires at {at_time})", file=sys.stderr)
                return True
            except json.JSONDecodeError:
                # Command succeeded but output wasn't clean JSON — still OK
                print(f"[planner] spawned {task_id} via cron (non-JSON output, rc=0)", file=sys.stderr)
                return True
        else:
            print(f"[planner] cron add failed (rc={result.returncode}): {result.stderr.strip()}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"[planner] cron add timed out for {task_id}", file=sys.stderr)
    except Exception as e:
        print(f"[planner] cron add error for {task_id}: {e}", file=sys.stderr)

    # Fallback: write pending file for heartbeat pickup
    print(f"[planner] falling back to pending file for {task_id}", file=sys.stderr)
    pending_dir = BASE / "data" / "planner-pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    spawn_file = pending_dir / f"{task_id}.json"
    try:
        with open(spawn_file, "w") as f:
            json.dump({
                "task_id": task_id,
                "prompt": prompt,
                "created_at": now_iso(),
                "type": "spawn",
            }, f, ensure_ascii=False)
        print(f"[planner] wrote fallback spawn request for {task_id}", file=sys.stderr)
        return False  # Return False to indicate fallback (not code-guaranteed)
    except Exception as e:
        print(f"[planner] fallback spawn file write error: {e}", file=sys.stderr)
    return False


def _spawn_completion_summary(plan: dict):
    """Spawn an isolated task to aggregate plan results and propose next steps.

    Triggered automatically when all steps complete. The summary task:
    1. Reads all step results
    2. Generates an aggregated summary
    3. Proposes concrete next steps / follow-up plan
    4. Sends the summary to the plan's chat
    """
    chat_id = plan["chat_id"]
    goal = plan["goal"]

    # Build step results for the summary prompt
    step_summaries = []
    for s in plan["steps"]:
        step_summaries.append(f"Step {s['id']}: {s['desc']}\n  Result: {s.get('result', 'N/A')}")

    steps_text = "\n".join(step_summaries)

    prompt = f"""## 规划器完成汇总任务

「{goal}」的所有步骤已完成。请生成汇总报告并发送到群聊。

### 各步骤结果
{steps_text}

### 你的任务
1. 读取所有相关报告文件（如果步骤结果提到了文件路径）
2. 生成一份精炼的**跨模块汇总**：
   - 最高优先级问题（必须立即修复的）
   - 共性问题（多个模块都有的）
   - 建议的下一步行动计划
3. 用 `bash /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "{chat_id}" "汇总内容"` 发送到群聊
4. 询问用户是否要创建清理/修复计划

### 注意
- 不要用 message 工具
- 最终回复 NO_REPLY
"""

    # Write spawn request (same mechanism as step spawning)
    pending_dir = BASE / "data" / "planner-pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    spawn_file = pending_dir / f"summary-{chat_id[-8:]}.json"
    try:
        with open(spawn_file, "w") as f:
            json.dump({
                "task_id": f"summary-{chat_id[-8:]}",
                "prompt": prompt,
                "created_at": now_iso(),
                "type": "spawn",
            }, f, ensure_ascii=False)
        print(f"[planner] wrote completion summary spawn request", file=sys.stderr)
    except Exception as e:
        print(f"[planner] completion summary spawn error: {e}", file=sys.stderr)


def schedule_advance(chat_id: str):
    """Schedule a PLANNER_ADVANCE cron wake.

    Tries openclaw cron first (exact timing).  Falls back to writing a
    pending file under data/planner-pending/ which is picked up by
    check-advances during heartbeat.
    """
    if DRY_RUN:
        print(f"[dry-run] schedule advance for {chat_id}", file=sys.stderr)
        return
    # Try openclaw cron first
    try:
        at_time = (datetime.now(SGT) + timedelta(seconds=10)).strftime("%H:%M")
        payload = json.dumps({"kind": "systemEvent", "text": f"PLANNER_ADVANCE {chat_id}"})
        result = subprocess.run(
            ["openclaw", "cron", "add", "--at", at_time, "--payload", payload, "--session", "main"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return
    except Exception:
        pass
    # Fallback: write pending file for heartbeat detection
    pending_dir = BASE / "data" / "planner-pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending_file = pending_dir / f"{chat_id_short(chat_id)}.json"
    with open(pending_file, "w") as f:
        json.dump({"chat_id": chat_id, "created_at": now_iso()}, f)

    # Trigger immediate heartbeat to pick up the advance (don't wait 5min)
    try:
        subprocess.run(
            ["openclaw", "cron", "add",
             "--name", f"planner-advance-{chat_id_short(chat_id)}",
             "--at", "10s",
             "--session", "main",
             "--system-event", f"Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.",
             "--wake", "now",
             "--delete-after-run",
             "--json"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pass  # Best effort — heartbeat will still pick it up within 5min


# === Display ===

def _format_time(iso_str: str) -> str:
    """Format ISO timestamp to HH:MM SGT."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(SGT).strftime("%H:%M")
    except Exception:
        return ""


def _short_desc(desc: str, max_len: int = 40) -> str:
    """Shorten step description: strip 'Review: ' prefix, truncate parenthetical detail."""
    d = desc
    # Remove common prefixes
    for prefix in ["Review: ", "Step: "]:
        if d.startswith(prefix):
            d = d[len(prefix):]
    # Truncate at first '（' or '(' if result is too long
    for sep in ["（", " ("]:
        idx = d.find(sep)
        if idx > 0 and idx < max_len:
            d = d[:idx]
            break
    if len(d) > max_len:
        d = d[:max_len-1] + "…"
    return d


def _format_duration(started_at: str, completed_at: str) -> str:
    """Format duration between two ISO timestamps."""
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(completed_at)
        secs = (end - start).total_seconds()
        if secs < 60:
            return f"⏱{secs:.0f}s"
        elif secs < 3600:
            return f"⏱{secs/60:.0f}m"
        else:
            return f"⏱{secs/3600:.1f}h"
    except Exception:
        return ""


def format_plan(plan: dict) -> str:
    """Format plan status as readable text.

    Unified format — one consistent style:
      📋 Plan — <goal>
      ✅ 1. <short desc> <task_id> <duration> — <result summary>
      🔄 2. <short desc> <task_id> <elapsed>
      ❌ 3. <short desc> <task_id> — <error>
      ⬜ 4. <short desc>

    Rules:
      - desc truncated to ~40 chars (strip verbose parenthetical)
      - task_id without backticks
      - result/error summary ≤60 chars
      - cancelled steps hidden
    """
    lines = [f"📋 Plan — {plan['goal']}"]
    if plan["status"] == "draft":
        lines[0] += " [草稿 — 待确认]"
    elif plan["status"] == "cancelled":
        lines[0] += " [CANCELLED]"
    elif plan["status"] == "completed":
        lines[0] += " [COMPLETED]"
    lines.append("")

    for step in plan["steps"]:
        sid = step["id"]
        desc = _short_desc(step["desc"])
        status = step["status"]
        tid = f" {step['task_id']}" if step.get("task_id") else ""

        if status == "done":
            dur = ""
            if step.get("started_at") and step.get("completed_at"):
                d = _format_duration(step["started_at"], step["completed_at"])
                if d:
                    dur = f" {d}"
            result_text = step.get("result", "")
            summary = f" — {result_text}" if result_text else ""
            if len(summary) > 63:
                summary = summary[:60] + "..."
            lines.append(f"✅ {sid}. {desc}{tid}{dur}{summary}")
        elif status == "running":
            time_info = ""
            if step.get("started_at"):
                try:
                    start = datetime.fromisoformat(step["started_at"])
                    mins = (datetime.now(SGT) - start).total_seconds() / 60
                    time_info = f" ⏱{mins:.0f}m"
                except Exception:
                    pass
            lines.append(f"🔄 {sid}. {desc}{tid}{time_info}")
        elif status == "failed":
            err = step.get("error", "")
            err_text = f" — {err}" if err else ""
            if len(err_text) > 63:
                err_text = err_text[:60] + "..."
            lines.append(f"❌ {sid}. {desc}{tid}{err_text}")
        elif status == "cancelled":
            continue  # Hide cancelled steps
        else:  # pending
            risk_tag = " 🔴" if step.get("risk") == "high" else ""
            lines.append(f"⬜ {sid}. {desc}{risk_tag}")

    return "\n".join(lines)


def build_spawn_prompt(plan: dict, step: dict) -> str:
    """Build the spawn prompt for a step, including planner callback footer.

    Uses step['detail'] if available, falls back to step['desc'].
    Appends standardized callback instructions for the subagent.
    """
    chat_id = plan["chat_id"]
    step_id = step["id"]
    planner_py = str(BASE / "scripts" / "planner.py")

    task_manager_py = str(BASE / "scripts" / "task-manager.py")
    task_id = step.get("task_id", "")
    register_line = ""
    if task_id:
        register_line = (
            f"- FIRST thing on start: run `python3 {task_manager_py} set-session {task_id}` "
            f"(registers your session, prevents zombie detection)\n"
        )

    footer = (
        f"\n\n## Planner Callback\n"
        f"{register_line}"
        f"- On success: python3 {planner_py} step-done {chat_id} {step_id} \"<result summary>\"\n"
        f"- On failure: python3 {planner_py} step-fail {chat_id} {step_id} \"<error reason>\"\n"
        f"- Do NOT use the message tool to send messages\n"
        f"- Final reply MUST be NO_REPLY\n"
    )
    return step.get("detail", step["desc"]) + footer


# === Subcommands ===

def cmd_init(chat_id: str, goal: str, steps_json: str):
    """Create a new plan in DRAFT status (does NOT auto-start).

    Args:
        chat_id: Lark chat ID or message_id (om_xxx) to auto-resolve
        goal: Human-readable goal description
        steps_json: JSON array of steps, each with title/prompt or desc/detail

    Behavior:
        - If chat_id starts with 'om_', auto-resolves to chat_id via get-source-chat.py
        - Rejects if an active/draft planner already exists for this chat
        - Creates plan in 'draft' status — NO task creation, NO spawn
        - User reviews the plan, then runs `planner.py start <chat_id>` to begin execution
    """
    # Auto-resolve message_id to chat_id
    chat_id = resolve_chat_id(chat_id)

    # Check for existing active/draft planner
    existing = find_planner_by_chat(chat_id)
    if existing and existing["status"] in ("active", "draft"):
        print(json.dumps({"error": f"{existing['status'].title()} planner already exists for {chat_id}. Cancel it first or use replan."}))
        sys.exit(1)

    try:
        raw_steps = json.loads(steps_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid steps JSON: {e}"}))
        sys.exit(1)

    if not isinstance(raw_steps, list) or not raw_steps:
        print(json.dumps({"error": "steps_json must be a non-empty array"}))
        sys.exit(1)

    # Build steps — normalize_step handles title/prompt → desc/detail mapping
    steps = [normalize_step(s, i) for i, s in enumerate(raw_steps, 1)]

    # Create plan in DRAFT status (not active, not started)
    plan = {
        "chat_id": chat_id,
        "goal": goal,
        "status": "draft",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "steps": steps,
    }

    save_planner(plan)

    # Send plan to chat for review
    draft_text = format_plan(plan)
    send_lark(chat_id, draft_text)

    # Output result
    result = {
        "planner": chat_id_short(chat_id),
        "goal": goal,
        "status": "draft",
        "total_steps": len(steps),
        "message": "计划已创建（草稿状态）。请确认后运行 `planner.py start` 开始执行。",
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_start(chat_id: str):
    """Start executing a draft plan (activate and spawn step 1).

    Args:
        chat_id: Lark chat ID or message_id (om_xxx)

    Behavior:
        - Only works on plans in 'draft' status
        - Changes status to 'active'
        - Creates task for step 1 and spawns it
    """
    chat_id = resolve_chat_id(chat_id)
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(json.dumps({"error": f"No planner found for {chat_id}"}))
        sys.exit(1)

    if plan["status"] != "draft":
        print(json.dumps({"error": f"Plan is '{plan['status']}', not 'draft'. Can only start draft plans."}))
        sys.exit(1)

    plan["status"] = "active"
    plan["started_at"] = now_iso()
    plan["updated_at"] = now_iso()

    # Create task for the first step
    first = plan["steps"][0]
    task_id = tm_add(f"[Plan] {plan['goal']} — Step 1: {first['desc']}", chat_id)
    if task_id:
        first["task_id"] = task_id
        first["status"] = "running"
        first["started_at"] = now_iso()
        tm_start(task_id, "cron-pending")

    save_planner(plan)

    # Spawn step 1
    prompt = build_spawn_prompt(plan, first)
    _spawn_via_cron(first, prompt)

    send_lark(chat_id, format_plan(plan))

    result = {
        "planner": chat_id_short(chat_id),
        "started": True,
        "first_step": {
            "id": first["id"],
            "desc": first["desc"],
            "task_id": first.get("task_id"),
        },
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_show(chat_id: str):
    """Display current plan status as formatted text.

    Args:
        chat_id: Lark chat ID

    Output:
        Formatted plan status using format_plan() icon system.
    """
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(f"No planner found for {chat_id}")
        sys.exit(1)
    print(format_plan(plan))


def cmd_step_done(chat_id: str, step_id: int, result: str):
    """Mark a step as done and auto-advance to next pending step.

    Args:
        chat_id: Lark chat ID
        step_id: Step number (1-based)
        result: Summary of what was accomplished

    Behavior:
        - Guards: step must be 'running' to complete
        - If a later step is already running, just marks done (no advance)
        - Completes the corresponding task in task-board
        - If all steps done → plan status = 'completed'
        - Otherwise, creates task for next pending step and marks it running
        - Sends plan status update to Lark
        - Schedules cron/pending advance for spawning
    """
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(json.dumps({"error": f"No planner found for {chat_id}"}))
        sys.exit(1)

    # Find step
    step = None
    for s in plan["steps"]:
        if s["id"] == step_id:
            step = s
            break
    if not step:
        print(json.dumps({"error": f"Step {step_id} not found"}))
        sys.exit(1)

    # Guard: only allow completing a step that is currently running
    if step["status"] != "running":
        print(json.dumps({"error": f"Step {step_id} is '{step['status']}', not 'running'. Ignoring."}))
        sys.exit(1)

    # Guard: don't advance if there's already another step running after this one
    later_running = any(s["status"] == "running" and s["id"] > step_id for s in plan["steps"])
    if later_running:
        # Just mark done, don't auto-advance (another step is already running)
        step["status"] = "done"
        step["result"] = result
        step["completed_at"] = now_iso()
        if step.get("task_id"):
            tm_complete(step["task_id"], result)
        save_planner(plan)
        print(json.dumps({"advance": False, "reason": "later step already running"}))
        return

    # Update step
    step["status"] = "done"
    step["result"] = result
    step["completed_at"] = now_iso()

    # Complete task in task board
    if step.get("task_id"):
        tm_complete(step["task_id"], result)

    # Check if all steps are done
    all_done = all(s["status"] == "done" for s in plan["steps"])
    if all_done:
        plan["status"] = "completed"
        plan["completed_at"] = now_iso()
        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
        _trigger_group_title_update(plan["chat_id"])
        print(json.dumps({
            "advance": False,
            "completed": True,
            "plan_status": format_plan(plan),
        }, ensure_ascii=False))
        return

    # Find next pending step and advance
    next_step = None
    for s in plan["steps"]:
        if s["status"] == "pending":
            next_step = s
            break

    # Check if completed step was high-risk → pause for user confirmation
    if step.get("risk") == "high" and next_step:
        save_planner(plan)
        pause_msg = format_plan(plan) + f"\n\n⚠️ 高风险步骤 {step['id']} 已完成，请确认系统正常后回复「继续」推进下一步。"
        send_lark(plan["chat_id"], pause_msg)
        _trigger_group_title_update(plan["chat_id"])
        print(json.dumps({
            "advance": False,
            "paused": True,
            "reason": "high_risk_step_completed",
            "next_step": {"id": next_step["id"], "desc": next_step["desc"]},
        }, ensure_ascii=False))
        return

    if next_step:
        # Create task for next step
        task_id = tm_add(
            f"[Plan] {plan['goal']} — Step {next_step['id']}: {next_step['desc']}",
            plan["chat_id"],
        )
        if task_id:
            next_step["task_id"] = task_id
            next_step["status"] = "running"
            next_step["started_at"] = now_iso()
            tm_start(task_id, "cron-pending")

        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
        _trigger_group_title_update(plan["chat_id"])

        spawn_prompt = build_spawn_prompt(plan, next_step)

        # Auto-spawn next step via cron agentTurn (isolated session)
        # This avoids routing through heartbeat LLM which causes 串台
        spawn_ok = False
        if not DRY_RUN:
            spawn_ok = _spawn_via_cron(next_step, spawn_prompt)

        print(json.dumps({
            "advance": True,
            "spawned": spawn_ok,
            "next_step": {
                "id": next_step["id"],
                "desc": next_step["desc"],
                "task_id": next_step.get("task_id"),
            },
            "spawn_prompt": spawn_prompt if not spawn_ok else "(spawned via cron)",
        }, ensure_ascii=False))
    else:
        # No pending steps (some may have failed)
        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
        _trigger_group_title_update(plan["chat_id"])
        print(json.dumps({"advance": False}, ensure_ascii=False))


def cmd_step_fail(chat_id: str, step_id: int, error: str):
    """Mark a step as failed — no auto-advance.

    Args:
        chat_id: Lark chat ID
        step_id: Step number (1-based)
        error: Error description

    Behavior:
        - Guards: step must be 'running' to fail
        - Marks step failed and records error
        - Fails the corresponding task in task-board
        - Sends plan status update to Lark
        - Does NOT auto-advance (human intervention needed)
    """
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(json.dumps({"error": f"No planner found for {chat_id}"}))
        sys.exit(1)

    step = None
    for s in plan["steps"]:
        if s["id"] == step_id:
            step = s
            break
    if not step:
        print(json.dumps({"error": f"Step {step_id} not found"}))
        sys.exit(1)

    # Guard: only allow failing a step that is currently running
    if step["status"] != "running":
        print(json.dumps({"error": f"Step {step_id} is '{step['status']}', not 'running'. Ignoring."}))
        sys.exit(1)

    step["status"] = "failed"
    step["error"] = error
    step["completed_at"] = now_iso()

    if step.get("task_id"):
        tm_fail(step["task_id"], error)

    save_planner(plan)
    send_lark(plan["chat_id"], format_plan(plan))
    _trigger_group_title_update(plan["chat_id"])

    print(json.dumps({
        "advance": False,
        "failed_step": {"id": step["id"], "desc": step["desc"], "error": error},
        "plan_status": format_plan(plan),
    }, ensure_ascii=False))


def cmd_replan(chat_id: str, new_steps_json: str):
    """Replace pending/failed steps with new ones.  Keep done and running steps.

    Args:
        chat_id: Lark chat ID
        new_steps_json: JSON array of new steps (title/prompt or desc/detail)

    Behavior:
        - Keeps all 'done' and 'running' steps
        - Drops all 'pending', 'failed', 'cancelled' steps
        - Appends new steps with sequential IDs continuing from kept steps
        - If no step is running, auto-starts first new pending step
        - Sends plan status update to Lark
    """
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(json.dumps({"error": f"No planner found for {chat_id}"}))
        sys.exit(1)

    try:
        new_raw = json.loads(new_steps_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid steps JSON: {e}"}))
        sys.exit(1)

    if not isinstance(new_raw, list) or not new_raw:
        print(json.dumps({"error": "new_steps_json must be a non-empty array"}))
        sys.exit(1)

    # Keep done + running steps; drop pending/failed/cancelled
    kept = [s for s in plan["steps"] if s["status"] in ("done", "running")]

    # Build new steps with sequential IDs continuing from kept
    next_id = max((s["id"] for s in kept), default=0) + 1
    new_steps = [normalize_step(raw, next_id + i) for i, raw in enumerate(new_raw)]

    plan["steps"] = kept + new_steps

    # If plan was draft, keep it as draft (don't auto-start)
    if plan["status"] == "draft":
        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
        print(json.dumps({
            "replanned": True,
            "kept_steps": len(kept),
            "new_steps": len(new_steps),
            "status": "draft",
            "message": "草稿已更新，等待确认后 start。",
        }, ensure_ascii=False))
        return

    plan["status"] = "active"

    # If no running step, auto-start first pending
    has_running = any(s["status"] == "running" for s in plan["steps"])
    first_pending = None
    if not has_running:
        for s in plan["steps"]:
            if s["status"] == "pending":
                first_pending = s
                break
        if first_pending:
            task_id = tm_add(
                f"[Plan] {plan['goal']} — Step {first_pending['id']}: {first_pending['desc']}",
                plan["chat_id"],
            )
            if task_id:
                first_pending["task_id"] = task_id
                first_pending["status"] = "running"
                first_pending["started_at"] = now_iso()
                tm_start(task_id, "cron-pending")

    save_planner(plan)
    send_lark(plan["chat_id"], format_plan(plan))
    _trigger_group_title_update(plan["chat_id"])

    # Auto-spawn if we auto-started a step
    spawn_ok = False
    if first_pending and first_pending.get("task_id") and not DRY_RUN:
        prompt = build_spawn_prompt(plan, first_pending)
        spawn_ok = _spawn_via_cron(first_pending, prompt)

    result = {
        "replanned": True,
        "kept_steps": len(kept),
        "new_steps": len(new_steps),
    }
    if first_pending and first_pending.get("task_id"):
        result["auto_started"] = {
            "id": first_pending["id"],
            "desc": first_pending["desc"],
            "task_id": first_pending.get("task_id"),
            "spawned": spawn_ok,
        }
    print(json.dumps(result, ensure_ascii=False))


def _trigger_group_title_update(chat_id: str):
    """触发群聊标题更新（fire-and-forget）。
    
    检查配置后，异步调用 update-group-title.py 更新群标题。
    失败不会阻塞主流程。
    """
    import subprocess
    try:
        # 检查配置
        config_path = BASE / "data" / "group-title-config.json"
        if not config_path.exists():
            return
        
        with open(config_path, "r") as f:
            config = json.load(f)
        
        if not config.get("enabled", True):
            return
        
        # 检查该群聊是否启用
        group_config = config.get("groups", {}).get(chat_id, {})
        default_enabled = config.get("default_enabled", False)
        if not group_config.get("enabled", default_enabled):
            return
        
        # 异步触发更新
        script_path = BASE / "scripts" / "update-group-title.py"
        subprocess.Popen(
            ["python3", str(script_path), "--chat-id", chat_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception:
        pass  # 忽略错误，不阻塞主流程


def cmd_cancel(chat_id: str):
    """Cancel entire plan.

    Args:
        chat_id: Lark chat ID

    Behavior:
        - Cancels all running tasks in task-board
        - Marks all running/pending steps as cancelled
        - Sets plan status to 'cancelled'
        - Sends plan status update to Lark
    """
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(json.dumps({"error": f"No planner found for {chat_id}"}))
        sys.exit(1)

    for s in plan["steps"]:
        if s["status"] in ("running", "pending"):
            if s.get("task_id") and s["status"] == "running":
                tm_cancel(s["task_id"])
            s["status"] = "cancelled"
            s["completed_at"] = now_iso()

    plan["status"] = "cancelled"
    save_planner(plan)
    send_lark(plan["chat_id"], format_plan(plan))
    _trigger_group_title_update(plan["chat_id"])

    print(json.dumps({
        "cancelled": True,
        "plan_status": format_plan(plan),
    }, ensure_ascii=False))


def cmd_advance(chat_id: str):
    """Check and advance — called by heartbeat or cron wake.

    Args:
        chat_id: Lark chat ID

    Behavior:
        - No-op if plan is not active or a step is already running
        - Finds first pending step, creates task, marks running
        - Sends plan status and returns spawn_prompt
        - If no pending steps and all done/cancelled → marks plan completed
    """
    plan = find_planner_by_chat(chat_id)
    if not plan:
        print(json.dumps({"advance": False, "reason": "no planner"}))
        return

    if plan["status"] != "active":
        print(json.dumps({"advance": False, "reason": f"plan is {plan['status']}"}))
        return

    # Don't advance if a step is still running
    has_running = any(s["status"] == "running" for s in plan["steps"])
    if has_running:
        print(json.dumps({"advance": False, "reason": "step still running"}))
        return

    # Find first pending step
    next_step = None
    for s in plan["steps"]:
        if s["status"] == "pending":
            next_step = s
            break

    if not next_step:
        # Check if all done
        all_done = all(s["status"] in ("done", "cancelled") for s in plan["steps"])
        if all_done:
            plan["status"] = "completed"
            save_planner(plan)
        print(json.dumps({"advance": False, "reason": "no pending steps"}))
        return

    # Create task and advance
    task_id = tm_add(
        f"[Plan] {plan['goal']} — Step {next_step['id']}: {next_step['desc']}",
        plan["chat_id"],
    )
    if task_id:
        next_step["task_id"] = task_id
        next_step["status"] = "running"
        next_step["started_at"] = now_iso()
        tm_start(task_id, "cron-pending")

    save_planner(plan)
    send_lark(plan["chat_id"], format_plan(plan))
    _trigger_group_title_update(plan["chat_id"])

    # Auto-spawn via pending file
    spawn_prompt = build_spawn_prompt(plan, next_step)
    spawn_ok = False
    if not DRY_RUN:
        spawn_ok = _spawn_via_cron(next_step, spawn_prompt)

    print(json.dumps({
        "advance": True,
        "spawned": spawn_ok,
        "next_step": {
            "id": next_step["id"],
            "desc": next_step["desc"],
            "task_id": next_step.get("task_id"),
        },
        "spawn_prompt": spawn_prompt if not spawn_ok else "(spawn request written)",
    }, ensure_ascii=False))


def cmd_check_advances():
    """Check all active planners for needed advances.  Used by heartbeat.

    Scans all planner JSON files and pending advance files.
    Reports which planners need advancement (no running step + has pending steps).
    Cleans up processed pending files.

    Output JSON:
        {
            "planners": [{"chat_id", "goal", "progress"}],
            "advances_needed": [{"chat_id", "goal", "next_step", "spawn_prompt"}]
        }
    """
    if not DATA_DIR.exists():
        print(json.dumps({"planners": [], "advances_needed": []}))
        return

    advances = []
    active_planners = []

    for fp in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(fp) as f:
                plan = json.load(f)
        except Exception:
            continue

        if plan.get("status") != "active":
            continue

        chat_id = plan["chat_id"]
        active_planners.append({
            "chat_id": chat_id,
            "goal": plan["goal"],
            "progress": f"{sum(1 for s in plan['steps'] if s['status'] == 'done')}/{len(plan['steps'])}",
        })

        # Only report advance needed if NO step is running
        has_running = any(s["status"] == "running" for s in plan["steps"])
        if has_running:
            continue

        next_pending = None
        for s in plan["steps"]:
            if s["status"] == "pending":
                next_pending = s
                break

        if next_pending:
            advances.append({
                "chat_id": chat_id,
                "goal": plan["goal"],
                "next_step": {
                    "id": next_pending["id"],
                    "desc": next_pending["desc"],
                    "detail": next_pending.get("detail", ""),
                },
                "spawn_prompt": build_spawn_prompt(plan, next_pending),
            })

    # Also check pending files (spawn requests from step-done)
    pending_dir = BASE / "data" / "planner-pending"
    spawns_needed = []
    if pending_dir.exists():
        for pf in pending_dir.glob("*.json"):
            try:
                with open(pf) as f:
                    pending = json.load(f)

                if pending.get("type") == "spawn":
                    # Direct spawn request from _spawn_via_cron
                    spawns_needed.append({
                        "task_id": pending["task_id"],
                        "prompt": pending["prompt"],
                        "file": str(pf),
                    })
                    pf.unlink()
                    continue

                # Legacy: advance request with chat_id
                pending_chat = pending.get("chat_id", "")
                # Check if already in advances list
                already = any(a["chat_id"] == pending_chat for a in advances)
                if not already:
                    plan = find_planner_by_chat(pending_chat)
                    if plan and plan["status"] == "active":
                        # Must check has_running here too (bug fix)
                        has_running = any(s["status"] == "running" for s in plan["steps"])
                        if not has_running:
                            next_pending = None
                            for s in plan["steps"]:
                                if s["status"] == "pending":
                                    next_pending = s
                                    break
                            if next_pending:
                                advances.append({
                                    "chat_id": pending_chat,
                                    "goal": plan["goal"],
                                    "next_step": {
                                        "id": next_pending["id"],
                                        "desc": next_pending["desc"],
                                        "detail": next_pending.get("detail", ""),
                                    },
                                    "spawn_prompt": build_spawn_prompt(plan, next_pending),
                                })
                # Clean up pending file regardless
                pf.unlink()
            except Exception:
                continue

    result = {
        "planners": active_planners,
        "advances_needed": advances,
    }
    if spawns_needed:
        result["spawns_needed"] = spawns_needed
    print(json.dumps(result, ensure_ascii=False))


def cmd_list():
    """List all planners (active ones first).

    Output format per planner:
        <status_icon> [<chat_id_short>] <goal> (<done>/<total>) [| running: Step N]

    Status icons: 🟢 active / ✅ completed / 🚫 cancelled
    """
    if not DATA_DIR.exists():
        print("No planners found.")
        return

    plans = []
    for fp in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(fp) as f:
                p = json.load(f)
            plans.append(p)
        except Exception:
            continue

    if not plans:
        print("No planners found.")
        return

    # Active first, then completed, then cancelled
    order = {"active": 0, "completed": 1, "cancelled": 2}
    plans.sort(key=lambda p: (order.get(p.get("status", ""), 9), p.get("created_at", "")))

    for p in plans:
        status_icon = {"active": "🟢", "completed": "✅", "cancelled": "🚫"}.get(p["status"], "❓")
        done = sum(1 for s in p["steps"] if s["status"] == "done")
        total = len(p["steps"])
        running = [s for s in p["steps"] if s["status"] == "running"]
        running_info = f" | running: Step {running[0]['id']}" if running else ""
        print(f"{status_icon} [{chat_id_short(p['chat_id'])}] {p['goal']} ({done}/{total}){running_info}")


def cmd_find_by_task(task_id: str):
    """Find which planner and step a task_id belongs to.

    Args:
        task_id: Task board task ID (e.g. t008)

    Output JSON:
        {found, chat_id, goal, planner_status, step, advance, next_step?}

    Useful for tracing a task back to its planner context.
    """
    if not DATA_DIR.exists():
        print(json.dumps({"found": False}))
        return

    for fp in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(fp) as f:
                p = json.load(f)
        except Exception:
            continue

        for step in p.get("steps", []):
            if step.get("task_id") == task_id:
                # Found the step — check if there's a next step to advance to
                next_step = None
                advance = False
                if step["status"] == "done":
                    for s in p["steps"]:
                        if s["status"] == "pending":
                            next_step = s
                            advance = True
                            break

                result = {
                    "found": True,
                    "chat_id": p["chat_id"],
                    "goal": p["goal"],
                    "planner_status": p["status"],
                    "step": {"id": step["id"], "desc": step["desc"], "status": step["status"]},
                    "advance": advance,
                }
                if next_step:
                    result["next_step"] = {
                        "id": next_step["id"],
                        "desc": next_step["desc"],
                        "detail": next_step.get("detail", ""),
                    }
                print(json.dumps(result, ensure_ascii=False))
                return

    print(json.dumps({"found": False}))


# === Main ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Check for --dry-run flag
    if "--dry-run" in sys.argv:
        DRY_RUN = True
        sys.argv.remove("--dry-run")

    cmd = sys.argv[1]

    if cmd == "init":
        if len(sys.argv) < 5:
            print("Usage: planner.py init <chat_id|message_id> <goal> <steps_json>", file=sys.stderr)
            sys.exit(1)
        cmd_init(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd == "start":
        if len(sys.argv) < 3:
            print("Usage: planner.py start <chat_id|message_id>", file=sys.stderr)
            sys.exit(1)
        cmd_start(sys.argv[2])

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("Usage: planner.py show <chat_id>", file=sys.stderr)
            sys.exit(1)
        cmd_show(sys.argv[2])

    elif cmd == "step-done":
        if len(sys.argv) < 5:
            print("Usage: planner.py step-done <chat_id> <step_id> \"<result>\"", file=sys.stderr)
            sys.exit(1)
        try:
            sid = int(sys.argv[3])
        except ValueError:
            print(f"Error: step_id must be an integer, got '{sys.argv[3]}'", file=sys.stderr)
            sys.exit(1)
        cmd_step_done(sys.argv[2], sid, sys.argv[4])

    elif cmd == "step-fail":
        if len(sys.argv) < 5:
            print("Usage: planner.py step-fail <chat_id> <step_id> \"<error>\"", file=sys.stderr)
            sys.exit(1)
        try:
            sid = int(sys.argv[3])
        except ValueError:
            print(f"Error: step_id must be an integer, got '{sys.argv[3]}'", file=sys.stderr)
            sys.exit(1)
        cmd_step_fail(sys.argv[2], sid, sys.argv[4])

    elif cmd == "replan":
        if len(sys.argv) < 4:
            print("Usage: planner.py replan <chat_id> <new_steps_json>", file=sys.stderr)
            sys.exit(1)
        cmd_replan(sys.argv[2], sys.argv[3])

    elif cmd == "cancel":
        if len(sys.argv) < 3:
            print("Usage: planner.py cancel <chat_id>", file=sys.stderr)
            sys.exit(1)
        cmd_cancel(sys.argv[2])

    elif cmd == "advance":
        if len(sys.argv) < 3:
            print("Usage: planner.py advance <chat_id>", file=sys.stderr)
            sys.exit(1)
        cmd_advance(sys.argv[2])

    elif cmd == "check-advances":
        cmd_check_advances()

    elif cmd == "list":
        cmd_list()

    elif cmd == "find-by-task":
        if len(sys.argv) < 3:
            print("Usage: planner.py find-by-task <task_id>", file=sys.stderr)
            sys.exit(1)
        cmd_find_by_task(sys.argv[2])

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
