#!/usr/bin/env python3
"""Luna OS — Planner (Orchestration Layer) — Neon PostgreSQL Backend

Sits on top of TaskStore (Neon PostgreSQL) and provides ordered
multi-step execution with automatic advancement.

Each group chat can have one active planner. Steps map 1-to-1 to
task-board tasks (tid-xxx).

Usage:
  planner.py init <chat_id> <goal> <steps_json>          — Create a new plan
  planner.py show <chat_id>                               — Display plan status
  planner.py step-done <chat_id> <step_id> "<result>"     — Mark step done & advance
  planner.py step-fail <chat_id> <step_id> "<error>"      — Mark step failed
  planner.py replan <chat_id> <new_steps_json> [--append] — Replace (or append to) pending steps
  planner.py cancel <chat_id>                             — Cancel entire plan
  planner.py advance <chat_id>                            — Check & advance (heartbeat)
  planner.py check-advances                               — Check all active planners
  planner.py check-contracts                              — Check events & auto-complete
  planner.py list                                         — List active planners
  planner.py find-by-task <task_id>                       — Find plan by task ID

Steps JSON format (both init and replan):
  [{"title": "...", "prompt": "..."}]   — preferred
  [{"desc": "...", "detail": "..."}]    — also supported (mapped internally)

Flags:
  --dry-run    Skip Lark messaging and DB writes
"""

import json
import os
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from task_store import TaskStore
from dashboard_updater import update_dashboard as _update_dashboard
from planner_helpers import (
    get_store, now_iso, chat_id_short, resolve_chat_id, resolve_full_chat_id,
    normalize_step, send_lark, _format_duration, _short_desc,
    _build_plan_summary, format_plan, send_plan_graph,
    DRY_RUN, BASE, SGT, LARK_SEND,
)
from planner_templates import list_templates, load_template, render_template
from planner_spawn import (
    build_spawn_prompt, _create_task_chat, _spawn_via_session,
    _spawn_via_cron, _prepare_and_spawn, schedule_advance,
    _trigger_group_title_update, _start_ready_steps,
)

TASK_CHAT = BASE / 'scripts' / 'task-chat.py'
GET_SOURCE_CHAT = BASE / 'scripts' / 'get-source-chat.py'


def cmd_init(chat_id: str, goal: str, steps_json: str,
             template_name: str = None, template_vars: dict = None):
    """Create a new plan (draft mode — use cmd_start to activate).
    
    If template_name is provided, goal and steps are loaded from template.
    template_vars overrides template variables.
    """
    chat_id = resolve_chat_id(chat_id)
    store = get_store()
    plan_id = store.next_plan_id()

    # Check for existing active plan — suggest replan instead of blocking
    existing = store.get_plan_by_chat(chat_id, status_filter='active')
    if existing:
        done_steps = [s for s in existing.get("steps", []) if s["status"] == "done"]
        running_steps = [s for s in existing.get("steps", []) if s["status"] == "running"]
        pending_steps = [s for s in existing.get("steps", []) if s["status"] == "pending"]
        print(json.dumps({
            "error": f"Active plan already exists: {existing['id']}",
            "existing_goal": existing["goal"],
            "done": len(done_steps),
            "running": len(running_steps),
            "pending": len(pending_steps),
            "hint": "Use 'planner.py replan' to modify pending steps, or 'planner.py cancel' first if this is a completely different goal."
        }))
        sys.exit(1)

    # Template mode
    if template_name:
        tmpl = load_template(template_name)
        if not tmpl:
            print(json.dumps({"error": f"Template not found: {template_name}"}))
            sys.exit(1)
        try:
            goal, steps = render_template(tmpl, template_vars or {})
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    else:
        # Parse steps from JSON
        raw_steps = json.loads(steps_json) if isinstance(steps_json, str) else steps_json
        steps = [normalize_step(s) for s in raw_steps]

    if not steps:
        print(json.dumps({"error": "No steps provided"}))
        sys.exit(1)

    # Create plan in DB
    plan = store.create_plan(plan_id, chat_id, goal, steps)
    store.update_plan_status(plan_id, "draft")

    # Send plan with confirmation hint
    plan_text = format_plan(plan)
    plan_text += "\n\n⏳ 等待确认。30分钟内未确认将自动取消。"
    plan_text += "\n回复「确认」开始执行，或「修改」调整步骤。"
    send_lark(chat_id, plan_text)

    # Generate and send timeline graph
    send_plan_graph(plan, chat_id)

    print(json.dumps({
        "plan_id": plan_id,
        "chat_id": chat_id,
        "goal": goal,
        "steps": len(steps),
        "status": "draft",
        "message": "Draft created. Awaiting confirmation (30min timeout).",
    }, ensure_ascii=False))



