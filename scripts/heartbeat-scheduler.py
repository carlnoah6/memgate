#!/usr/bin/env python3
"""
心跳调度脚本 — 判断哪些任务到期需要 spawn。
输出 JSON 格式的到期任务列表，供心跳 handler 直接执行。
不需要 LLM 判断，纯逻辑。
"""
import json
import time
import sys
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
STATE_FILE = "/home/ubuntu/.openclaw/workspace/data/heartbeat-state.json"

# 任务定义
TASKS = {
    "periodic": {
        "interval_ms": 5 * 60 * 1000,  # 5 分钟
        "night_skip": True,  # 23:00-07:00 跳过
    },
    "research": {
        "interval_ms": 5 * 60 * 1000,  # 5 分钟
        "night_skip": False,  # 深夜继续
    },
}

def main():
    now = datetime.now(SGT)
    now_ms = int(time.time() * 1000)
    hour = now.hour
    is_night = hour >= 23 or hour < 7
    
    # 读取状态
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except:
        state = {"lastChecks": {}}
    
    due_tasks = []
    
    for task_name, task_config in TASKS.items():
        last_ms = state.get("lastChecks", {}).get(task_name, 0)
        elapsed_ms = now_ms - last_ms
        interval_ms = task_config["interval_ms"]
        
        if task_config.get("night_skip") and is_night:
            continue
        
        if elapsed_ms >= interval_ms:
            due_tasks.append(task_name)
    
    # 每日任务
    today_str = now.strftime("%Y-%m-%d")
    daily_state = state.get("daily", {})
    
    # 日报 04:00
    if hour >= 4 and daily_state.get("dailyReport") != today_str:
        due_tasks.append("dailyReport")
    
    # 早安 07:00
    if hour >= 7 and daily_state.get("morningGreeting") != today_str:
        due_tasks.append("morningGreeting")
    
    # 周日计划 Review 10:00（每周日）
    if now.weekday() == 6 and hour >= 10 and daily_state.get("weeklyReview") != today_str:
        due_tasks.append("weeklyReview")
    
    # 输出结果
    result = {
        "time": now.strftime("%H:%M SGT"),
        "is_night": is_night,
        "due": due_tasks,
        "state_age": {k: f"{(now_ms - state.get('lastChecks', {}).get(k, 0)) / 60000:.0f}m" for k in TASKS},
    }
    
    print(json.dumps(result))
    
    # 运行知识同步监控检查（静默执行，如有问题会自己发警报）
    import subprocess
    try:
        subprocess.run(
            ["python3", "/home/ubuntu/.openclaw/workspace/scripts/knowledge-sync-monitor.py", "check"],
            capture_output=True,
            timeout=10
        )
    except:
        pass  # Silent fail, monitor.py handles its own alerts
    
    # 检查 Carl 的任务完成状态
    try:
        result = subprocess.run(
            ["python3", "/home/ubuntu/.openclaw/workspace/scripts/check-carl-todos.py"],
            capture_output=True,
            timeout=15
        )
        if result.returncode == 0:
            check_result = json.loads(result.stdout)
            if check_result.get("completed"):
                # 有任务完成，添加到 due_tasks 让心跳 handler 处理
                due_tasks.append("carl-todo-completed")
    except:
        pass  # Silent fail
    
    # 如果有到期任务，更新状态
    if due_tasks:
        for task in due_tasks:
            if task in TASKS:
                state.setdefault("lastChecks", {})[task] = now_ms
            elif task in ("dailyReport", "morningGreeting", "weeklyReview"):
                state.setdefault("daily", {})[task] = today_str
        
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

if __name__ == "__main__":
    main()
