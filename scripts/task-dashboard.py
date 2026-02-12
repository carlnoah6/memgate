#!/usr/bin/env python3
"""Luna OS - Task Dashboard

实时看板：显示活跃任务 + SysMonitor 实况数据。
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_engine import TaskEngine

engine = TaskEngine()


def generate_dashboard():
    tasks = engine.list_tasks(status_filter="running", enrich=True)

    if not tasks:
        print("✅ No active background tasks.")
        return

    print(f"📊 **Luna Task Dashboard** ({datetime.now().strftime('%H:%M:%S')})\n")
    print("| ID | Status | Tokens | Last Active | Task Description |")
    print("|----|--------|--------|-------------|------------------|")

    for task in tasks:
        desc = task['description'][:30] + "..." if len(task['description']) > 30 else task['description']

        if not task.get("session_key"):
            print(f"| {task['id']} | ⚪ No Key | - | - | {desc} |")
            continue

        # Use enriched SysMonitor data
        status_icon = task.get("real_status", "⚪ Unknown")
        if "Running" in status_icon:
            status = "🟢 Run"
        elif "Stalled" in status_icon:
            status = "🟡 Stall"
        elif "Dead" in status_icon:
            status = "🔴 Dead"
        else:
            status = status_icon

        tokens = f"{task.get('total_tokens', 0) // 1000}k"
        ago = task.get("last_active_ago", "-")

        print(f"| {task['id']} | {status} | {tokens} | {ago} | {desc} |")

        # If dead/stalled, show last action
        if "Dead" in status_icon or "Stalled" in status_icon:
            action = task.get("last_action", "").replace("\n", " ")[:60]
            print(f"| ↳ | ⚠️ Alert | | | Last: {action} |")


if __name__ == "__main__":
    generate_dashboard()