def cmd_start(chat_id: str):
    """Activate a draft plan and start all ready steps (parallel if no deps)."""
    chat_id = resolve_chat_id(chat_id)
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='draft')

    if not plan:
        print(json.dumps({"error": f"No plan found for {chat_id}"}))
        sys.exit(1)

    store.update_plan_status(plan["id"], "active")

    # Start all ready steps (those with no unmet dependencies)
    ready = store.ready_steps(plan["id"])
    results = []
    if ready:
        results = _start_ready_steps(store, plan, ready)

        # Reload plan for display
        plan = store.get_plan(plan["id"])
        send_lark(plan["chat_id"], format_plan(plan))
        send_plan_graph(plan)
        _trigger_group_title_update(plan["chat_id"])

    print(json.dumps({
        "started": True,
        "plan_id": plan["id"],
        "parallel_steps": [r[0] for r in results],
        "spawned": [r[1] for r in results],
    }, ensure_ascii=False))



def cmd_show(identifier: str, send_graph: bool = False):
    """Display plan status. Accepts plan ID, chat_id, or chat_id suffix.
    
    If send_graph=True, also generates and sends a dependency graph image to the chat.
    """
    store = get_store()
    # Try direct plan ID first (any status)
    plan = store.get_plan(identifier)
    if not plan:
        # Fallback to chat_id lookup
        plan = store.get_plan_by_chat(identifier)
    if not plan:
        print(f"No plan found for {identifier}")
        sys.exit(1)
    print(format_plan(plan))

    if send_graph and plan.get("chat_id"):
        try:
            send_plan_graph(plan)
        except Exception as e:
            print(f"[planner] graph generation failed: {e}", file=sys.stderr)



def cmd_step_done(chat_id: str, step_num: int, result: str):
    """Mark a step as done and advance to next."""
    chat_id = resolve_chat_id(chat_id)
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='active')

    if not plan:
        print(json.dumps({"error": f"No plan found for {chat_id}"}))
        sys.exit(1)

    # Guard: skip if step already done (idempotency)
    existing = store.get_step(plan["id"], step_num)
    if existing and existing["status"] == "done":
        print(json.dumps({"skipped": True, "reason": "step already done", "step": step_num}))
        return

    # Complete the step
    store.complete_step(plan["id"], step_num, result)

    # Complete the associated task
    step = store.get_step(plan["id"], step_num)
    if step and step.get("task_id"):
        store.complete_task(step["task_id"], result)
        # NOTE: do NOT emit step.done here — task_manager.complete already emits it.
        # Emitting here causes chain reaction: check-contracts -> cmd_step_done -> emit -> check-contracts -> ...
        # Notify the task chat if one exists
        task = store.get_task(step["task_id"])
        task_chat_id = task.get("task_chat_id", "") if task else ""
        if task_chat_id:
            send_lark(task_chat_id,
                      f"Step {step_num} completed: {_short_desc(result, 120)}")

        # Send step summary to source chat
        step_title = step.get("title", f"Step {step_num}")
        send_lark(plan["chat_id"], f"✅ Step {step_num} ({step_title}) 完成\n{_short_desc(result, 300)}")


    # Try to advance — start all newly-ready steps (parallel support)
    ready = store.ready_steps(plan["id"])
    spawn_results = []
    plan_completed = False

    if ready:
        spawn_results = _start_ready_steps(store, plan, ready)

        plan = store.get_plan(plan["id"])
        send_lark(plan["chat_id"], format_plan(plan))
        send_plan_graph(plan)
        _trigger_group_title_update(plan["chat_id"])
    else:
        # No ready steps — check if ALL steps are done
        plan = store.get_plan(plan["id"])
        all_steps = plan.get("steps", [])
        still_running = [s for s in all_steps if s["status"] == "running"]
        if still_running:
            # Some steps still running — don't mark completed yet, just update display
            send_lark(plan["chat_id"], format_plan(plan))
            send_plan_graph(plan)
        else:
            # All steps truly done — mark plan completed and send summary
            store.update_plan_status(plan["id"], "completed")
            plan = store.get_plan(plan["id"])
            summary = _build_plan_summary(plan)
            send_lark(plan["chat_id"], format_plan(plan))
            send_plan_graph(plan)
            if summary:
                send_lark(plan["chat_id"], summary)
            _trigger_group_title_update(plan["chat_id"])
            plan_completed = True

    _update_dashboard(trigger="step_done")

    print(json.dumps({
        "step_done": step_num,
        "result": result[:100],
        "next_steps": [r[0] for r in spawn_results],
        "spawned": [r[1] for r in spawn_results],
        "plan_completed": plan_completed,
    }, ensure_ascii=False))



