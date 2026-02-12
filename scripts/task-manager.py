#!/usr/bin/env python3
"""Luna OS - Task Board Manager

任务面板管理工具 (CLI Wrapper around TaskEngine)。
主 session 用这个跟踪所有异步任务。
支持依赖关系和自动并行调度。

Usage:
  task-manager.py add "描述" [source_chat_id]           → 创建任务 + 自动建群
  task-manager.py add "描述" [chat_id] --no-chat        → 创建任务，不建群（定期检查用）
  task-manager.py add "描述" [chat_id] --after t001     → 创建任务，依赖 t001 完成后才能运行
  task-manager.py add "描述" [chat_id] --after t001,t002 → 依赖多个任务
  task-manager.py start <id> [session_key]              → 标记为运行中
  task-manager.py complete <id> ["结果摘要"]            → 标记完成（自动解锁依赖它的任务）
  task-manager.py fail <id> ["错误信息"]                → 标记失败
  task-manager.py cancel <id>                           → 取消
  task-manager.py list [status]                         → 列出任务
  task-manager.py ready                                 → 可以立即 spawn 的任务（queued + 依赖已满足）
  task-manager.py status                                → 快速状态概览 (JSON)
  task-manager.py active                                → 仅活跃任务 (JSON)
  task-manager.py cleanup [days]                        → 清理 N 天前的已完成任务
  task-manager.py set-session <id> <session_key>        → 补设 session key
"""

import json
import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure we can import task_engine from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_engine import TaskEngine

SGT = timezone(timedelta(hours=8))

def print_json(data):
    print(json.dumps(data, ensure_ascii=False))

