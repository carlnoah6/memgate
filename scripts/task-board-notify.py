#!/usr/bin/env python3
"""Luna OS - 任务板状态推送

定期将任务板状态推送到 Lark「Luna 任务板」群聊。
心跳调用，仅当状态有变化时才发送更新。

Usage: python3 scripts/task-board-notify.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token as _get_tenant_token, send_message as _lark_send

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"
STATE_FILE = "/home/ubuntu/.openclaw/workspace/data/task-board-notify-state.json"
CHAT_ID = "oc_630995d9b870d2ff6ab3fa34a4e7315a"
SEND_SCRIPT = "/home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh"


def send_message(text):
    try:
        _lark_send(CHAT_ID, text)
        return True
    except Exception:
        return False


def load_board():
    if os.path.exists(TASK_BOARD):
        with open(TASK_BOARD) as f:
            return json.load(f)
    return {"tasks": [], "next_id": 1}


def load_last_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False)


def build_snapshot(board):
    """Build a hashable snapshot of current task statuses"""
    return {t["id"]: t["status"] for t in board["tasks"] if t["status"] in ("queued", "running", "done", "failed")}


def format_status(board):
    now = datetime.now(SGT)
    tasks = board["tasks"]
    
    running = [t for t in tasks if t["status"] == "running"]
    queued = [t for t in tasks if t["status"] == "queued"]
    
    today = now.strftime("%Y-%m-%d")
    done_today = [t for t in tasks if t["status"] == "done" and (t.get("completed") or "").startswith(today)]
    failed_today = [t for t in tasks if t["status"] == "failed" and (t.get("completed") or "").startswith(today)]
    
    lines = [f"📋 任务板更新 — {now.strftime('%H:%M')}", ""]
    
    if running or queued:
        lines.append(f"🔄 进行中 ({len(running) + len(queued)}):")
        for t in running:
            elapsed = ""
            if t.get("started"):
                mins = (now - datetime.fromisoformat(t["started"])).total_seconds() / 60
                elapsed = f" ({mins:.0f}min)"
            lines.append(f"  🏃 {t['id']} {t['description']}{elapsed}")
        for t in queued:
            deps = t.get("depends_on", [])
            done_ids = {tt["id"] for tt in tasks if tt["status"] == "done"}
            unmet = [d for d in deps if d not in done_ids]
            if unmet:
                lines.append(f"  🔒 {t['id']} {t['description']} [等 {','.join(unmet)}]")
            else:
                lines.append(f"  ⏳ {t['id']} {t['description']}")
        lines.append("")
    
    if done_today:
        lines.append(f"✅ 今日完成 ({len(done_today)}):")
        for t in done_today:
            summary = t.get("result", "")
            if summary and len(summary) > 50:
                summary = summary[:50] + "..."
            lines.append(f"  • {t['id']} {t['description']}")
            if summary:
                lines.append(f"    → {summary}")
        lines.append("")
    
    if failed_today:
        lines.append(f"❌ 今日失败 ({len(failed_today)}):")
        for t in failed_today:
            lines.append(f"  • {t['id']} {t['description']}")
        lines.append("")
    
    if not running and not queued and not done_today and not failed_today:
        lines.append("💤 无活跃任务")
    
    return "\n".join(lines)


def main():
    board = load_board()
    current = build_snapshot(board)
    last = load_last_state()
    
    # Only send if something changed
    if current == last.get("snapshot"):
        print(json.dumps({"changed": False}))
        return
    
    msg = format_status(board)
    success = send_message(msg)
    
    if success:
        save_state({"snapshot": current, "last_sent": datetime.now(SGT).isoformat()})
        print(json.dumps({"changed": True, "sent": True}))
    else:
        print(json.dumps({"changed": True, "sent": False, "error": "send failed"}))


if __name__ == "__main__":
    main()
