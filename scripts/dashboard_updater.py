#!/usr/bin/env python3
"""Dashboard Auto-Update Module

集成到 TaskEngine，在状态变更后自动触发仪表盘更新。
包含防抖机制（最小间隔 30 秒），避免频繁刷新。
"""

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Config
MIN_UPDATE_INTERVAL_SECONDS = 30  # 防抖间隔
DASHBOARD_STATE_FILE = Path("/home/ubuntu/.openclaw/workspace/data/dashboard-state.json")
UPDATE_LOG_FILE = Path("/home/ubuntu/.openclaw/workspace/data/dashboard-update.log")

SGT = timezone(timedelta(hours=8))


def _now():
    return datetime.now(SGT)


def _should_update() -> bool:
    """检查是否应该更新（基于时间间隔防抖）"""
    # 检查 dashboard state 中的 last_update_ts
    if DASHBOARD_STATE_FILE.exists():
        try:
            with open(DASHBOARD_STATE_FILE) as f:
                state = json.load(f)
            last_ts = state.get("last_update_ts")
            if last_ts:
                elapsed = _now().timestamp() - last_ts
                if elapsed < MIN_UPDATE_INTERVAL_SECONDS:
                    return False  # 太频繁，跳过
        except Exception:
            pass
    return True


def _log_update(trigger: str, result: dict):
    """记录更新日志"""
    try:
        log_entry = {
            "time": _now().isoformat(),
            "trigger": trigger,
            "result": result,
        }
        logs = []
        if UPDATE_LOG_FILE.exists():
            try:
                with open(UPDATE_LOG_FILE) as f:
                    logs = json.load(f)
            except Exception:
                pass
        logs.append(log_entry)
        # 只保留最近 100 条
        logs = logs[-100:]
        with open(UPDATE_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def update_dashboard(trigger: str = "unknown", force: bool = False) -> dict:
    """
    触发仪表盘更新。
    
    Args:
        trigger: 触发来源（如 'task_start', 'task_complete', 'heartbeat'）
        force: 是否强制更新（跳过防抖检查）
    
    Returns:
        {"ok": bool, "action": str, "skipped": bool, "reason": str}
    """
    # 检查防抖
    if not force and not _should_update():
        result = {"ok": True, "skipped": True, "reason": "rate_limited", "trigger": trigger}
        _log_update(trigger, result)
        return result
    
    # 调用 lark-task-dashboard.py
    try:
        proc = subprocess.run(
            ["python3", "/home/ubuntu/.openclaw/workspace/scripts/lark-task-dashboard.py"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode == 0:
            output = json.loads(proc.stdout)
            result = {
                "ok": True,
                "skipped": False,
                "action": output.get("action", "unknown"),
                "message_id": output.get("message_id"),
                "trigger": trigger,
            }
        else:
            result = {
                "ok": False,
                "skipped": False,
                "error": f"exit_code={proc.returncode}, stderr={proc.stderr}",
                "trigger": trigger,
            }
    except subprocess.TimeoutExpired:
        result = {"ok": False, "skipped": False, "error": "timeout", "trigger": trigger}
    except Exception as e:
        result = {"ok": False, "skipped": False, "error": str(e), "trigger": trigger}
    
    _log_update(trigger, result)
    return result


def get_last_update_info() -> dict:
    """获取上次更新信息（用于调试）"""
    if not DASHBOARD_STATE_FILE.exists():
        return {"error": "no_state_file"}
    
    try:
        with open(DASHBOARD_STATE_FILE) as f:
            state = json.load(f)
        
        last_ts = state.get("last_update_ts", 0)
        elapsed = _now().timestamp() - last_ts if last_ts else None
        
        return {
            "message_id": state.get("message_id"),
            "last_updated": state.get("last_updated"),
            "seconds_ago": elapsed,
            "can_update": elapsed is None or elapsed >= MIN_UPDATE_INTERVAL_SECONDS,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(get_last_update_info(), ensure_ascii=False, indent=2))
    else:
        trigger = sys.argv[1] if len(sys.argv) > 1 else "manual"
        result = update_dashboard(trigger=trigger, force=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
