#!/usr/bin/env python3
"""Luna OS - Zombie Task Cleanup

用于系统重启后，清理所有处于 'running' 状态的僵尸任务。
将它们标记为 failed，并记录原因。
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"

def cleanup_zombies():
    if not os.path.exists(TASK_BOARD):
        return

    with open(TASK_BOARD) as f:
        board = json.load(f)

    changed = False
    cleaned_count = 0
    now_iso = datetime.now(SGT).isoformat()

    for t in board["tasks"]:
        if t["status"] == "running":
            t["status"] = "failed"
            t["result"] = "系统重启，任务自动终止 (Zombie Cleanup)"
            t["completed"] = now_iso
            changed = True
            cleaned_count += 1
            print(f"💀 Killed zombie task: {t['id']} - {t['description']}")

            # 尝试解散对应的群聊（如果有）
            if t.get("task_chat_id"):
                try:
                    import subprocess
                    # 发送通知并解散
                    subprocess.run(
                        ["bash", "/home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh",
                         t["task_chat_id"], "❌ 系统重启，任务异常终止"],
                        timeout=5
                    )
                    subprocess.run(
                        ["python3", "/home/ubuntu/.openclaw/workspace/scripts/task-chat.py",
                         "dissolve", t["task_chat_id"]],
                        timeout=15
                    )
                    t["task_chat_id"] = None
                except Exception:
                    pass

    if changed:
        with open(TASK_BOARD, "w") as f:
            json.dump(board, f, indent=2, ensure_ascii=False)
        print(f"✅ Cleaned up {cleaned_count} zombie tasks.")
    else:
        print("✅ No zombie tasks found.")

if __name__ == "__main__":
    cleanup_zombies()
