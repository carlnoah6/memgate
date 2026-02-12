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
    """
    desc = raw.get("title") or raw.get("desc") or f"Step {step_id}"
    detail = raw.get("prompt") or raw.get("detail") or ""
    return {
        "id": step_id,
        "desc": desc,
        "detail": detail,
        "status": "pending",
    }


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


def format_plan(plan: dict) -> str:
    """Format plan status as readable text.

    Icon system (hardcoded — do NOT invent new icons):
      📋 Plan title
      ✅ done (with task_id, completion time, result summary ≤80 chars)
      🔄 running (with task_id, start time, elapsed minutes)
      ❌ failed (with task_id, error ≤80 chars)
      ⬜ pending
      cancelled steps are hidden

    All steps are always shown — never fold/collapse.
    """
    lines = [f"📋 Plan — {plan['goal']}"]
    if plan["status"] == "cancelled":
        lines[0] += " [CANCELLED]"
    elif plan["status"] == "completed":
        lines[0] += " [COMPLETED]"
    lines.append("")

    for step in plan["steps"]:
        sid = step["id"]
        desc = step["desc"]
        status = step["status"]
        tid = f" `{step['task_id']}`" if step.get("task_id") else ""

        if status == "done":
            done_time = ""
            if step.get("completed_at"):
                t = _format_time(step["completed_at"])
                if t:
                    done_time = f" ✅{t}"
            result_text = step.get("result", "")
            summary = f" — {result_text}" if result_text else ""
            if len(summary) > 80:
                summary = summary[:77] + "..."
            lines.append(f"✅ {sid}. {desc}{tid}{done_time}{summary}")
        elif status == "running":
            time_info = ""
            if step.get("started_at"):
                try:
                    start = datetime.fromisoformat(step["started_at"])
                    start_hm = start.astimezone(SGT).strftime("%H:%M")
                    mins = (datetime.now(SGT) - start).total_seconds() / 60
                    time_info = f" ⏱️{start_hm}起 ({mins:.0f}min)"
                except Exception:
                    pass
            lines.append(f"🔄 {sid}. {desc}{tid}{time_info}")
        elif status == "failed":
            err = step.get("error", "")
            err_text = f" — {err}" if err else ""
            if len(err_text) > 80:
                err_text = err_text[:77] + "..."
            lines.append(f"❌ {sid}. {desc}{tid}{err_text}")
        elif status == "cancelled":
            continue  # Hide cancelled steps from display
        else:  # pending
            lines.append(f"⬜ {sid}. {desc}{tid}")

    return "\n".join(lines)


def build_spawn_prompt(plan: dict, step: dict) -> str:
    """Build the spawn prompt for a step, including planner callback footer.

    Uses step['detail'] if available, falls back to step['desc'].
    Appends standardized callback instructions for the subagent.
    """
    chat_id = plan["chat_id"]
    step_id = step["id"]
    planner_py = str(BASE / "scripts" / "planner.py")

    footer = (
        f"\n\n## Planner Callback\n"
        f"- On success: python3 {planner_py} step-done {chat_id} {step_id} \"<result summary>\"\n"
        f"- On failure: python3 {planner_py} step-fail {chat_id} {step_id} \"<error reason>\"\n"
        f"- Do NOT use the message tool to send messages\n"
        f"- Final reply MUST be NO_REPLY\n"
    )
    return step.get("detail", step["desc"]) + footer


# === Subcommands ===

def cmd_init(chat_id: str, goal: str, steps_json: str):
    """Create a new plan.

    Args:
        chat_id: Lark chat ID for this plan
        goal: Human-readable goal description
        steps_json: JSON array of steps, each with title/prompt or desc/detail

    Behavior:
        - Rejects if an active planner already exists for this chat
        - Creates tasks in task-board for step 1 and marks it running
        - Returns JSON with planner info and spawn_prompt for step 1
    """
    # Check for existing active planner
    existing = find_planner_by_chat(chat_id)
    if existing and existing["status"] == "active":
        print(json.dumps({"error": f"Active planner already exists for {chat_id}. Cancel it first or use replan."}))
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

    # Create plan
    plan = {
        "chat_id": chat_id,
        "goal": goal,
        "status": "active",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "steps": steps,
    }

    # Create task for the first step
    first = steps[0]
    task_id = tm_add(f"[Plan] {goal} — Step 1: {first['desc']}", chat_id)
    if task_id:
        first["task_id"] = task_id
        first["status"] = "running"
        first["started_at"] = now_iso()
        tm_start(task_id)

    save_planner(plan)

    # Output result
    result = {
        "planner": chat_id_short(chat_id),
        "goal": goal,
        "total_steps": len(steps),
        "first_step": {
            "id": first["id"],
            "desc": first["desc"],
            "task_id": first.get("task_id"),
        },
        "spawn_prompt": build_spawn_prompt(plan, first),
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
        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
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
            tm_start(task_id)

        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
        schedule_advance(plan["chat_id"])

        print(json.dumps({
            "advance": True,
            "next_step": {
                "id": next_step["id"],
                "desc": next_step["desc"],
                "task_id": next_step.get("task_id"),
            },
            "spawn_prompt": build_spawn_prompt(plan, next_step),
        }, ensure_ascii=False))
    else:
        # No pending steps (some may have failed)
        save_planner(plan)
        send_lark(plan["chat_id"], format_plan(plan))
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
                tm_start(task_id)

    save_planner(plan)
    send_lark(plan["chat_id"], format_plan(plan))

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
        }
        result["spawn_prompt"] = build_spawn_prompt(plan, first_pending)
    print(json.dumps(result, ensure_ascii=False))


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
        tm_start(task_id)

    save_planner(plan)
    send_lark(plan["chat_id"], format_plan(plan))

    print(json.dumps({
        "advance": True,
        "next_step": {
            "id": next_step["id"],
            "desc": next_step["desc"],
            "task_id": next_step.get("task_id"),
        },
        "spawn_prompt": build_spawn_prompt(plan, next_step),
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

    # Also check pending files (fallback from failed cron scheduling)
    pending_dir = BASE / "data" / "planner-pending"
    if pending_dir.exists():
        for pf in pending_dir.glob("*.json"):
            try:
                with open(pf) as f:
                    pending = json.load(f)
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

    print(json.dumps({
        "planners": active_planners,
        "advances_needed": advances,
    }, ensure_ascii=False))


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
            print("Usage: planner.py init <chat_id> <goal> <steps_json>", file=sys.stderr)
            sys.exit(1)
        cmd_init(sys.argv[2], sys.argv[3], sys.argv[4])

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
