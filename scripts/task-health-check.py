#!/usr/bin/env python3
"""Luna OS - Task Board Health Check

心跳时运行，检查任务面板健康状况：
1. 检测卡死的子任务（运行超过 max_minutes 且 session 已结束）
2. 自动清理 7 天前的已完成任务
3. 输出 JSON 状态供心跳决策

输出格式：
{"stale": [...], "active": [...], "cleaned": N}
- stale 为空 → 健康
- stale 非空 → 有卡死任务需要处理
"""

import json
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"
MAX_RUNNING_MINUTES = 35  # sub-agent timeout is typically 4-30 min
CLEANUP_DAYS = 7


def load_board():
    if os.path.exists(TASK_BOARD):
        with open(TASK_BOARD) as f:
            return json.load(f)
    return {"tasks": [], "next_id": 1}


def save_board(board):
    with open(TASK_BOARD, "w") as f:
        json.dump(board, f, indent=2, ensure_ascii=False)


def check_health():
    board = load_board()
    now = datetime.now(SGT)
    result = {"stale": [], "active": [], "cleaned": 0}

    for t in board["tasks"]:
        if t["status"] == "running":
            if t.get("started"):
                started = datetime.fromisoformat(t["started"])
                elapsed_min = (now - started).total_seconds() / 60
                if elapsed_min > MAX_RUNNING_MINUTES:
                    # Mark as failed (likely timed out)
                    t["status"] = "failed"
                    t["result"] = f"自动标记失败：运行 {elapsed_min:.0f} 分钟超时"
                    t["completed"] = now.isoformat()
                    result["stale"].append({
                        "id": t["id"],
                        "description": t["description"],
                        "elapsed_min": round(elapsed_min),
                    })
                else:
                    result["active"].append({
                        "id": t["id"],
                        "description": t["description"],
                        "elapsed_min": round(elapsed_min),
                    })
            else:
                result["active"].append({
                    "id": t["id"],
                    "description": t["description"],
                    "elapsed_min": None,
                })
        elif t["status"] == "queued":
            result["active"].append({
                "id": t["id"],
                "description": t["description"],
                "elapsed_min": None,
            })

    # Auto-dissolve task group chats for completed/failed tasks
    for t in board["tasks"]:
        if t["status"] in ("done", "failed", "cancelled") and t.get("task_chat_id"):
            try:
                import subprocess
                subprocess.run(
                    ["python3", "/home/ubuntu/.openclaw/workspace/scripts/task-chat.py",
                     "dissolve", t["task_chat_id"]],
                    timeout=15, capture_output=True
                )
                t["task_chat_id"] = None
            except Exception:
                pass  # Will retry next heartbeat

    # Auto-cleanup old completed/failed/cancelled tasks
    cutoff = now - timedelta(days=CLEANUP_DAYS)
    before = len(board["tasks"])
    board["tasks"] = [
        t for t in board["tasks"]
        if t["status"] in ("queued", "running")
        or not t.get("completed")
        or datetime.fromisoformat(t["completed"]) > cutoff
    ]
    result["cleaned"] = before - len(board["tasks"])

    if result["stale"] or result["cleaned"] > 0:
        save_board(board)

    # Check planner pending advances
    pending_dir = Path("/home/ubuntu/.openclaw/workspace/data/planner-pending")
    if pending_dir.exists():
        pending_files = list(pending_dir.glob("*.json"))
        if pending_files:
            result["planner_pending"] = [f.stem for f in pending_files]

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    check_health()
