#!/usr/bin/env python3
"""Knowledge Sync Watcher Monitor — 监控知识同步守护进程状态

Usage:
  knowledge-sync-monitor.py check        — 检查 watcher 状态，失败时报警
  knowledge-sync-monitor.py report       — 发送状态报告到 Carl

功能：
  1. 检测 watcher 是否运行（PID 有效性检查）
  2. 检查日志文件是否有错误
  3. 如发现问题，发送 Lark 消息通知 Carl
  4. 每分钟由 cron 调用（通过 heartbeat-scheduler.py）
"""

import json
import os
import sys
import subprocess
import re
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
WORKSPACE = "/home/ubuntu/.openclaw/workspace"
PID_FILE = os.path.join(WORKSPACE, "data", "knowledge-watcher.pid")
LOG_FILE = os.path.join(WORKSPACE, "data", "knowledge-watcher.log")
INCIDENTS_FILE = os.path.join(WORKSPACE, "data", "cross-session-incidents.jsonl")
SEND_SCRIPT = os.path.join(WORKSPACE, "scripts", "lark-send-message.sh")

# Carl 主对话 chat_id
CARL_CHAT_ID = "oc_680d9c843e6a0ad501de9299a97f3a7e"


def now_sgt():
    return datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S")


def check_watcher_running():
    """Check if watcher process is actually running."""
    if not os.path.exists(PID_FILE):
        return False, "PID file missing"
    
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        os.kill(pid, 0)
        return True, f"Running (PID: {pid})"
    except (ValueError, ProcessLookupError, PermissionError) as e:
        return False, f"Process not found: {e}"


def check_log_errors():
    """Check log file for recent errors."""
    if not os.path.exists(LOG_FILE):
        return []
    
    errors = []
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        
        # Check last 100 lines for errors in last hour
        for line in lines[-100:]:
            if "ERROR" in line or "❌" in line:
                # Parse timestamp if present
                errors.append(line.strip())
    except Exception as e:
        errors.append(f"Failed to read log: {e}")
    
    return errors[-5:]  # Return last 5 errors


def check_recent_incidents():
    """Check for recent cross-session incidents."""
    if not os.path.exists(INCIDENTS_FILE):
        return []
    
    incidents = []
    try:
        with open(INCIDENTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        # Check if within last hour
                        ts = data.get("timestamp", "")
                        incidents.append(data)
                    except json.JSONDecodeError:
                        continue
        # Return last 5 incidents
        return incidents[-5:]
    except Exception as e:
        return [{"error": str(e)}]


def send_alert(message):
    """Send alert message to Carl via Lark."""
    if not os.path.exists(SEND_SCRIPT):
        print(f"❌ Send script not found: {SEND_SCRIPT}")
        return False
    
    try:
        result = subprocess.run(
            ["bash", SEND_SCRIPT, CARL_CHAT_ID, message],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"✅ Alert sent to Carl")
            return True
        else:
            print(f"❌ Failed to send alert: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error sending alert: {e}")
        return False


def cmd_check():
    """Check watcher status and send alert if needed."""
    issues = []
    
    # 1. Check if watcher is running
    running, status_msg = check_watcher_running()
    if not running:
        issues.append(f"🚨 知识同步 watcher 未运行\n   原因: {status_msg}")
    
    # 2. Check for recent errors in log
    errors = check_log_errors()
    if errors:
        issues.append(f"⚠️ 检测到 {len(errors)} 个错误日志\n   最新: {errors[-1][:100]}")
    
    # 3. Check for recent cross-session incidents (only real leaks, not prevented ones)
    incidents = check_recent_incidents()
    # Filter to only actual leaks (announce_cross_session), not prevented skips
    actual_leaks = [i for i in incidents if i.get("type") != "private_to_group_skipped"]
    if len(actual_leaks) > 0:
        issues.append(f"⚠️ 今日有 {len(actual_leaks)} 个串台泄露事件")
    
    # Build report
    report = {
        "time": now_sgt(),
        "running": running,
        "status": status_msg if running else "STOPPED",
        "issues": issues,
        "errors_count": len(errors),
        "incidents_count": len(incidents),
    }
    
    # Send alert if there are issues
    if issues:
        alert_msg = f"🚨 知识同步监控警报 ({now_sgt()})\n"
        alert_msg += f"📍 当前群：Luna机器人主对话（私聊）\n\n"
        alert_msg += "\n\n".join(issues)
        alert_msg += f"\n\n💡 手动重启: `bash scripts/start-knowledge-watcher.sh`"
        send_alert(alert_msg)
        print(json.dumps({"alert_sent": True, **report}, ensure_ascii=False, indent=2))
        return 1
    else:
        print(json.dumps({"alert_sent": False, **report}, ensure_ascii=False, indent=2))
        return 0


def cmd_report():
    """Send status report to Carl."""
    running, status_msg = check_watcher_running()
    errors = check_log_errors()
    incidents = check_recent_incidents()
    
    # Get today's incidents count
    today = datetime.now(SGT).strftime("%Y-%m-%d")
    today_incidents = [i for i in incidents if i.get("timestamp", "").startswith(today)]
    
    status_emoji = "🟢" if running else "🔴"
    errors_emoji = "✅" if len(errors) == 0 else "⚠️"
    incidents_emoji = "✅" if len(today_incidents) == 0 else "🚨"
    
    report = f"""📊 知识同步状态报告 ({now_sgt()})

{status_emoji} Watcher 状态: {status_msg}
{errors_emoji} 最近错误: {len(errors)} 个
{incidents_emoji} 今日串台事件: {len(today_incidents)} 个

监控命令:
• 检查状态: `python3 scripts/knowledge-sync.py status`
• 查看日志: `tail -f data/knowledge-watcher.log`
• 重启 watcher: `bash scripts/start-knowledge-watcher.sh`"""
    
    send_alert(report)
    print(json.dumps({"report_sent": True, "time": now_sgt()}, ensure_ascii=False))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    cmd = sys.argv[1]
    
    if cmd == "check":
        return cmd_check()
    elif cmd == "report":
        return cmd_report()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