def cmd_step_fail(chat_id: str, step_num: int, error: str):
    """Mark a step as failed. Idempotent — skips if already failed."""
    chat_id = resolve_chat_id(chat_id)
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='active')

    if not plan:
        print(json.dumps({"error": f"No plan found for {chat_id}"}))
        sys.exit(1)

    # Idempotent: skip if step already failed (prevents event storm)
    existing_step = store.get_step(plan["id"], step_num)
    if existing_step and existing_step.get("status") == "failed":
        print(json.dumps({"step_already_failed": step_num}))
        return

    store.fail_step(plan["id"], step_num, error)

    step = store.get_step(plan["id"], step_num)
    if step and step.get("task_id"):
        task = store.get_task(step["task_id"])
        # Only fail task if not already failed
        if task and task.get("status") != "failed":
            store.fail_task(step["task_id"], error)
            # NOTE: do NOT emit step.failed here — the original trigger
            # (task_manager, emit_event.py) is responsible for emitting.
            # Emitting here causes event storm: check-contracts → cmd_step_fail → emit → check-contracts → ...
        # Notify the task chat if one exists
        task = store.get_task(step["task_id"])
        task_chat_id = task.get("task_chat_id", "") if task else ""
        if task_chat_id:
            send_lark(task_chat_id,
                      f"Step {step_num} FAILED: {_short_desc(error, 120)}")

    plan = store.get_plan(plan["id"])
    send_lark(plan["chat_id"], format_plan(plan))
    send_plan_graph(plan)

    _update_dashboard(trigger="step_fail")

    print(json.dumps({
        "step_failed": step_num,
        "error": error[:100],
    }, ensure_ascii=False))



