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
import urllib.request
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"
CARL_OPEN_ID = "ou_35f664e694dd100adf97b867e68e1d3a"
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"


def get_tenant_token():
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["tenant_access_token"]


def create_chat(task_id, task_name):
    """Create a Lark group chat for a task, update task board, return chat_id"""
    token = get_tenant_token()
    
    # Truncate name for Lark group name limit
    display_name = task_name[:30] if len(task_name) > 30 else task_name
    
    body = json.dumps({
        "name": f"🤖 {task_id} {display_name}",
        "description": f"Luna OS 子任务: {task_name}",
        "user_id_list": [CARL_OPEN_ID],
        "chat_mode": "group",
        "chat_type": "private"
    }).encode()
    
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/im/v1/chats?set_bot_manager=true",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    
    if result.get("code") != 0:
        print(json.dumps({"error": result.get("msg", "unknown")}))
        sys.exit(1)
    
    chat_id = result["data"]["chat_id"]
    
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
    send_to_chat(token, chat_id, 
        f"🚀 任务 {task_id} 已启动\n\n"
        f"📋 {task_name}\n\n"
        f"子任务会在这里更新进度。完成后群聊会自动解散。"
    )
    
    print(json.dumps({"chat_id": chat_id, "task_id": task_id}))
    return chat_id


def send_to_chat(token, chat_id, text):
    """Send a text message to a chat"""
    body = json.dumps({
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }).encode()
    
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("code") == 0
    except Exception:
        return False


def dissolve_chat(chat_id):
    """Dissolve a group chat"""
    token = get_tenant_token()
    
    # Send goodbye message first
    send_to_chat(token, chat_id, "✅ 任务完成，群聊即将解散。")
    
    req = urllib.request.Request(
        f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}",
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            success = result.get("code") == 0
            print(json.dumps({"dissolved": success, "chat_id": chat_id}))
            return success
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
