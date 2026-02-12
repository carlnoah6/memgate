#!/usr/bin/env python3
"""
Lark 待办任务管理 — 给 Carl 创建有权限访问的任务

确保：
1. 任务创建在共享列表中
2. Carl 有权限查看和操作
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/scripts')
from lark_common import get_tenant_token, get_user_token, lark_api

# Carl 的 open_id
CARL_OPEN_ID = "ou_35f664e694dd100adf97b867e68e1d3a"

def create_shared_task_list(name="Carl 的待办任务", description="Luna 分配的任务列表"):
    """创建共享任务列表，并添加 Carl 为成员"""
    
    # 先检查是否已存在
    existing = get_or_create_task_list()
    if existing:
        return existing
    
    # 创建新的任务列表
    token = get_user_token()  # 使用 user_token 创建
    
    body = {
        "name": name,
        "description": description,
        "members": [
            {
                "member_id": CARL_OPEN_ID,
                "role": "editor"  # 给 Carl 编辑权限
            }
        ]
    }
    
    result = lark_api(
        "POST",
        "/task/v1/tasklists",
        body=body,
        token=token
    )
    
    if result.get("code") == 0:
        tasklist = result.get("data", {}).get("tasklist", {})
        print(f"✅ 创建共享任务列表: {tasklist.get('name')} ({tasklist.get('guid')})")
        
        # 保存到本地
        save_task_list_info(tasklist)
        return tasklist
    else:
        print(f"❌ 创建失败: {result.get('msg')}")
        return None

def get_or_create_task_list():
    """获取现有的 Carl 任务列表"""
    token = get_user_token()
    
    # 列出所有任务列表
    result = lark_api(
        "GET",
        "/task/v1/tasklists?page_size=100",
        token=token
    )
    
    if result.get("code") == 0:
        items = result.get("data", {}).get("items", [])
        for item in items:
            if "Carl" in item.get("name", "") or "待办" in item.get("name", ""):
                print(f"📋 找到现有列表: {item.get('name')} ({item.get('guid')})")
                return item
    
    return None

def create_task_in_list(title, description="", due_date=None, task_list_guid=None):
    """在指定列表中创建任务"""
    
    if not task_list_guid:
        # 获取或创建任务列表
        task_list = get_or_create_task_list()
        if task_list:
            task_list_guid = task_list.get("guid")
        else:
            print("❌ 无法获取任务列表")
            return None
    
    token = get_user_token()
    
    body = {
        "summary": title,
        "description": description,
        "tasklists": [{"guid": task_list_guid}],
        "followers": [{"id": CARL_OPEN_ID}],  # Carl 可以关注任务
    }
    
    if due_date:
        body["due"] = {
            "timestamp": int(due_date.timestamp()),
            "is_all_day": True
        }
    
    result = lark_api(
        "POST",
        "/task/v1/tasks",
        body=body,
        token=token
    )
    
    if result.get("code") == 0:
        task = result.get("data", {}).get("task", {})
        print(f"✅ 创建任务: {task.get('summary')}")
        print(f"   链接: https://applink.larksuite.com/client/todo/detail?guid={task.get('guid')}")
        return task
    else:
        print(f"❌ 创建任务失败: {result.get('msg')}")
        return None

def save_task_list_info(tasklist):
    """保存任务列表信息到本地"""
    import os
    
    data = {
        "guid": tasklist.get("guid"),
        "name": tasklist.get("name"),
        "url": f"https://applink.larksuite.com/client/todo/task_list?guid={tasklist.get('guid')}",
        "created_at": datetime.now().isoformat()
    }
    
    # 保存到文件
    state_file = "/home/ubuntu/.openclaw/workspace/data/lark-task-list-info.json"
    with open(state_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 任务列表信息已保存: {state_file}")

def get_task_list_url():
    """获取任务列表 URL"""
    state_file = "/home/ubuntu/.openclaw/workspace/data/lark-task-list-info.json"
    try:
        with open(state_file) as f:
            data = json.load(f)
            return data.get("url")
    except:
        return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 lark-todo-manager.py <command> [args]")
        print("")
        print("Commands:")
        print("  create-list                  创建共享任务列表")
        print("  add-task <title> [desc]      添加任务")
        print("  url                          显示任务列表链接")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create-list":
        create_shared_task_list()
    elif cmd == "add-task":
        if len(sys.argv) < 3:
            print("Usage: add-task <title> [description]")
            sys.exit(1)
        title = sys.argv[2]
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        create_task_in_list(title, desc)
    elif cmd == "url":
        url = get_task_list_url()
        if url:
            print(f"任务列表链接: {url}")
        else:
            print("未找到任务列表，请先运行 create-list")
    else:
        print(f"Unknown command: {cmd}")
