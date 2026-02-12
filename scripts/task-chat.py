#!/usr/bin/env python3
"""Luna OS - 任务群聊管理

为子任务自动创建/解散 Lark 临时群聊。

Usage:
  task-chat.py create <task_id> <task_name>   → 创建群，返回 chat_id
  task-chat.py dissolve <chat_id>             → 解散群
  task-chat.py dissolve-task <task_id>        → 根据任务 ID 解散对应群
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Add scripts dir to path for lark_common import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token, lark_api, send_message, CARL_OPEN_ID

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"


def create_chat(task_id, task_name):
    """Create a Lark group chat for a task, update task board, return chat_id"""
    token = get_tenant_token()
    
    # Truncate name for Lark group name limit
    display_name = task_name[:30] if len(task_name) > 30 else task_name
    
    result = lark_api(
        "POST",
        "/im/v1/chats?set_bot_manager=true",
        body={
            "name": f"🤖 {task_id} {display_name}",
            "description": f"Luna OS 子任务: {task_name}",
            "user_id_list": [CARL_OPEN_ID],
            "chat_mode": "group",
            "chat_type": "private",
        },
        token=token,
    )
    
    chat_id = result["chat_id"]
    
    # Update task board with chat_id
    if os.path.exists(TASK_BOARD):
        with open(TASK_BOARD) as f:
            board = json.load(f)
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["task_chat_id"] = chat_id
                break
        with open(TASK_BOARD, "w") as f:
            json.dump(board, f, indent=2, ensure_ascii=False)
    
    # Send welcome message
    try:
        send_message(chat_id,
            f"🚀 任务 {task_id} 已启动\n\n"
            f"📋 {task_name}\n\n"
            f"子任务会在这里更新进度。完成后群聊会自动解散。",
            token=token,
        )
    except Exception:
        pass  # Non-critical
    
    print(json.dumps({"chat_id": chat_id, "task_id": task_id}))
    return chat_id


def dissolve_chat(chat_id):
    """Dissolve a group chat"""
    token = get_tenant_token()
    
    # Send goodbye message first
    try:
        send_message(chat_id, "✅ 任务完成，群聊即将解散。", token=token)
    except Exception:
        pass  # Non-critical
    
    try:
        lark_api("DELETE", f"/im/v1/chats/{chat_id}", token=token)
        print(json.dumps({"dissolved": True, "chat_id": chat_id}))
        return True
    except Exception as e:
        print(json.dumps({"dissolved": False, "error": str(e)}))
        return False


def dissolve_task_chat(task_id):
    """Dissolve the chat associated with a task"""
    if not os.path.exists(TASK_BOARD):
        print(json.dumps({"error": "task board not found"}))
        return False
    
    with open(TASK_BOARD) as f:
        board = json.load(f)
    
    for t in board["tasks"]:
        if t["id"] == task_id:
            chat_id = t.get("task_chat_id")
            if not chat_id:
                print(json.dumps({"error": f"no chat for task {task_id}"}))
                return False
            
            success = dissolve_chat(chat_id)
            
            if success:
                t["task_chat_id"] = None
                with open(TASK_BOARD, "w") as f:
                    json.dump(board, f, indent=2, ensure_ascii=False)
            
            return success
    
    print(json.dumps({"error": f"task {task_id} not found"}))
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        task_id = sys.argv[2]
        task_name = sys.argv[3] if len(sys.argv) > 3 else task_id
        create_chat(task_id, task_name)
    elif cmd == "dissolve":
        dissolve_chat(sys.argv[2])
    elif cmd == "dissolve-task":
        dissolve_task_chat(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