def cmd_replan(chat_id: str, new_steps_json: str, append: bool = False):
    """Replace or append pending steps. Works on active and draft plans.
    
    If append=True, keeps existing pending steps and adds new ones after them.
    If append=False (default), replaces all pending steps with new ones.
    """
    chat_id = resolve_chat_id(chat_id)
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='active')
    if not plan:
        plan = store.get_plan_by_chat(chat_id, status_filter='draft')

    if not plan:
        print(json.dumps({"error": f"No plan found for {chat_id}"}))
        sys.exit(1)

    raw_steps = json.loads(new_steps_json) if isinstance(new_steps_json, str) else new_steps_json
    new_steps = [normalize_step(s) for s in raw_steps]

    all_steps = plan.get("steps", [])
    conn = store.get_conn()
    cur = conn.cursor()
    if append:
        # Keep everything, add new steps after the last step
        next_num = max((s["step_num"] for s in all_steps), default=0) + 1
    else:
        # Keep completed/running steps, replace pending
        kept = [s for s in all_steps if s["status"] in ("done", "running", "failed")]
        next_num = max((s["step_num"] for s in kept), default=0) + 1
        # Delete old pending steps from DB
        cur.execute("DELETE FROM plan_steps WHERE plan_id = %s AND status = 'pending'", (plan["id"],))
        conn.commit()

    # Insert new steps
    for i, ns in enumerate(new_steps):
        cur.execute("""
            INSERT INTO plan_steps (plan_id, step_num, title, prompt, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (plan["id"], next_num + i, ns["title"], ns["prompt"]))
    conn.commit()

    # Preserve original status: draft stays draft, active stays active
    original_status = plan.get("status", "draft")
    if original_status == "active":
        # Only auto-advance if plan was already active
        plan = store.get_plan(plan["id"])
        has_running = any(s["status"] == "running" for s in plan.get("steps", []))
        if not has_running:
            first_pending = store.next_pending_step(plan["id"])
            if first_pending:
                task_id = store.next_task_id()
                store.add_task(task_id, f"[Plan] {plan['goal']} — Step {first_pending['step_num']}: {first_pending['title']}",
                               source_chat=plan["chat_id"])
                store.start_task(task_id, "cron-pending")
                store.start_step(plan["id"], first_pending["step_num"], task_id)

    plan = store.get_plan(plan["id"])
    send_lark(plan["chat_id"], format_plan(plan))
    send_plan_graph(plan)
    _trigger_group_title_update(plan["chat_id"])

    if first_pending and first_pending.get("task_id"):
        fp_updated = store.get_step(plan["id"], first_pending["step_num"])
        spawn_ok = _prepare_and_spawn(plan, fp_updated)

    print(json.dumps({
        "replanned": True,
        "kept_steps": len(kept),
        "new_steps": len(new_steps),
        "spawned": spawn_ok,
    }, ensure_ascii=False))



def cmd_cancel(chat_id: str):
    """Cancel entire plan. Works on active and draft plans."""
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='active')
    if not plan:
        plan = store.get_plan_by_chat(chat_id, status_filter='draft')

    if not plan:
        print(json.dumps({"error": f"No planner found for {chat_id}"}))
        sys.exit(1)

    # Cancel all running/pending steps
    for s in plan.get("steps", []):
        if s["status"] in ("running", "pending"):
            if s.get("task_id") and s["status"] == "running":
                store.cancel_task(s["task_id"])
            store.update_step(plan["id"], s["step_num"], status="cancelled")

    store.cancel_plan(plan["id"])
    plan = store.get_plan(plan["id"])
    send_lark(plan["chat_id"], format_plan(plan))
    send_plan_graph(plan)
    _trigger_group_title_update(plan["chat_id"])

    print(json.dumps({
        "cancelled": True,
        "plan_status": format_plan(plan),
    }, ensure_ascii=False))



def cmd_advance(chat_id: str):
    """Check if current step is done and advance."""
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='active')

    if not plan or plan["status"] != "active":
        print(json.dumps({"advance": False, "reason": "no active plan"}))
        return

    running = [s for s in plan.get("steps", []) if s["status"] == "running"]
    if not running:
        # No running step — try to start ready steps (respects depends_on)
        ready = store.ready_steps(plan["id"])
        if ready:
            spawn_results = _start_ready_steps(store, plan, ready)
            plan = store.get_plan(plan["id"])
            send_lark(plan["chat_id"], format_plan(plan))
            send_plan_graph(plan)
            started = [s for s, ok in spawn_results if ok]
            print(json.dumps({"advance": True, "started_steps": started}))
        else:
            # No pending steps — check if ALL steps are done
            plan = store.get_plan(plan["id"])
            still_running = [s for s in plan.get("steps", []) if s["status"] == "running"]
            if still_running:
                send_lark(plan["chat_id"], format_plan(plan))
                send_plan_graph(plan)
                print(json.dumps({"advance": False, "still_running": len(still_running)}))
            else:
                store.update_plan_status(plan["id"], "completed")
                plan = store.get_plan(plan["id"])
                summary = _build_plan_summary(plan)
                send_lark(plan["chat_id"], format_plan(plan))
                send_plan_graph(plan)
                if summary:
                    send_lark(plan["chat_id"], summary)
                print(json.dumps({"advance": True, "plan_completed": True}))
        return

    # Check if running step's task is actually done
    current = running[0]
    if current.get("task_id"):
        task = store.get_task(current["task_id"])
        if task and task["status"] == "done":
            result = task.get("result", "")
            cmd_step_done(chat_id, current["step_num"], result)
            return
        elif task and task["status"] == "failed":
            error = task.get("result", "unknown error")
            cmd_step_fail(chat_id, current["step_num"], error)
            return

    print(json.dumps({"advance": False, "reason": "step still running",
                       "step": current["step_num"]}))




def cmd_pause(chat_id: str):
    """Pause an active plan."""
    chat_id = resolve_chat_id(chat_id)
    store = get_store()
    plan = store.get_plan_by_chat(chat_id, status_filter='active')
    if not plan:
        print(json.dumps({"error": "No active plan found"}))
        sys.exit(1)

    store.update_plan_status(plan["id"], "paused")
    send_lark(plan["chat_id"], f"⏸️ 计划已暂停: {plan['goal'][:60]}\n\n回复 `resume` 恢复。")
    print(json.dumps({"paused": True, "plan_id": plan["id"]}))


def cmd_resume(plan_id_or_chat: str):
    """Resume a paused plan. Accepts plan_id, chat_id, or 'all'."""
    store = get_store()

    if plan_id_or_chat == "all":
        paused = store.list_plans(status="paused")
        resumed = []
        for p in paused:
            store.update_plan_status(p["id"], "active")
            full = store.get_plan(p["id"])
            if full:
                send_lark(full["chat_id"], f"▶️ 计划已恢复: {full['goal'][:60]}")
                # Trigger advancement
                try:
                    cmd_advance(full["chat_id"])
                except Exception:
                    pass
            resumed.append(p["id"])
        print(json.dumps({"resumed": resumed, "count": len(resumed)}))
        return

    # Try as plan_id first
    plan = store.get_plan(plan_id_or_chat)
    if not plan:
        # Try as chat_id
        plan = store.get_plan_by_chat(resolve_chat_id(plan_id_or_chat), status_filter='paused')
    if not plan:
        print(json.dumps({"error": f"No paused plan found for {plan_id_or_chat}"}))
        sys.exit(1)

    if plan["status"] != "paused":
        print(json.dumps({"error": f"Plan {plan['id']} is {plan['status']}, not paused"}))
        sys.exit(1)

    store.update_plan_status(plan["id"], "active")
    send_lark(plan["chat_id"], f"▶️ 计划已恢复: {plan['goal'][:60]}")
    # Trigger advancement
    try:
        cmd_advance(plan["chat_id"])
    except Exception:
        pass
    print(json.dumps({"resumed": True, "plan_id": plan["id"]}))


def cmd_check_advances():
    """Check all active planners for advancement."""
    store = get_store()
    plans = store.list_plans(status="active")
    advanced = 0
    for p in plans:
        try:
            cmd_advance(p["chat_id"])
            advanced += 1
        except Exception as e:
            print(f"[planner] advance error for {p['id']}: {e}", file=sys.stderr)
    print(json.dumps({"checked": len(plans), "advanced": advanced}))



def _resolve_plan_for_task(store, task_id):
    """Find plan_id and step_num for a given task_id."""
    plans = store.list_plans(status="active")
    for p in plans:
        full = store.get_plan(p["id"])
        for s in full.get("steps", []):
            if s.get("task_id") == task_id:
                return p["id"], s["step_num"]
    return None, None




def _was_circuit_broken(session_id: str) -> bool:
    """Check if a session was killed by loop detection circuit breaker."""
    import glob
    session_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    return bool(glob.glob(str(session_dir / f"{session_id}.jsonl.loop-*")))


def _is_agent_process_alive(session_id: str) -> bool:
    """Check if an openclaw-agent session is still active.
    
    Uses session file modification time as the primary signal:
    - If .jsonl was modified in the last 3 minutes → alive
    - If .jsonl.lock exists and was created recently → alive
    - If circuit breaker .loop-* file exists → dead
    
    Note: pgrep doesn't work because openclaw-agent doesn't expose
    --session-id in /proc/pid/cmdline (Node.js internal routing).
    """
    import os
    import time

    # Circuit breaker kill leaves a .loop-* file — immediate detection
    if _was_circuit_broken(session_id):
        return False

    session_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    jsonl_path = session_dir / f"{session_id}.jsonl"
    lock_path = session_dir / f"{session_id}.jsonl.lock"

    now = time.time()

    # Check session file modification time (agent writes to it continuously)
    if jsonl_path.exists():
        mtime = os.path.getmtime(jsonl_path)
        if now - mtime < 180:  # Modified in last 3 minutes
            return True

    # Check lock file (created when session starts)
    if lock_path.exists():
        mtime = os.path.getmtime(lock_path)
        if now - mtime < 180:
            return True

    return False


RESTART_COOLDOWN_FILE = "/tmp/openclaw-restart-ts"
RESTART_COOLDOWN_SECONDS = 300
RESTART_PAUSED_FLAG = "/tmp/openclaw-restart-paused"


def _handle_restart_pause(store):
    """On gateway restart, pause all active plans and notify user. Runs once."""
    import time

    if not os.path.exists(RESTART_COOLDOWN_FILE):
        return False

    mtime = os.path.getmtime(RESTART_COOLDOWN_FILE)
    age = time.time() - mtime
    if age > RESTART_COOLDOWN_SECONDS:
        return False  # Cooldown expired

    # Already handled this restart?
    if os.path.exists(RESTART_PAUSED_FLAG):
        flag_mtime = os.path.getmtime(RESTART_PAUSED_FLAG)
        if flag_mtime >= mtime:
            return True  # Already paused for this restart, still in cooldown

    # First check-contracts after restart — pause all active plans
    active_plans = store.list_plans(status="active")
    if not active_plans:
        # No active plans, just mark as handled
        with open(RESTART_PAUSED_FLAG, "w") as f:
            f.write(str(time.time()))
        return True

    paused_summaries = []
    failed_tasks = []
    for p in active_plans:
        full = store.get_plan(p["id"])
        if not full:
            continue
        store.update_plan_status(p["id"], "paused")
        running_steps = [s for s in full.get("steps", []) if s["status"] == "running"]
        # Fail running tasks whose agent process was killed by restart
        for rs in running_steps:
            tid = rs.get("task_id")
            if tid:
                try:
                    store.fail_task(tid, "Gateway restart killed agent process")
                    failed_tasks.append(tid)
                except Exception:
                    pass
        step_info = f" (Step {running_steps[0]['step_num']} running)" if running_steps else ""
        paused_summaries.append(f"• {p['id']} {full['goal'][:50]}{step_info}")

        # Notify each plan's chat
        send_lark(full["chat_id"],
                  f"⏸️ Gateway 重启，计划已自动暂停。\n等待确认后继续。\n\n回复 `resume` 恢复此计划。")

    # Send summary to first plan's chat (or could be a dedicated admin chat)
    if paused_summaries:
        summary = "🔄 Gateway 已重启，以下计划已自动暂停：\n\n" + "\n".join(paused_summaries)
        summary += "\n\n回复 `resume <plan_id>` 恢复指定计划，或 `resume all` 恢复全部。"
        # Send to the first plan's chat as a central notification
        first_plan = store.get_plan(active_plans[0]["id"])
        if first_plan:
            send_lark(first_plan["chat_id"], summary)
        print(f"[planner] Restart detected: paused {len(paused_summaries)} plans")

    with open(RESTART_PAUSED_FLAG, "w") as f:
        f.write(str(time.time()))
    return True


def cmd_check_contracts():
    """Poll event queue and process step/contract completions."""
    store = get_store()

    # Layer 1: Restart cooldown — pause plans and skip processing
    if _handle_restart_pause(store):
        print(json.dumps({"skipped": True, "reason": "restart_cooldown"}))
        return

    events = store.poll_events(limit=20)

    if not events:
        print(json.dumps({"processed": 0}))
        return

    processed = 0
    for evt in events:
        try:
            etype = evt["event_type"]
            task_id = evt.get("task_id")
            plan_id = evt.get("plan_id")
            step_num = evt.get("step_num")
            payload = evt.get("payload") or {}

            # Resolve plan from task_id if not provided
            if task_id and not plan_id:
                plan_id, step_num = _resolve_plan_for_task(store, task_id)

            # step.done or contract.done → mark step done + advance
            if etype in ("step.done", "contract.done") and plan_id and step_num:
                result = payload.get("result", "completed")
                plan = store.get_plan(plan_id)
                if plan:
                    try:
                        cmd_step_done(plan["chat_id"], step_num, result)
                    except SystemExit:
                        pass  # cmd_step_done uses sys.exit on error

            # step.failed or contract.fail → mark step failed (use store directly, no cmd_*)
            elif etype in ("step.failed", "contract.fail") and plan_id and step_num:
                error = payload.get("error", payload.get("result", "unknown error"))
                plan = store.get_plan(plan_id)
                if plan:
                    # Check idempotency
                    existing = store.get_step(plan_id, step_num)
                    if existing and existing.get("status") == "failed":
                        pass  # Already failed, skip
                    else:
                        store.fail_step(plan_id, step_num, error)
                        if existing and existing.get("task_id"):
                            task = store.get_task(existing["task_id"])
                            if task and task.get("status") != "failed":
                                store.fail_task(existing["task_id"], error)
                        # Refresh plan and send ONE notification
                        plan = store.get_plan(plan_id)
                        send_lark(plan["chat_id"], format_plan(plan))
                        _update_dashboard(trigger="step_fail")

            # contract.partial → treat as failure (use store directly, no cmd_*)
            elif etype == "contract.partial" and plan_id and step_num:
                result = payload.get("result", "partial completion")
                succeeded = payload.get("succeeded", 0)
                failed = payload.get("failed", 0)
                error = f"Partial: {result} ({succeeded} ok, {failed} failed)"
                plan = store.get_plan(plan_id)
                if plan:
                    existing = store.get_step(plan_id, step_num)
                    if existing and existing.get("status") == "failed":
                        pass  # Already failed
                    else:
                        store.fail_step(plan_id, step_num, error)
                        if existing and existing.get("task_id"):
                            task = store.get_task(existing["task_id"])
                            if task and task.get("status") != "failed":
                                store.fail_task(existing["task_id"], error)
                        plan = store.get_plan(plan_id)
                        send_lark(plan["chat_id"], format_plan(plan))
                        _update_dashboard(trigger="contract_partial")

            # contract.progress → just ack (informational)
            elif etype == "contract.progress":
                pass  # ack below

            # contract.start → just ack (informational)
            elif etype == "contract.start":
                pass  # ack below

            store.ack_event(evt["id"])
            processed += 1
        except Exception as e:
            print(f"[planner] event processing error: {e}", file=sys.stderr)
            store.ack_event(evt["id"])  # ack anyway to avoid infinite loop

    # Also check for expired drafts (>30 min without confirmation)
    drafts = store.list_plans(status="draft")
    expired_drafts = 0
    for d in drafts:
        created = d.get("created_at")
        if created:
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if created.tzinfo is None:
                created = created.replace(tzinfo=SGT)
            age_min = (datetime.now(SGT) - created.astimezone(SGT)).total_seconds() / 60
            if age_min > 30:
                store.update_plan_status(d["id"], "cancelled")
                full = store.get_plan(d["id"])
                if full:
                    send_lark(full["chat_id"],
                              f"⏰ 计划草稿已超时取消（30分钟未确认）\n\n{full['goal']}")
                expired_drafts += 1

    # Layer 2: Skip test plans in production
    # (Test plans have chat_id starting with "oc_test_")

    # Layer 3: Auto-pause stale plans (no step completed in 24h)
    stale_paused = 0
    active_plans_all = store.list_plans(status="active")
    for p in (active_plans_all or []):
        full = store.get_plan(p["id"])
        if not full:
            continue

        # Layer 2: Skip test plans
        if full.get("chat_id", "").startswith("oc_test_"):
            store.update_plan_status(p["id"], "cancelled")
            print(f"[planner] Cancelled test plan: {p['id']}")
            continue

        # Layer 3: Check staleness — last step completion > 24h ago
        steps = full.get("steps", [])
        last_activity = full.get("created_at")
        for s in steps:
            if s.get("completed_at"):
                completed = s["completed_at"]
                if isinstance(completed, str):
                    completed = datetime.fromisoformat(completed)
                if completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
                if last_activity is None or completed > (
                    last_activity if isinstance(last_activity, datetime)
                    else datetime.fromisoformat(str(last_activity)).replace(tzinfo=timezone.utc)
                ):
                    last_activity = completed
            if s.get("started_at"):
                started = s["started_at"]
                if isinstance(started, str):
                    started = datetime.fromisoformat(started)
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                if last_activity is None or started > (
                    last_activity if isinstance(last_activity, datetime)
                    else datetime.fromisoformat(str(last_activity)).replace(tzinfo=timezone.utc)
                ):
                    last_activity = started

        if last_activity:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            stale_hours = (datetime.now(timezone.utc) - last_activity).total_seconds() / 3600
            if stale_hours > 24:
                # Double-check status (another check-contracts run may have already paused it)
                fresh = store.get_plan(p["id"])
                if fresh and fresh["status"] == "active":
                    store.update_plan_status(p["id"], "paused")
                    send_lark(full["chat_id"],
                              f"⏸️ 计划已自动暂停（超过 24 小时无进展）\n\n{full['goal'][:60]}\n\n回复 `resume` 恢复。")
                    stale_paused += 1
                    print(f"[planner] Stale plan paused: {p['id']} ({stale_hours:.0f}h)")

    # Check for stuck running steps (agent died, session gone)
    stuck_steps = 0
    active_plans = store.list_plans(status="active")
    for p in (active_plans or []):
        full = store.get_plan(p["id"])
        if not full:
            continue
        for step in full.get("steps", []):
            if step.get("status") != "running":
                continue
            # Skip steps whose task is in waiting state (user input pending)
            if step.get("task_id"):
                task = store.get_task(step["task_id"])
                if task and task.get("status") == "waiting":
                    continue
            started = step.get("started_at")
            if not started:
                continue
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            age_min = (datetime.now(timezone.utc) - started).total_seconds() / 60

            should_fail = False
            fail_reason = ""

            if age_min > 45:
                # Hard timeout — always fail
                should_fail = True
                fail_reason = f"Auto-failed: step stuck for {age_min:.0f} minutes (timeout=45min)"
            elif age_min > 2:
                # Soft check — verify agent process is alive
                task_id = step.get("task_id", "")
                task_obj = store.get_task(task_id) if task_id else None
                task_chat = (task_obj or {}).get("task_chat_id", "")
                if task_chat:
                    session_id = f"task-{task_chat[-8:]}"
                    if not _is_agent_process_alive(session_id):
                        should_fail = True
                        circuit = _was_circuit_broken(session_id)
                        fail_reason = f"Auto-failed: {'circuit breaker (tool loop)' if circuit else 'agent process dead'} after {age_min:.0f} minutes"

            if should_fail:
                # Use store directly (not cmd_step_fail) to avoid duplicate notifications
                existing = store.get_step(full["id"], step["step_num"])
                if existing and existing.get("status") == "failed":
                    pass  # Already failed
                else:
                    store.fail_step(full["id"], step["step_num"], fail_reason)
                    if existing and existing.get("task_id"):
                        task = store.get_task(existing["task_id"])
                        if task and task.get("status") != "failed":
                            store.fail_task(existing["task_id"], fail_reason)
                    updated_plan = store.get_plan(full["id"])
                    send_lark(full["chat_id"], format_plan(updated_plan))
                    _update_dashboard(trigger="stuck_step_fail")
                    stuck_steps += 1

    result = {"processed": processed, "total_events": len(events)}
    if expired_drafts:
        result["expired_drafts"] = expired_drafts
    if stuck_steps:
        result["stuck_steps_failed"] = stuck_steps
    if stale_paused:
        result["stale_paused"] = stale_paused
    print(json.dumps(result))



def cmd_list():
    """List all planners (active first)."""
    store = get_store()
    plans = store.list_plans()

    if not plans:
        print("No planners found.")
        return

    # Sort: active first, then completed, then cancelled
    order = {"active": 0, "draft": 0, "completed": 1, "cancelled": 2}
    plans.sort(key=lambda p: (order.get(p.get("status", ""), 9), p.get("created_at", "")))

    for p in plans:
        full = store.get_plan(p["id"])
        if not full:
            continue
        steps = full.get("steps", [])
        status_icon = {"active": "🟢", "completed": "✅", "cancelled": "🚫", "draft": "📝"}.get(p["status"], "❓")
        done = sum(1 for s in steps if s["status"] == "done")
        total = len(steps)
        running = [s for s in steps if s["status"] == "running"]
        running_info = f" | running: Step {running[0]['step_num']}" if running else ""
        print(f"{status_icon} {p['id']} [{chat_id_short(p.get('chat_id', ''))}] {p['goal']} ({done}/{total}){running_info}")



def cmd_find_by_task(task_id: str):
    """Find which planner and step a task_id belongs to."""
    store = get_store()
    conn = store.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT ps.plan_id, ps.step_num, ps.title, ps.status, ps.result,
               p.chat_id, p.goal, p.status as plan_status
        FROM plan_steps ps
        JOIN plans p ON p.id = ps.plan_id
        WHERE ps.task_id = %s
    """, (task_id,))
    row = cur.fetchone()
    if not row:
        print(json.dumps({"found": False}))
        return

    cols = [d[0] for d in cur.description]
    data = dict(zip(cols, row))

    # Check for next pending step
    next_step = store.next_pending_step(data["plan_id"])
    result = {
        "found": True,
        "chat_id": data["chat_id"],
        "goal": data["goal"],
        "planner_status": data["plan_status"],
        "step": {"id": data["step_num"], "desc": data["title"], "status": data["status"]},
        "advance": next_step is not None and data["status"] == "done",
    }
    if next_step:
        result["next_step"] = {
            "id": next_step["step_num"],
            "desc": next_step["title"],
            "detail": next_step.get("prompt", ""),
        }
    print(json.dumps(result, ensure_ascii=False))


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

    if cmd in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)
    elif cmd == "init":
        if "--template" in sys.argv:
            tidx = sys.argv.index("--template")
            tname = sys.argv[tidx + 1] if tidx + 1 < len(sys.argv) else None
            chat_id = sys.argv[2] if len(sys.argv) > 2 else None
            # Parse --var key=value pairs
            tvars = {}
            for a in sys.argv:
                if a.startswith("--var=") or (a == "--var"):
                    pass
            i = 0
            while i < len(sys.argv):
                if sys.argv[i] == "--var" and i + 1 < len(sys.argv):
                    k, _, v = sys.argv[i + 1].partition("=")
                    tvars[k] = v
                    i += 2
                else:
                    i += 1
            if not chat_id or not tname:
                print("Usage: planner.py init <chat_id> --template <name> [--var key=value ...]", file=sys.stderr)
                sys.exit(1)
            cmd_init(chat_id, "", "", template_name=tname, template_vars=tvars)
        elif len(sys.argv) < 5:
            print("Usage: planner.py init <chat_id> <goal> <steps_json>", file=sys.stderr)
            sys.exit(1)
        else:
            cmd_init(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd == "start":
        if len(sys.argv) < 3:
            print("Usage: planner.py start <chat_id>", file=sys.stderr)
            sys.exit(1)
        cmd_start(sys.argv[2])

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("Usage: planner.py show <chat_id> [--graph]", file=sys.stderr)
            sys.exit(1)
        send_graph = "--graph" in sys.argv
        cmd_show(sys.argv[2], send_graph=send_graph)

    elif cmd == "step-done":
        if len(sys.argv) < 5:
            print("Usage: planner.py step-done <chat_id> <step_id> \"<result>\"", file=sys.stderr)
            sys.exit(1)
        sid = int(sys.argv[3])
        cmd_step_done(sys.argv[2], sid, sys.argv[4])

    elif cmd == "step-fail":
        if len(sys.argv) < 5:
            print("Usage: planner.py step-fail <chat_id> <step_id> \"<error>\"", file=sys.stderr)
            sys.exit(1)
        sid = int(sys.argv[3])
        cmd_step_fail(sys.argv[2], sid, sys.argv[4])

    elif cmd == "replan":
        if len(sys.argv) < 4:
            print("Usage: planner.py replan <chat_id> <new_steps_json> [--append]", file=sys.stderr)
            sys.exit(1)
        append_mode = "--append" in sys.argv
        cmd_replan(sys.argv[2], sys.argv[3], append=append_mode)

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

    elif cmd == "pause":
        if len(sys.argv) < 3:
            print("Usage: planner.py pause <chat_id>", file=sys.stderr)
            sys.exit(1)
        cmd_pause(sys.argv[2])
    elif cmd == "resume":
        if len(sys.argv) < 3:
            print("Usage: planner.py resume <plan_id|chat_id|all>", file=sys.stderr)
            sys.exit(1)
        cmd_resume(sys.argv[2])
    elif cmd == "check-contracts":
        cmd_check_contracts()

    elif cmd == "templates":
        templates = list_templates()
        if not templates:
            print("No templates found.")
        else:
            for t in templates:
                vars_str = ", ".join(t["variables"]) if t["variables"] else "none"
                print(f"  {t['name']:20} {t['steps']} steps  vars: {vars_str}  — {t['description']}")

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