def cmd_add(args):
    # Parse --after and --no-chat flags
    depends_on = None
    create_chat = True
    filtered = []
    i = 0
    while i < len(args):
        if args[i] == "--after" and i + 1 < len(args):
            depends_on = [x.strip() for x in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--no-chat":
            create_chat = False
            i += 1
        else:
            filtered.append(args[i])
            i += 1
    
    desc = filtered[0] if len(filtered) > 0 else ""
    source = filtered[1] if len(filtered) > 1 else None
    
    if not desc:
        print("Error: Task description is required", file=sys.stderr)
        sys.exit(1)

    engine = TaskEngine()
    try:
        task = engine.add(desc, source, depends_on=depends_on, create_chat=create_chat)
        
        # Construct output matching old format
        out = {
            "id": task["id"],
            "status": task["status"],
        }
        if task.get("depends_on"):
            out["depends_on"] = task["depends_on"]
        if task.get("task_chat_id"):
            out["task_chat_id"] = task["task_chat_id"]
        # Note: Chat creation failure warning is handled inside TaskEngine (it returns None for chat_id)
        # We don't have explicit "chat_warning" in TaskEngine return yet, but that's acceptable.
        
        print_json(out)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_start(task_id, session_key=""):
    engine = TaskEngine()
    try:
        result = engine.start(task_id, session_key)
        print_json(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_complete(task_id, result_text=""):
    engine = TaskEngine()
    try:
        result = engine.complete(task_id, result_text)
        # Trigger group title update for related chats
        _update_group_title_for_task(engine, task_id)
        print_json(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_fail(task_id, error_text=""):
    engine = TaskEngine()
    try:
        result = engine.fail(task_id, error_text)
        # Trigger group title update for related chats
        _update_group_title_for_task(engine, task_id)
        print_json(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_cancel(task_id):
    engine = TaskEngine()
    try:
        result = engine.cancel(task_id)
        print_json(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_list(status_filter=None):
    engine = TaskEngine()
    # Use enrich=True to get elapsed times and priorities
    tasks = engine.list_tasks(status_filter, enrich=True)
    
    if not tasks:
        print("📋 任务面板为空")
        return

    # Helper to determine if a task is done
    done_ids = {t["id"] for t in tasks if t["status"] == "done"}
    
    active = [t for t in tasks if t["status"] in ("queued", "running")]
    done = [t for t in tasks if t["status"] == "done"]
    failed = [t for t in tasks if t["status"] == "failed"]
    
    # Sort active: running first, then priority (desc), then created
    # TaskEngine already sorts ready tasks, but here we have all active
    active.sort(key=lambda t: (
        0 if t["status"] == "running" else 1,
        -t.get("priority_value", 2),
        t.get("created", "")
    ))

    if active:
        print("🔄 进行中:")
        for t in active:
            deps = t.get("depends_on", [])
            unmet = [d for d in deps if d not in done_ids]
            
            if t["status"] == "running":
                icon = "🏃"
            elif unmet:
                icon = "🔒"
            else:
                icon = "⏳"
            
            elapsed = ""
            if t.get("elapsed_min"):
                elapsed = f" ({t['elapsed_min']:.0f}min)"
            
            dep_info = ""
            if unmet:
                dep_info = f" [blocked by {','.join(unmet)}]"
            
            pri_icon = t.get("priority_icon", "")
            # Only show priority icon if it's not normal or if we want to be explicit
            # task-manager original didn't show priority, let's add it if it's interesting
            # But let's stick to original format mostly.
            
            print(f"  {icon} [{t['id']}] {t['description']}{elapsed}{dep_info}")

    if done:
        print(f"\n✅ 最近完成 (共{len(done)}个):")
        # Show last 5
        for t in done[-5:]:
            summary = t.get("result", "")
            if summary and len(summary) > 60:
                summary = summary[:60] + "..."
            
            duration = ""
            if t.get("started") and t.get("completed"):
                try:
                    start = datetime.fromisoformat(t["started"])
                    end = datetime.fromisoformat(t["completed"])
                    secs = (end - start).total_seconds()
                    if secs < 60:
                        duration = f" ⏱{secs:.0f}s"
                    elif secs < 3600:
                        duration = f" ⏱{secs/60:.0f}m"
                    else:
                        duration = f" ⏱{secs/3600:.1f}h"
                except:
                    pass
            
            print(f"  [{t['id']}]{duration} {t['description']}")
            if summary:
                print(f"       → {summary}")

    if failed:
        print(f"\n❌ 失败 ({len(failed)}个):")
        for t in failed[-3:]:
            print(f"  [{t['id']}] {t['description']}: {t.get('result', '未知错误')}")

def cmd_ready():
    engine = TaskEngine()
    ready = engine.ready()
    print_json(ready)

def cmd_active():
    engine = TaskEngine()
    active = engine.active(enrich=True)
    # Filter keys to match old output exactly if needed, but extra keys are usually fine for JSON consumers
    # Old active() returned: id, status, description, elapsed_min, session_key, depends_on
    # TaskEngine active() returns more. We'll stick to the engine output which is a superset.
    print_json(active)

def cmd_status():
    engine = TaskEngine()
    status = engine.status()
    print_json(status)

def cmd_set_session(task_id, session_key):
    engine = TaskEngine()
    try:
        result = engine.set_session_key(task_id, session_key)
        print_json(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_cleanup(days):
    engine = TaskEngine()
    count = engine.cleanup(days)
    print(f"Cleaned up {count} old tasks")

def _update_group_title_for_task(engine, task_id):
    """任务状态变更后，触发相关群聊的标题更新。
    
    这是一个 fire-and-forget 操作，失败不会阻塞主流程。
    """
    import subprocess
    try:
        task = engine.get_task(task_id)
        if not task:
            return
        
        # 获取相关群聊列表
        chat_ids = set()
        if task.get("source_chat"):
            chat_ids.add(task["source_chat"])
        if task.get("task_chat_id"):
            chat_ids.add(task["task_chat_id"])
        
        if not chat_ids:
            return
        
        # 检查配置，只更新启用的群聊
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "group-title-config.json")
        enabled_chats = set()
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            if not config.get("enabled", True):
                return
            for chat_id, settings in config.get("groups", {}).items():
                if settings.get("enabled", config.get("default_enabled", False)):
                    enabled_chats.add(chat_id)
        except Exception:
            # 配置读取失败，使用默认行为（全部启用）
            enabled_chats = chat_ids
        
        # 触发标题更新（异步，不阻塞）
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update-group-title.py")
        for chat_id in chat_ids:
            if chat_id in enabled_chats:
                try:
                    subprocess.Popen(
                        ["python3", script_path, "--chat-id", chat_id],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                except Exception:
                    pass  # 忽略更新失败
    except Exception:
        pass  # 确保不影响主流程

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        cmd_add(sys.argv[2:])
    elif cmd == "start":
        cmd_start(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "complete":
        cmd_complete(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "fail":
        cmd_fail(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "cancel":
        cmd_cancel(sys.argv[2])
    elif cmd == "list":
        f = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_list(f)
    elif cmd == "ready":
        cmd_ready()
    elif cmd == "active":
        cmd_active()
    elif cmd == "status":
        cmd_status()
    elif cmd == "set-session":
        if len(sys.argv) < 4:
            print("Usage: task-manager.py set-session <id> <session_key>", file=sys.stderr)
            sys.exit(1)
        cmd_set_session(sys.argv[2], sys.argv[3])
    elif cmd == "cleanup":
        d = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        cmd_cleanup(d)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
