#!/usr/bin/env python3
"""Luna OS - Lark Task Board Card

生成并发送/更新任务看板交互式卡片到 Lark 群聊。

Usage:
  lark-task-card.py send <chat_id>       — 发送新卡片，输出 message_id
  lark-task-card.py update <message_id>  — 更新已有卡片
  lark-task-card.py auto <chat_id>       — 有缓存则更新，否则发送新卡片
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_engine import TaskEngine, SGT, PRIORITY_ICONS
from lark_common import get_tenant_token, BASE_URL

BASE = Path("/home/ubuntu/.openclaw/workspace")
CARD_STATE = BASE / "data" / "task-card-state.json"

engine = TaskEngine()


def build_card() -> dict:
    """构建任务看板卡片 JSON（v1 格式）"""
    board = engine.load_board()
    tasks = board.get("tasks", [])
    now = datetime.now(SGT)
    today = now.strftime("%Y-%m-%d")

    # Stats
    running_tasks = [t for t in tasks if t["status"] == "running"]
    queued_tasks = [t for t in tasks if t["status"] == "queued"]
    done_today = [t for t in tasks if t["status"] == "done" and (t.get("completed") or "").startswith(today)]

    # Enrich running tasks
    enriched_running = [engine._enrich_task(t) for t in running_tasks]

    # Build elements
    elements = []

    # Stats fields (two columns)
    elements.append({
        "tag": "div",
        "fields": [
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**🏃 运行中** {len(running_tasks)}/3"
                }
            },
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**⏳ 等待中** {len(queued_tasks)}"
                }
            },
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**✅ 今日完成** {len(done_today)}"
                }
            },
        ]
    })

    elements.append({"tag": "hr"})

    # Running tasks section
    if enriched_running:
        running_lines = ["**🏃 运行中任务**"]
        for t in enriched_running:
            pri_icon = PRIORITY_ICONS.get(t.get("priority", "normal"), "🟢")
            elapsed = ""
            if t.get("elapsed_min") is not None:
                elapsed = f" ({t['elapsed_min']:.0f}min)"
            tokens = ""
            if t.get("total_tokens"):
                tok_val = t["total_tokens"]
                tokens = f" | tok={tok_val // 1000}k" if tok_val else ""
            running_lines.append(f"{pri_icon} **{t['id']}** {t['description']}{elapsed}{tokens}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(running_lines)}
        })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🏃 运行中任务**\n_无_"}
        })

    # Queued tasks section
    if queued_tasks:
        # Sort by priority
        sorted_queued = sorted(queued_tasks, key=lambda t: (-t.get("priority_value", 2), t.get("created", "")))
        done_ids = {t["id"] for t in tasks if t["status"] == "done"}
        queued_lines = ["**⏳ 等待中任务**"]
        for t in sorted_queued[:10]:  # Max 10 to keep card readable
            pri_icon = PRIORITY_ICONS.get(t.get("priority", "normal"), "🟢")
            deps = t.get("depends_on", [])
            unmet = [d for d in deps if d not in done_ids]
            blocked = f" [← {','.join(unmet)}]" if unmet else ""
            queued_lines.append(f"{pri_icon} **{t['id']}** {t['description']}{blocked}")
        if len(queued_tasks) > 10:
            queued_lines.append(f"_... 还有 {len(queued_tasks) - 10} 个任务_")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(queued_lines)}
        })

    # Update time note
    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": f"更新时间: {now.strftime('%Y-%m-%d %H:%M:%S')} SGT"}
        ]
    })

    # Refresh button
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🔄 刷新"},
                "type": "primary",
                "value": {"action": "refresh_board"}
            }
        ]
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"content": "📋 Luna 任务看板", "tag": "plain_text"},
            "template": "blue"
        },
        "elements": elements
    }
    return card


def send_card(chat_id: str) -> str:
    """发送新卡片到群聊，返回 message_id"""
    token = get_tenant_token()
    card = build_card()

    body = json.dumps({
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card),
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    message_id = data.get("data", {}).get("message_id", "")

    # Cache state
    save_card_state(chat_id, message_id)

    return message_id


def update_card(message_id: str):
    """更新已有卡片"""
    token = get_tenant_token()
    card = build_card()

    body = json.dumps({
        "content": json.dumps(card),
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/im/v1/messages/{message_id}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    # Update cached timestamp
    state = load_card_state()
    if state:
        state["last_updated"] = datetime.now(SGT).isoformat()
        _save_state(state)

    return data


def auto_card(chat_id: str) -> str:
    """自动模式：有缓存则更新，否则发送新卡片"""
    state = load_card_state()
    if state and state.get("message_id") and state.get("chat_id") == chat_id:
        try:
            update_card(state["message_id"])
            return state["message_id"]
        except Exception:
            # Update failed (message deleted?), send new
            pass
    return send_card(chat_id)


def load_card_state() -> dict:
    if CARD_STATE.exists():
        try:
            with open(CARD_STATE) as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def save_card_state(chat_id: str, message_id: str):
    state = {
        "chat_id": chat_id,
        "message_id": message_id,
        "last_updated": datetime.now(SGT).isoformat(),
    }
    _save_state(state)


def _save_state(state: dict):
    os.makedirs(os.path.dirname(CARD_STATE), exist_ok=True)
    with open(CARD_STATE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]
    target = sys.argv[2]

    try:
        if action == "send":
            msg_id = send_card(target)
            print(json.dumps({"action": "send", "message_id": msg_id}, ensure_ascii=False))
        elif action == "update":
            result = update_card(target)
            print(json.dumps({"action": "update", "message_id": target, "ok": True}, ensure_ascii=False))
        elif action == "auto":
            msg_id = auto_card(target)
            print(json.dumps({"action": "auto", "message_id": msg_id}, ensure_ascii=False))
        else:
            print(f"Unknown action: {action}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
