#!/usr/bin/env python3
"""Luna OS - Lark 看板卡片构建器

读取 task-board.json + session-overview.json，生成 Lark Interactive Card JSON (v1 格式)。
输出到 stdout，供 lark-task-dashboard.py 调用。

Usage: python3 lark-card-builder.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"
SESSION_OVERVIEW = "/home/ubuntu/.openclaw/workspace/data/session-overview.json"
SESSION_SCRIPT = "/home/ubuntu/.openclaw/workspace/scripts/session-overview.py"

PRIORITY_ICONS = {"critical": "🔴", "high": "🟡", "normal": "🟢", "low": "🔵"}


def load_board():
    if os.path.exists(TASK_BOARD):
        with open(TASK_BOARD) as f:
            board = json.load(f)
    else:
        board = {"tasks": [], "next_id": 1}
    for t in board.get("tasks", []):
        t.setdefault("priority", "normal")
        t.setdefault("priority_value", 2)
        t.setdefault("priority_boosted", False)
        t.setdefault("queued_heartbeats", 0)
    return board


def fmt_duration(minutes):
    """Format minutes into human-readable duration."""
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
    """Format token count into human-readable string."""
    if tokens >= 1000000:
        return f"{tokens / 1000000:.1f}M"
    if tokens >= 1000:
        return f"{tokens / 1000:.0f}K"
    return str(tokens)


def _col(text, weight=1):
    """Helper: create a column element for column_set."""
    return {
        "tag": "column",
        "width": "weighted",
        "weight": weight,
        "vertical_align": "top",
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
    }


def build_session_section():
    """Build session overview section using column_set table layout."""
    elements = []

    if not os.path.exists(SESSION_OVERVIEW):
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🧠 Session 概览**\n📡 数据加载中..."}
        })
        return elements

    try:
        with open(SESSION_OVERVIEW) as f:
            data = json.load(f)
    except Exception:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🧠 Session 概览**\n⚠️ 数据读取失败"}
        })
        return elements

    sessions = data.get("sessions", [])
    subagent_count = data.get("subagent_count", 0)

    if not sessions:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🧠 Session 概览**\n💤 无活跃 session"}
        })
        return elements

    # Section title
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md",
                 "content": f"**🧠 Session 概览** ({len(sessions)} 聊天 | {subagent_count} 子任务)"}
    })

    # Table header
    elements.append({
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "grey",
        "columns": [
            _col("**群名**", 3),
            _col("**Tokens**", 2),
            _col("**活跃 · 摘要**", 3),
        ],
    })

    # Data rows
    for s in sessions:
        pct = s["usage_pct"]
        if pct >= 80:
            dot = "🔴"
        elif pct >= 50:
            dot = "🟡"
        else:
            dot = "🟢"

        name = s["name"]
        tokens_str = fmt_tokens(s["tokens"])
        compact_tag = f" 🧹{s['compactions']}" if s.get("compactions", 0) > 0 else ""
        last_act = s.get("last_activity", "—")
        rel_time = s["relative_time"]

        # Combine relative time + short activity
        if last_act and last_act != "—":
            time_act = f"{rel_time} · {last_act}"
        else:
            time_act = rel_time

        elements.append({
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                _col(f"{dot} {name}", 3),
                _col(f"{tokens_str} ({pct}%){compact_tag}", 2),
                _col(time_act, 3),
            ],
        })

    return elements


def build_card():
    # Refresh session overview data first
    try:
        subprocess.run(
            ["python3", SESSION_SCRIPT],
            capture_output=True, text=True, timeout=30
        )
    except Exception:
        pass

    board = load_board()
    now = datetime.now(SGT)
    today = now.strftime("%Y-%m-%d")
    tasks = board.get("tasks", [])

    # Categorize
    running = [t for t in tasks if t["status"] == "running"]
    queued = [t for t in tasks if t["status"] == "queued"]
    done_today = [t for t in tasks if t["status"] == "done" and (t.get("completed") or "").startswith(today)]
    failed_today = [t for t in tasks if t["status"] == "failed" and (t.get("completed") or "").startswith(today)]

    # Sort queued by priority_value DESC, created ASC
    queued.sort(key=lambda t: (-t.get("priority_value", 2), t.get("created", "")))

    done_ids = {t["id"] for t in tasks if t["status"] == "done"}

    elements = []

    # === Running Section ===
    if running:
        lines = [f"**🏃 运行中 ({len(running)})**"]
        for t in running:
            pri = t.get("priority", "normal")
            pri_icon = PRIORITY_ICONS.get(pri, "🟢")
            elapsed = ""
            if t.get("started"):
                try:
                    started = t["started"]
                    if started.endswith("Z"):
                        started = started[:-1] + "+00:00"
                    start_dt = datetime.fromisoformat(started)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=SGT)
                    mins = (now - start_dt).total_seconds() / 60
                    elapsed = f" ⏱ {fmt_duration(mins)}"
                except Exception:
                    pass
            desc = t["description"]
            if len(desc) > 40:
                desc = desc[:40] + "…"
            lines.append(f"{pri_icon} `{t['id']}` {desc}{elapsed}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines)}
        })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🏃 运行中 (0)**\n💤 无运行中的任务"}
        })

    elements.append({"tag": "hr"})

    # === Queued Section ===
    if queued:
        lines = [f"**⏳ 排队中 ({len(queued)})**"]
        for t in queued:
            pri = t.get("priority", "normal")
            pri_icon = PRIORITY_ICONS.get(pri, "🟢")
            wait = ""
            if t.get("created"):
                try:
                    created = t["created"]
                    if created.endswith("Z"):
                        created = created[:-1] + "+00:00"
                    created_dt = datetime.fromisoformat(created)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=SGT)
                    mins = (now - created_dt).total_seconds() / 60
                    wait = f" ⏱ 等待{fmt_duration(mins)}"
                except Exception:
                    pass

            # Check if blocked
            deps = t.get("depends_on", [])
            unmet = [d for d in deps if d not in done_ids]
            blocked = f" 🔒 等待 {','.join(unmet)}" if unmet else ""

            boosted = " ⬆️" if t.get("priority_boosted") else ""

            desc = t["description"]
            if len(desc) > 40:
                desc = desc[:40] + "…"
            lines.append(f"{pri_icon}{boosted} `{t['id']}` {desc}{wait}{blocked}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines)}
        })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**⏳ 排队中 (0)**\n💤 无排队任务"}
        })

    elements.append({"tag": "hr"})

    # === Session Overview Section ===
    session_elements = build_session_section()
    elements.extend(session_elements)

    elements.append({"tag": "hr"})

    # === Stats ===
    total_active = len(running) + len(queued)
    stats = (
        f"📊 **今日统计**  "
        f"✅ 完成 {len(done_today)}  |  "
        f"❌ 失败 {len(failed_today)}  |  "
        f"📋 活跃 {total_active}"
    )
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": stats}
    })

    elements.append({"tag": "hr"})

    # === Footer: last updated + refresh button ===
    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": f"🕐 最后更新: {now.strftime('%Y-%m-%d %H:%M:%S')} SGT"}
        ]
    })

    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🔄 刷新"},
                "type": "primary",
                "value": {"action": "refresh_dashboard"}
            }
        ]
    })

    # === Build card ===
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🖥️ Luna 任务面板"},
            "template": "blue"
        },
        "elements": elements
    }

    return card


if __name__ == "__main__":
    card = build_card()
    print(json.dumps(card, ensure_ascii=False))
