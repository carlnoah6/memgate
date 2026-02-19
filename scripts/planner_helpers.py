"""Planner helper functions — utilities, formatting, Lark messaging."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from task_store import TaskStore

SGT = timezone(timedelta(hours=8))
from openclaw_config import get_workspace
BASE = get_workspace()
LARK_SEND = BASE / "scripts" / "lark-send-message.sh"
DRY_RUN = False

_store = None
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def get_store() -> TaskStore:
    global _store
    if _store is None:
        _store = TaskStore()
    return _store


# === Helpers ===


def now_iso():
    return datetime.now(SGT).isoformat()



def chat_id_short(chat_id: str) -> str:
    """Last 8 chars of chat_id for display."""
    return chat_id[-8:] if len(chat_id) > 8 else chat_id



def resolve_chat_id(chat_id_or_msgid: str) -> str:
    """Resolve chat_id from direct ID or Lark message_id (om_...)."""
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



def resolve_full_chat_id(short_id: str) -> str:
    """Expand short chat_id to full oc_ format if needed."""
    if short_id.startswith("oc_"):
        return short_id
    store = get_store()
    plan = store.get_plan_by_chat(short_id, status_filter='active')
    if plan:
        return plan["chat_id"]
    return short_id



def normalize_step(raw: dict) -> dict:
    """Normalize step input to {title, prompt, depends_on} format."""
    title = raw.get("title") or raw.get("desc") or raw.get("name") or "Untitled"
    prompt = raw.get("prompt") or raw.get("detail") or ""
    depends_on = raw.get("depends_on") or []
    if isinstance(depends_on, int):
        depends_on = [depends_on]
    return {"title": title, "prompt": prompt, "depends_on": depends_on}




TEMPLATE_DIR = Path(__file__).parent / "templates"



def send_lark(chat_id: str, message: str) -> bool:
    """Send a text message to a Lark chat."""
    if DRY_RUN:
        print(f"[dry-run] lark-send: {chat_id} → {message[:80]}...", file=sys.stderr)
        return True
    try:
        full_chat_id = resolve_full_chat_id(chat_id)
        result = subprocess.run(
            ["bash", str(LARK_SEND), full_chat_id, message],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            print(f"[planner] lark-send failed: {result.stderr.strip()}", file=sys.stderr)
            return False
        print(f"[planner] lark-send success: {full_chat_id[:20]}...", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[planner] lark-send error: {e}", file=sys.stderr)
        return False


# === Display ===



def _format_duration(start, end=None):
    """Format duration between two timestamps."""
    if not start:
        return ""
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if end:
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
    else:
        end = datetime.now(SGT)
    if start.tzinfo is None:
        start = start.replace(tzinfo=SGT)
    if end.tzinfo is None:
        end = end.replace(tzinfo=SGT)
    delta = end - start
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    hours = secs / 3600
    return f"{hours:.1f}h"



def _short_desc(text: str, max_len: int = 60) -> str:
    """Truncate text for display."""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:max_len] + "..." if len(text) > max_len else text


# === Lark Messaging ===


def _build_plan_summary(plan: dict) -> str:
    """Build a summary message for a completed plan with cost/time breakdown."""
    steps = plan.get("steps", [])
    done_steps = [s for s in steps if s["status"] == "done"]
    if not done_steps:
        return ""

    store = get_store()

    # Calculate plan total duration
    plan_start = plan.get("created_at")
    plan_end = max((s.get("completed_at") for s in done_steps if s.get("completed_at")), default=None)
    plan_dur = _format_duration(plan_start, plan_end) if plan_start and plan_end else ""

    # Gather cost data per step
    total_input = 0
    total_output = 0
    total_cost = 0.0
    step_costs = []
    for s in done_steps:
        tid = s.get("task_id")
        inp, out, cost = 0, 0, 0.0
        if tid:
            task = store.get_task(tid)
            if task:
                inp = task.get("input_tokens", 0) or 0
                out = task.get("output_tokens", 0) or 0
                cost = float(task.get("cost_usd", 0) or 0)
        total_input += inp
        total_output += out
        total_cost += cost
        step_costs.append((s, inp, out, cost))

    # Build summary
    lines = [f"📊 规划完成: {plan.get('goal', '')}"]
    if plan_dur:
        lines[0] += f"  ⏱ 总用时 {plan_dur}"
    if total_cost > 0:
        lines[0] += f"  💰 ${total_cost:.4f}"
    lines.append("")

    for s, inp, out, cost in step_costs:
        dur = _format_duration(s.get("started_at"), s.get("completed_at"))
        dur_str = f"⏱{dur}" if dur else ""
        tokens_str = f"{(inp+out):,} tok" if (inp + out) > 0 else ""
        pct = f"({cost/total_cost*100:.0f}%)" if total_cost > 0 and cost > 0 else ""
        cost_str = f"${cost:.4f} {pct}" if cost > 0 else ""

        parts = [f"  {s['step_num']}. {s.get('title', '')}"]
        detail = " | ".join(filter(None, [dur_str, tokens_str, cost_str]))
        if detail:
            parts.append(f"    {detail}")
        result = _short_desc(s.get("result", ""), 150)
        if result:
            parts.append(f"    → {result}")
        lines.extend(parts)

    # Totals
    if total_cost > 0 or total_input > 0:
        lines.append("")
        lines.append(f"  合计: {total_input:,} input + {total_output:,} output = {(total_input+total_output):,} tokens | ${total_cost:.4f}")

    return "\n".join(lines)



def format_plan(plan: dict) -> str:
    """Format plan for display (Lark message)."""
    status_label = {"active": "", "completed": " [COMPLETED]", "cancelled": " [CANCELLED]",
                    "draft": " [DRAFT]"}.get(plan["status"], "")
    lines = [f"📋 {plan["id"]} — {plan["goal"]}{status_label}\n"]

    for s in plan.get("steps", []):
        num = s.get("step_num", 0)
        title = s.get("title", "")
        st = s.get("status", "pending")

        if st == "done":
            dur = _format_duration(s.get("started_at"), s.get("completed_at"))
            dur_str = f" ⏱{dur}" if dur else ""
            result = _short_desc(s.get("result", ""), 60)
            lines.append(f"✅ {num}. {title} {s.get('task_id', '')}{dur_str} — {result}")
        elif st == "running":
            dur = _format_duration(s.get("started_at"))
            dur_str = f" ⏱{dur}" if dur else ""
            lines.append(f"🔄 {num}. {title} {s.get('task_id', '')}{dur_str}")
        elif st == "failed":
            result = _short_desc(s.get("result", ""), 60)
            lines.append(f"❌ {num}. {title} {s.get('task_id', '')} — {result}")
        elif st == "cancelled":
            lines.append(f"🚫 {num}. {title}")
        else:
            deps = s.get("depends_on") or []
            dep_str = f" (after {','.join(str(d) for d in deps)})" if deps else ""
            lines.append(f"⬜ {num}. {title}{dep_str}")

    return "\n".join(lines)


# === Dependency Graph ===


def send_plan_graph(plan: dict, chat_id: str = None):
    """Generate a timeline graph for a plan and send it to the chat.
    
    Reads step statuses, tids, and durations from the plan dict,
    renders a PNG timeline, uploads to Lark, and sends as image message.
    """
    if DRY_RUN:
        print("[dry-run] skip send_plan_graph", file=sys.stderr)
        return

    target_chat = chat_id or plan.get("chat_id", "")
    if not target_chat:
        return

    steps_data = []
    for s in plan.get("steps", []):
        num = s.get("step_num", 0)
        st = s.get("status", "pending")
        
        step_entry = {
            "id": num,
            "title": s.get("title", f"Step {num}"),
            "deps": s.get("depends_on") or [],
            "status": st,
        }
        
        # Add tid if assigned
        tid = s.get("task_id", "")
        if tid:
            step_entry["tid"] = tid
        
        # Add duration for running tasks
        if st == "running" and s.get("started_at"):
            dur = _format_duration(s["started_at"])
            if dur:
                step_entry["duration"] = dur
        
        steps_data.append(step_entry)

    if not steps_data:
        return

    try:
        from plan_timeline import generate_html, render_png
        from lark_common import upload_image, send_image_message
        import tempfile

        goal = plan.get("goal", "Plan")[:80]
        status_label = {"active": "", "completed": " ✅", "cancelled": " 🚫",
                        "draft": " [Draft]", "paused": " ⏸️"}.get(plan.get("status", ""), "")
        title = f"📋 {goal}{status_label}"

        html = generate_html(steps_data, title)
        out_dir = tempfile.mkdtemp(prefix="plan-graph-")
        png_path = os.path.join(out_dir, "timeline.png")
        render_png(html, png_path)

        image_key = upload_image(png_path)
        send_image_message(target_chat, image_key)

        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
    except Exception as e:
        print(f"[planner] send_plan_graph failed: {e}", file=sys.stderr)


# === Spawn Logic ===


