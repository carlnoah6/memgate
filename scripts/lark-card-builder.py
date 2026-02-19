#!/usr/bin/env python3
"""Luna OS - Lark 看板卡片构建器

Reads task data from PostgreSQL (via TaskStore), generates Lark Interactive Card JSON.
Output to stdout for lark-task-dashboard.py.

Usage: python3 lark-card-builder.py
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

    # Header
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
        # Build name cell: session name + planner goal on second line
        planner = s.get("planner")
        if planner and planner.get("goal"):
            goal = planner["goal"][:30]
            name_cell = f"{name}\n📋 {goal}"
        else:
            name_cell = name
        # Status: planner status_text or last_activity
        activity = s.get("last_activity") or "—"
        if planner and planner.get("status_text"):
            status = planner["status_text"]
        else:
            status = activity
        # Tokens with usage %
        tok = s.get("tokens", 0)
        pct = s.get("usage_pct", 0)
        tokens_str = f"{fmt_tokens(tok)} ({pct}%)" if tok else "0"
        # Age
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


def build_card() -> dict:
    """Build task dashboard card from PostgreSQL data."""
    # Refresh session overview before building card
    try:
        subprocess.run(
            ["python3", SESSION_SCRIPT],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pass
    store = TaskStore()
    tasks = store.list_tasks()
    now = datetime.now(SGT)
    today = now.strftime("%Y-%m-%d")

    running_tasks = [t for t in tasks if t["status"] == "running"]
    max_concurrent = 8  # matches task_manager.MAX_CONCURRENT
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

    # Footer
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
            "title": {"tag": "plain_text", "content": "🖥️ Luna 任务仪表盘"},
            "template": "blue"
        },
        "elements": elements
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)
    card = build_card()
    print(json.dumps(card, ensure_ascii=False))
