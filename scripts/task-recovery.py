#!/usr/bin/env python3
"""
task-recovery.py — 重启后自动恢复中断的任务

扫描 task board 中 status=running 的任务：
1. 检查 session 文件是否存在
2. 存在 → 输出到 recoverable 列表，由心跳通过 sessions_send 恢复
3. 不存在 → 标记失败

用法:
    python3 scripts/task-recovery.py              # 扫描并处理
    python3 scripts/task-recovery.py --dry-run    # 仅检查，不标记失败
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
sys.path.insert(0, str(WORKSPACE / "scripts"))

from inspect_session import get_session_file, analyze_session
from task_engine import TaskEngine

SGT = timezone(timedelta(hours=8))
engine = TaskEngine()


RESUME_MSG_TEMPLATE = (
    "⚠️ 系统重启，你的任务 {task_id} 被中断了。\n\n"
    "请检查你之前的进度，从中断处继续完成任务。\n\n"
    "完成后执行:\n"
    "```bash\n"
    "python3 {workspace}/scripts/spawn-task.py complete {task_id} \"结果摘要\"\n"
    "```\n"
    "失败时执行:\n"
    "```bash\n"
    "python3 {workspace}/scripts/spawn-task.py fail {task_id} \"失败原因\"\n"
    "```"
)


def check_task(task):
    """检查一个中断的任务，返回 (action, detail, extra)"""
    task_id = task["id"]
    session_key = task.get("session_key", "")

    if not session_key:
        return "no_session", "无 session_key（调用 start 时未传入，无法恢复）", {}

    # 1. 检查 session 文件是否存在
    session_file = get_session_file(session_key)
    if not session_file:
        return "lost", "session 文件不存在，无法恢复", {}

    # 2. 分析 session 状态
    analysis = analyze_session(session_key)
    if analysis.get("error"):
        return "lost", f"session 分析失败: {analysis['error']}", {}

    status = analysis.get("status", "")

    # 3. 如果 session 还活着，跳过
    if "Running" in status:
        return "alive", "session 仍在运行", {}

    # 4. Session 文件存在但已停止 → 可恢复
    resume_msg = RESUME_MSG_TEMPLATE.format(
        task_id=task_id, workspace=WORKSPACE
    )
    return "recoverable", f"session 文件存在，可通过 sessions_send 恢复", {
        "session_key": session_key,
        "resume_message": resume_msg,
        "session_id": analysis.get("session_id", ""),
        "last_action": analysis.get("last_action", ""),
        "tokens_used": analysis.get("total_tokens", 0),
    }


def main():
    dry_run = "--dry-run" in sys.argv

    board = engine.load_board()
    running_tasks = [t for t in board["tasks"] if t["status"] == "running"]

    if not running_tasks:
        print(json.dumps({"total": 0, "recoverable": [], "lost": [], "alive": []}))
        return

    result = {
        "total": len(running_tasks),
        "recoverable": [],
        "lost": [],
        "alive": [],
    }

    for task in running_tasks:
        action, detail, extra = check_task(task)
        info = {
            "task_id": task["id"],
            "description": task["description"][:80],
            "detail": detail,
            **extra,
        }

        if action == "recoverable":
            result["recoverable"].append(info)
        elif action in ("lost", "no_session"):
            result["lost"].append(info)
            if not dry_run:
                try:
                    engine.fail(task["id"], f"重启后无法恢复: {detail}")
                except Exception:
                    pass
        elif action == "alive":
            result["alive"].append(info)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
