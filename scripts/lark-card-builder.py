#!/usr/bin/env python3
"""Luna OS - Lark 看板卡片构建器

Builds a Lark Interactive Card for the task dashboard.
Supports two modes:
  - Global mode (no --chat-id): shows running/queued tasks + session overview
  - Plan mode (--chat-id <id>): shows the plan for that specific group chat

Usage:
  python3 lark-card-builder.py                          # global dashboard
  python3 lark-card-builder.py --chat-id oc_xxx         # plan for group
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_store import TaskStore, PRIORITY_ICONS, SGT

SESSION_OVERVIEW = "/home/ubuntu/.openclaw/workspace/data/session-overview.json"
SESSION_SCRIPT = "/home/ubuntu/.openclaw/workspace/scripts/session-overview.py"


def fmt_duration(minutes):
    if minutes < 1:
        return "<1min"
    if minutes < 60:
        return f"{minutes:.0f}min"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h"
    days = hours / 24
    return f"{days:.1f}d"


def fmt_tokens(tokens):
    if tokens >= 1000000:
        return f"{tokens / 1000000:.1f}M"
    if tokens >= 1000:
        return f"{tokens / 1000:.0f}K"
    return str(tokens)


def _col(text, weight=1):
    return {
        "tag": "column",
        "width": "weighted",
        "weight": weight,
        "vertical_align": "top",
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
    }


STATUS_EMOJI = {
    "done": "✅",
    "running": "🔄",
    "pending": "⏳",
    "failed": "❌",
    "cancelled": "🚫",
    "waiting": "⏸️",
}

PLAN_STATUS_TEMPLATE = {
    "active": ("blue", "🟢 进行中"),
    "completed": ("green", "✅ 已完成"),
    "cancelled": ("grey", "🚫 已取消"),
    "draft": ("yellow", "📝 草稿"),
    "paused": ("orange", "⏸️ 已暂停"),
}


def build_plan_card(chat_id: str) -> dict:
    """Build a plan-focused card for a specific group chat."""
    from planner_helpers import get_store as get_plan_store
    plan_store = get_plan_store()

    # Find the most recent plan for this chat (any status)
    all_plans_raw = plan_store.list_plans()
    all_plans = [p.to_dict() if hasattr(p, 'to_dict') else p for p in all_plans_raw]
    chat_plans = [p for p in all_plans if p.get("chat_id") == chat_id]
    # Sort by most recently updated first
    chat_plans.sort(key=lambda p: p.get("updated_at") or p.get("created_at") or "", reverse=True)

    now = datetime.now(SGT)
    elements = []

    if not chat_plans:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "📋 **当前群聊无规划任务**\n\n使用 planner 创建新的规划。"}
        })
        return _wrap_card("📋 规划仪表盘", "grey", elements, now)

    plan = chat_plans[0]
    steps = plan.get("steps", [])
    total = len(steps)
    done_count = sum(1 for s in steps if s.get("status") == "done")
    running_count = sum(1 for s in steps if s.get("status") == "running")
    failed_count = sum(1 for s in steps if s.get("status") == "failed")

    template_color, status_text = PLAN_STATUS_TEMPLATE.get(plan["status"], ("grey", plan["status"]))

    # Plan header
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**📋 {plan['goal']}**"}
    })
    elements.append({
        "tag": "div",
        "fields": [
            {"is_short": True, "text": {"tag": "lark_md", "content": f"**状态** {status_text}"}},
            {"is_short": True, "text": {"tag": "lark_md", "content": f"**进度** {done_count}/{total}"}},
        ]
    })

    if running_count > 0 or failed_count > 0:
        extra_fields = []
        if running_count:
            extra_fields.append({"is_short": True, "text": {"tag": "lark_md", "content": f"**🔄 运行中** {running_count}"}})
        if failed_count:
            extra_fields.append({"is_short": True, "text": {"tag": "lark_md", "content": f"**❌ 失败** {failed_count}"}})
        elements.append({"tag": "div", "fields": extra_fields})

    elements.append({"tag": "hr"})

    # Steps list
    for s in steps:
        num = s.get("step_num", 0)
        title = s.get("title", f"Step {num}")
        status = s.get("status", "pending")
        emoji = STATUS_EMOJI.get(status, "⬜")
        tid = s.get("task_id", "")

        line = f"{emoji} **S{num}.** {title}"
        if tid:
            line += f"  `{tid}`"

        # Duration for running/done
        if status == "running" and s.get("started_at"):
            started = s["started_at"]
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            if started.tzinfo is None:
                started = started.replace(tzinfo=SGT)
            mins = (now - started.astimezone(SGT)).total_seconds() / 60
            line += f"  ⏱{fmt_duration(mins)}"

        # Result snippet for done steps
        if status == "done" and s.get("result"):
            result = s["result"][:60]
            line += f"\n    _{result}_"

        # Deps
        deps = s.get("depends_on") or []
        if deps and status == "pending":
            line += f"  (等待 S{', S'.join(str(d) for d in deps)})"

        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": line}
        })

    elements.append({"tag": "hr"})

    # Show other plans for this chat if any
    other_plans = [p for p in chat_plans[1:] if p["status"] in ("active", "paused", "draft")]
    if other_plans:
        other_lines = ["**其他规划**"]
        for p in other_plans[:3]:
            _, st = PLAN_STATUS_TEMPLATE.get(p["status"], ("grey", p["status"]))
            other_lines.append(f"  {st} {p['goal'][:40]}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(other_lines)}
        })
        elements.append({"tag": "hr"})

    return _wrap_card(f"📋 {plan['goal'][:30]}", template_color, elements, now)


def build_global_card() -> dict:
    """Build the global task dashboard card."""
    # Refresh session overview
    try:
        subprocess.run(["python3", SESSION_SCRIPT], capture_output=True, text=True, timeout=10)
    except Exception:
        pass

    store = TaskStore()
    tasks_raw = store.list_tasks()
    tasks = [t.to_dict() if hasattr(t, 'to_dict') else t for t in tasks_raw]
    now = datetime.now(SGT)

    running_tasks = [t for t in tasks if t["status"] == "running"]
    max_concurrent = 8
    queued_tasks = [t for t in tasks if t["status"] == "queued"]

    elements = []

    # Stats
    elements.append({
        "tag": "div",
        "fields": [
            {"is_short": True, "text": {"tag": "lark_md", "content": f"**🏃 运行中** {len(running_tasks)}/{max_concurrent}"}},
            {"is_short": True, "text": {"tag": "lark_md", "content": f"**⏳ 等待中** {len(queued_tasks)}"}},
        ]
    })
    elements.append({"tag": "hr"})

    # Running tasks
    if running_tasks:
        running_lines = ["**🏃 运行中任务**"]
        for t in running_tasks:
            icon = PRIORITY_ICONS.get(t.get("priority", "normal"), "🟢")
            elapsed = ""
            if t.get("started_at"):
                started = t["started_at"]
                if isinstance(started, str):
                    started = datetime.fromisoformat(started)
                if started.tzinfo is None:
                    started = started.replace(tzinfo=SGT)
                mins = (now - started.astimezone(SGT)).total_seconds() / 60
                elapsed = f" ⏱{fmt_duration(mins)}"
            desc = t["description"][:50]
            running_lines.append(f"{icon} `{t['id']}` {desc}{elapsed}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(running_lines)}
        })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🏃 运行中任务** — 无"}
        })

    elements.append({"tag": "hr"})

    # Queued tasks
    if queued_tasks:
        queued_lines = ["**⏳ 等待中任务**"]
        for t in queued_tasks[:5]:
            icon = PRIORITY_ICONS.get(t.get("priority", "normal"), "🟢")
            deps = t.get("depends_on") or []
            dep_str = f" (等待 {','.join(deps)})" if deps else ""
            desc = t["description"][:50]
            queued_lines.append(f"{icon} `{t['id']}` {desc}{dep_str}")
        if len(queued_tasks) > 5:
            queued_lines.append(f"... 还有 {len(queued_tasks) - 5} 个")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(queued_lines)}
        })

    elements.append({"tag": "hr"})

    # Session overview
    session_elements = build_session_section()
    if session_elements:
        elements.extend(session_elements)
        elements.append({"tag": "hr"})

    return _wrap_card("🖥️ Luna 任务仪表盘", "blue", elements, now)


def build_session_section():
    """Build session overview section."""
    elements = []

    if not os.path.exists(SESSION_OVERVIEW):
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "📊 **Session 概览** — 暂无数据"}
        })
        return elements

    try:
        with open(SESSION_OVERVIEW) as f:
            overview = json.load(f)
    except Exception:
        return elements

    sessions = overview.get("sessions", [])
    if not sessions:
        return elements

    # Header row
    elements.append({
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "grey",
        "columns": [
            _col("**Session**", 3),
            _col("**状态**", 2),
            _col("**Tokens**", 2),
            _col("**时长**", 1),
        ]
    })

    for s in sessions[:8]:
        name = s.get("name", "?")[:20]
        planner = s.get("planner")
        if planner and planner.get("goal"):
            goal = planner["goal"][:30]
            name_cell = f"{name}\n📋 {goal}"
        else:
            name_cell = name
        activity = s.get("last_activity") or "—"
        if planner and planner.get("status_text"):
            status = planner["status_text"]
        else:
            status = activity
        tok = s.get("tokens", 0)
        pct = s.get("usage_pct", 0)
        tokens_str = f"{fmt_tokens(tok)} ({pct}%)" if tok else "0"
        age = s.get("relative_time", "?")
        elements.append({
            "tag": "column_set",
            "flex_mode": "none",
            "columns": [
                _col(name_cell, 3),
                _col(status, 2),
                _col(tokens_str, 2),
                _col(age, 1),
            ]
        })

    return elements


def _wrap_card(title: str, template: str, elements: list, now: datetime) -> dict:
    """Wrap elements in a card with header, footer, and refresh button."""
    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": f"🕐 最后更新: {now.strftime('%Y-%m-%d %H:%M:%S')} SGT"}
        ]
    })
    elements.append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🔄 刷新"},
            "type": "primary",
            "value": {"action": "refresh_dashboard"}
        }]
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }


def build_card(chat_id=None) -> dict:
    """Build the appropriate card based on context."""
    if chat_id:
        return build_plan_card(chat_id)
    return build_global_card()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)

    chat_id = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--chat-id" and i + 1 < len(sys.argv[1:]):
            chat_id = sys.argv[i + 2]
            break

    card = build_card(chat_id=chat_id)
    print(json.dumps(card, ensure_ascii=False))
