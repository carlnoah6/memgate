#!/usr/bin/env python3
"""Luna OS - Task Board Manager

任务面板管理工具。主 session 用这个跟踪所有异步任务。
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
"""

import json
import sys
import os
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
TASK_BOARD = "/home/ubuntu/.openclaw/workspace/data/task-board.json"


def load_board():
    if os.path.exists(TASK_BOARD):
        with open(TASK_BOARD) as f:
            return json.load(f)
    return {"tasks": [], "next_id": 1}


def save_board(board):
    os.makedirs(os.path.dirname(TASK_BOARD), exist_ok=True)
    with open(TASK_BOARD, "w") as f:
        json.dump(board, f, indent=2, ensure_ascii=False)


def now_iso():
    return datetime.now(SGT).isoformat()


def add_task(description, source_chat=None, depends_on=None, create_chat=True):
    board = load_board()
    task_id = f"t{board['next_id']:03d}"
    board["next_id"] += 1
    task = {
        "id": task_id,
        "status": "queued",
        "description": description,
        "created": now_iso(),
        "started": None,
        "session_key": None,
        "source_chat": source_chat,
        "depends_on": depends_on or [],
        "result": None,
        "completed": None,
        "task_chat_id": None,
    }
    board["tasks"].append(task)
    save_board(board)
    
    out = {"id": task_id, "status": "queued"}
    if depends_on:
        out["depends_on"] = depends_on

    # Auto-create Lark group chat (unless --no-chat)
    if create_chat:
        try:
            import subprocess
            result = subprocess.run(
                ["python3", os.path.join(os.path.dirname(__file__), "task-chat.py"),
                 "create", task_id, description],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                chat_data = json.loads(result.stdout)
                chat_id = chat_data.get("chat_id", "")
                if chat_id:
                    # task-chat.py already updates task board with chat_id
                    out["task_chat_id"] = chat_id
            else:
                # Chat creation failed, task still created
                out["chat_warning"] = "群聊创建失败，任务已创建"
                print(f"Warning: chat creation failed: {result.stderr[:100]}", file=sys.stderr)
        except Exception as e:
            out["chat_warning"] = f"群聊创建异常: {str(e)[:50]}"
            print(f"Warning: chat creation error: {e}", file=sys.stderr)

    print(json.dumps(out, ensure_ascii=False))


def start_task(task_id, session_key=""):
    board = load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t["status"] = "running"
            t["session_key"] = session_key
            t["started"] = now_iso()
            save_board(board)
            print(json.dumps({"id": task_id, "status": "running"}, ensure_ascii=False))
            return
    print(f"Task {task_id} not found", file=sys.stderr)
    sys.exit(1)


def complete_task(task_id, result=""):
    board = load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t["status"] = "done"
            t["result"] = result
            t["completed"] = now_iso()
            save_board(board)
            # Show newly unblocked tasks
            unblocked = _get_ready_tasks(board, just_completed=task_id)
            out = {"id": task_id, "status": "done"}
            if unblocked:
                out["unblocked"] = [u["id"] for u in unblocked]
            print(json.dumps(out, ensure_ascii=False))
            return
    print(f"Task {task_id} not found", file=sys.stderr)
    sys.exit(1)


def fail_task(task_id, error=""):
    board = load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t["status"] = "failed"
            t["result"] = error
            t["completed"] = now_iso()
            save_board(board)
            print(json.dumps({"id": task_id, "status": "failed"}, ensure_ascii=False))
            return
    print(f"Task {task_id} not found", file=sys.stderr)
    sys.exit(1)


def cancel_task(task_id):
    board = load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t["status"] = "cancelled"
            t["completed"] = now_iso()
            save_board(board)
            print(json.dumps({"id": task_id, "status": "cancelled"}, ensure_ascii=False))
            return
    print(f"Task {task_id} not found", file=sys.stderr)
    sys.exit(1)


def _get_done_ids(board):
    """Get set of completed task IDs"""
    return {t["id"] for t in board["tasks"] if t["status"] == "done"}


def _get_ready_tasks(board, just_completed=None):
    """Find tasks that are queued and have all dependencies met"""
    done_ids = _get_done_ids(board)
    ready = []
    for t in board["tasks"]:
        if t["status"] != "queued":
            continue
        deps = t.get("depends_on", [])
        if not deps or all(d in done_ids for d in deps):
            ready.append(t)
    return ready


def ready_tasks():
    """Show tasks ready to be spawned (queued + deps met) as JSON"""
    board = load_board()
    ready = _get_ready_tasks(board)
    result = []
    for t in ready:
        result.append({
            "id": t["id"],
            "description": t["description"],
            "source_chat": t.get("source_chat"),
            "depends_on": t.get("depends_on", []),
        })
    print(json.dumps(result, ensure_ascii=False))


def list_tasks(status_filter=None):
    board = load_board()
    tasks = board["tasks"]
    if status_filter:
        tasks = [t for t in tasks if t["status"] == status_filter]

    if not tasks:
        print("📋 任务面板为空")
        return

    done_ids = _get_done_ids(board)
    active = [t for t in tasks if t["status"] in ("queued", "running")]
    done = [t for t in tasks if t["status"] == "done"]
    failed = [t for t in tasks if t["status"] == "failed"]

    if active:
        print("🔄 进行中:")
        for t in active:
            deps = t.get("depends_on", [])
            unmet = [d for d in deps if d not in done_ids]

            if t["status"] == "running":
                icon = "🏃"
            elif unmet:
                icon = "🔒"  # blocked by dependency
            else:
                icon = "⏳"

            elapsed = ""
            if t.get("started"):
                start = datetime.fromisoformat(t["started"])
                mins = (datetime.now(SGT) - start).total_seconds() / 60
                elapsed = f" ({mins:.0f}min)"

            dep_info = ""
            if unmet:
                dep_info = f" [blocked by {','.join(unmet)}]"

            print(f"  {icon} [{t['id']}] {t['description']}{elapsed}{dep_info}")

    if done:
        print(f"\n✅ 最近完成 (共{len(done)}个):")
        for t in done[-5:]:
            summary = t.get("result", "")
            if summary and len(summary) > 60:
                summary = summary[:60] + "..."
            print(f"  [{t['id']}] {t['description']}")
            if summary:
                print(f"       → {summary}")

    if failed:
        print(f"\n❌ 失败 ({len(failed)}个):")
        for t in failed[-3:]:
            print(f"  [{t['id']}] {t['description']}: {t.get('result', '未知错误')}")


def active_tasks():
    """JSON output of active tasks only - for heartbeat monitoring"""
    board = load_board()
    active = [t for t in board["tasks"] if t["status"] in ("queued", "running")]
    result = []
    for t in active:
        elapsed_min = None
        if t.get("started"):
            start = datetime.fromisoformat(t["started"])
            elapsed_min = round((datetime.now(SGT) - start).total_seconds() / 60, 1)
        result.append({
            "id": t["id"],
            "status": t["status"],
            "description": t["description"],
            "elapsed_min": elapsed_min,
            "session_key": t.get("session_key"),
            "depends_on": t.get("depends_on", []),
        })
    print(json.dumps(result, ensure_ascii=False))


def status():
    """Quick status overview as JSON"""
    board = load_board()
    tasks = board["tasks"]
    today = datetime.now(SGT).strftime("%Y-%m-%d")
    ready = _get_ready_tasks(board)
    result = {
        "running": sum(1 for t in tasks if t["status"] == "running"),
        "queued": sum(1 for t in tasks if t["status"] == "queued"),
        "ready": len(ready),
        "done_today": sum(
            1
            for t in tasks
            if t["status"] == "done" and (t.get("completed") or "").startswith(today)
        ),
        "failed_today": sum(
            1
            for t in tasks
            if t["status"] == "failed" and (t.get("completed") or "").startswith(today)
        ),
        "total": len(tasks),
    }
    print(json.dumps(result, ensure_ascii=False))


def set_session_key(task_id, session_key):
    board = load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t["session_key"] = session_key
            save_board(board)
            print(json.dumps({"id": task_id, "session_key": session_key}, ensure_ascii=False))
            return
    print(f"Task {task_id} not found", file=sys.stderr)
    sys.exit(1)


def cleanup(days=7):
    """Remove completed/failed/cancelled tasks older than N days"""
    board = load_board()
    cutoff = datetime.now(SGT) - timedelta(days=days)
    before = len(board["tasks"])
    board["tasks"] = [
        t
        for t in board["tasks"]
        if t["status"] in ("queued", "running")
        or (
            t.get("completed")
            and datetime.fromisoformat(t["completed"]) > cutoff
        )
    ]
    after = len(board["tasks"])
    save_board(board)
    print(f"Cleaned up {before - after} old tasks ({after} remaining)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        # Parse --after and --no-chat flags
        args = sys.argv[2:]
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
        add_task(desc, source, depends_on, create_chat)
    elif cmd == "start":
        start_task(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "complete":
        complete_task(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "fail":
        fail_task(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "cancel":
        cancel_task(sys.argv[2])
    elif cmd == "list":
        f = sys.argv[2] if len(sys.argv) > 2 else None
        list_tasks(f)
    elif cmd == "ready":
        ready_tasks()
    elif cmd == "active":
        active_tasks()
    elif cmd == "status":
        status()
    elif cmd == "set-session":
        if len(sys.argv) < 4:
            print("Usage: task-manager.py set-session <id> <session_key>", file=sys.stderr)
            sys.exit(1)
        set_session_key(sys.argv[2], sys.argv[3])
    elif cmd == "cleanup":
        d = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        cleanup(d)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
