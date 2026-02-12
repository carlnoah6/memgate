#!/usr/bin/env python3
"""cleanup-task-chats.py — Dissolve old task group chats

Identifies Lark group chats created by Luna OS task system (name starts with "🤖")
and dissolves those older than a configurable threshold (default: 24 hours).

Strategy (since Lark chat API doesn't expose create_time):
1. Cross-reference with task-board.json for creation timestamps
2. Orphaned chats (not in board) → dissolve unconditionally
3. Active/running tasks → never dissolve
4. Protected permanent chats → never dissolve

Usage:
    python3 scripts/cleanup-task-chats.py              # Run cleanup
    python3 scripts/cleanup-task-chats.py --dry-run     # Preview without dissolving
    python3 scripts/cleanup-task-chats.py --hours 48    # Custom age threshold

Designed to be called from daily-report-engine.py at 4AM as part of the daily cleanup.
Can also be run standalone.

Output: JSON with results summary.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token, BASE_URL

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"

# Task chats are named "🤖 tid-XXX description"
TASK_CHAT_PREFIX = "\U0001f916"  # 🤖

# Permanent chats that must NEVER be dissolved, regardless of name
PROTECTED_CHATS = {
    "oc_680d9c843e6a0ad501de9299a97f3a7e",  # Luna机器人主对话
    "oc_7f3ebd31a5cf2fec9170952b29eb2700",  # Luna日程
    "oc_a2a70c6b4a29c2f2eb6c2500ea42a500",  # Luna 卢娜数字员工 (PROTECTED - 特殊标识群，勿自动改名)
    "oc_630995d9b870d2ff6ab3fa34a4e7315a",  # Luna任务板
    "oc_0900e63860f8b6d1b08285262701817f",  # Luna任务
    "oc_4fe2e6e2dbfd0e6fc35c9dab672ab820",  # Luan测试群聊
    "oc_453c88ec52dd029845c46249837e3ba0",  # Carl 私聊
}


def list_bot_chats(token):
    """List all chats the bot is in, handling pagination."""
    chats = []
    page_token = ""
    while True:
        url = f"{BASE_URL}/im/v1/chats?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        if result.get("code") != 0:
            print(f"Error listing chats: {result.get('msg')}", file=sys.stderr)
            break

        items = result.get("data", {}).get("items", [])
        chats.extend(items)

        if not result.get("data", {}).get("has_more"):
            break
        page_token = result.get("data", {}).get("page_token", "")

    return chats


def dissolve_chat(token, chat_id):
    """Dissolve a group chat via Lark API."""
    req = urllib.request.Request(
        f"{BASE_URL}/im/v1/chats/{chat_id}",
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("code") == 0
    except Exception as e:
        print(f"Failed to dissolve {chat_id}: {e}", file=sys.stderr)
        return False


def load_task_board():
    """Load task board and build chat_id → task lookup."""
    if not os.path.exists(TASK_BOARD):
        return {}
    with open(TASK_BOARD) as f:
        board = json.load(f)
    # Map: task_chat_id → task dict
    return {
        t["task_chat_id"]: t
        for t in board.get("tasks", [])
        if t.get("task_chat_id")
    }


def parse_iso(s):
    """Parse ISO datetime string to timezone-aware datetime."""
    if not s:
        return None
    # Handle various formats
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def update_task_board(dissolved_chat_ids):
    """Clear task_chat_id for dissolved chats in task board."""
    if not os.path.exists(TASK_BOARD):
        return 0
    with open(TASK_BOARD) as f:
        board = json.load(f)

    changed = 0
    for t in board.get("tasks", []):
        if t.get("task_chat_id") in dissolved_chat_ids:
            t["task_chat_id"] = None
            changed += 1

    if changed:
        with open(TASK_BOARD, "w") as f:
            json.dump(board, f, indent=2, ensure_ascii=False)

    return changed


def cleanup_old_task_chats(hours=24, dry_run=False):
    """Main cleanup logic. Returns result dict.

    Can be called programmatically from daily-report-engine.py
    or run standalone via CLI.
    """
    now = datetime.now(SGT)
    cutoff = now - timedelta(hours=hours)

    token = get_tenant_token()
    all_chats = list_bot_chats(token)

    # Build task board lookup: chat_id → task
    board_lookup = load_task_board()

    # Filter: task chats (🤖 prefix) that should be dissolved
    to_dissolve = []
    skipped_active = []
    skipped_young = []

    task_chats = [c for c in all_chats if c.get("name", "").startswith(TASK_CHAT_PREFIX)]

    for chat in task_chats:
        chat_id = chat.get("chat_id", "")
        name = chat.get("name", "")

        # Skip protected chats (safety net)
        if chat_id in PROTECTED_CHATS:
            continue

        task = board_lookup.get(chat_id)

        # If task exists and is still running → skip (never dissolve active work)
        if task and task.get("status") in ("running", "queued"):
            skipped_active.append({"chat_id": chat_id, "name": name, "task_id": task.get("id")})
            continue

        # Determine age from task board's "created" field
        reason = ""
        if task:
            created_dt = parse_iso(task.get("created"))
            if created_dt and created_dt > cutoff:
                skipped_young.append({"chat_id": chat_id, "name": name, "age_hours": round((now - created_dt).total_seconds() / 3600, 1)})
                continue
            age_hours = round((now - created_dt).total_seconds() / 3600, 1) if created_dt else None
            reason = f"task {task.get('id')} ({task.get('status')}), age {age_hours}h" if age_hours else f"task {task.get('id')} ({task.get('status')}), no timestamp"
        else:
            # Orphaned chat: not in task board at all → dissolve unconditionally
            reason = "orphaned (not in task board)"

        to_dissolve.append({
            "chat_id": chat_id,
            "name": name,
            "reason": reason,
        })

    result = {
        "total_bot_chats": len(all_chats),
        "task_chats_found": len(task_chats),
        "to_dissolve": len(to_dissolve),
        "skipped_active": len(skipped_active),
        "skipped_young": len(skipped_young),
        "cutoff_hours": hours,
        "dry_run": dry_run,
        "dissolved": [],
        "failed": [],
    }

    if dry_run:
        result["preview"] = to_dissolve
        if skipped_active:
            result["active_tasks"] = skipped_active
    else:
        dissolved_ids = set()
        for chat_info in to_dissolve:
            cid = chat_info["chat_id"]
            if dissolve_chat(token, cid):
                result["dissolved"].append(chat_info)
                dissolved_ids.add(cid)
            else:
                result["failed"].append(chat_info)
            time.sleep(0.2)  # Lark API rate limit

        # Clean up task board references
        if dissolved_ids:
            result["board_cleaned"] = update_task_board(dissolved_ids)

    return result


def main():
    dry_run = "--dry-run" in sys.argv
    hours = 24
    for i, arg in enumerate(sys.argv):
        if arg == "--hours" and i + 1 < len(sys.argv):
            hours = int(sys.argv[i + 1])

    result = cleanup_old_task_chats(hours=hours, dry_run=dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
