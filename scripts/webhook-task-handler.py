#!/usr/bin/env python3
"""处理 Lark 任务完成事件的 webhook"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lark_common import send_message

def handle_task_updated(event_data):
    """处理任务更新事件"""
    task = event_data.get("task", {})
    
    # 检查任务是否完成
    if task.get("status") != "completed":
        return {"status": "ignored", "reason": "task not completed"}
    
    task_guid = task.get("guid")
    task_summary = task.get("summary", "")
    
    # 加载我们的待办列表
    todo_file = Path("/home/ubuntu/.openclaw/workspace/data/luna-carl-todos.json")
    if not todo_file.exists():
        return {"status": "no_todos_file"}
    
    with open(todo_file) as f:
        data = json.load(f)
    
    # 查找匹配的任务
    for todo in data.get("todos", []):
        if todo.get("lark_task_guid") == task_guid and todo.get("status") == "waiting":
            # 标记为完成
            todo["status"] = "completed"
            todo["completed_at"] = task.get("completed_at")
            
            with open(todo_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 通知 Carl
            chat_id = "oc_4fe2e6e2dbfd0e6fc35c9dab672ab820"
            send_message(chat_id, f"✅ 检测到任务完成：{todo['desc']}\n\n自动推进规划器...")
            
            # TODO: 推进规划器
            # 可以在这里调用 planner.py step-done
            
            return {"status": "processed", "todo_id": todo["id"]}
    
    return {"status": "no_matching_todo"}

def main():
    # 从 stdin 读取 webhook payload
    payload = json.load(sys.stdin)
    
    event_type = payload.get("header", {}).get("event_type")
    
    if event_type == "task.task.updated_v1":
        result = handle_task_updated(payload.get("event", {}))
        print(json.dumps(result))
    else:
        print(json.dumps({"status": "ignored", "event_type": event_type}))

if __name__ == "__main__":
    main()
