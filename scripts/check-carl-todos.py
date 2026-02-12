#!/usr/bin/env python3
"""检查 Carl 的 Lark 任务完成状态"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lark_common import get_tenant_token, send_message

TODO_FILE = Path("/home/ubuntu/.openclaw/workspace/data/carl-todos.json")

def main():
    if not TODO_FILE.exists():
        return {"checked": 0, "completed": []}
    
    with open(TODO_FILE) as f:
        data = json.load(f)
    
    todos = data.get("todos", [])
    completed_tasks = []
    updated = False
    
    for todo in todos:
        if todo.get("status") != "waiting":
            continue
        if not todo.get("lark_task_guid"):
            continue
            
        try:
            token = get_tenant_token()
            req = urllib.request.Request(
                f"https://open.larksuite.com/open-apis/task/v2/tasks/{todo['lark_task_guid']}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                task_data = json.loads(resp.read())
                task = task_data.get("task", {})
                
                if task.get("status") == "completed":
                    todo["status"] = "completed"
                    todo["completed_at"] = task.get("completed_at")
                    updated = True
                    completed_tasks.append(todo)
                    
                    # 通知 Carl
                    chat_id = "oc_4fe2e6e2dbfd0e6fc35c9dab672ab820"
                    send_message(chat_id, f"✅ 检测到任务完成：{todo['desc']}\n\n正在自动推进规划器...")
                    
        except Exception as e:
            print(f"检查失败 {todo.get('id')}: {e}", file=sys.stderr)
    
    if updated:
        with open(TODO_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return {"checked": len(todos), "completed": completed_tasks}

if __name__ == "__main__":
    result = main()
    print(json.dumps(result))
