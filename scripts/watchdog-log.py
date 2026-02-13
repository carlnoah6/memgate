import os
import glob
import time
import re
import subprocess
import sys
import json
from datetime import datetime

# Configuration
LOG_DIR = "/tmp/openclaw"
TIMEOUT_SECONDS = 60  # 1 minute aggressive timeout
WORKSPACE_DIR = "/home/ubuntu/.openclaw/workspace"
GATEWAY_PID_FILE = f"{WORKSPACE_DIR}/data/gateway.pid"
WATCHDOG_LOG = f"{WORKSPACE_DIR}/data/watchdog-log-check.log"

# We use SIGUSR1 for Hot Reload (config.patch) instead of restart
# This preserves connections but resets the agent loop

def log_message(message):
    """Log to watchdog log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(WATCHDOG_LOG, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)

def check_gateway_process():
    """Check if openclaw-gateway process is running"""
    # Check PID file first
    if os.path.exists(GATEWAY_PID_FILE):
        try:
            with open(GATEWAY_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            # Check if process exists
            if os.path.exists(f"/proc/{pid}"):
                # Verify it's openclaw-gateway
                try:
                    with open(f"/proc/{pid}/comm", "r") as f:
                        comm = f.read().strip()
                    if "openclaw" in comm or "node" in comm:
                        return True
                except:
                    pass
        except (ValueError, IOError):
            pass
    
    # Fallback: use pgrep
    result = subprocess.run(
        ["pgrep", "-f", "openclaw-gateway"],
        capture_output=True
    )
    if result.returncode == 0:
        # Process found, update PID file
        pids = result.stdout.decode().strip().split("\n")
        if pids and pids[0]:
            try:
                with open(GATEWAY_PID_FILE, "w") as f:
                    f.write(pids[0])
            except IOError:
                pass
        return True
    
    return False

def restart_gateway():
    """Call gateway-watchdog.sh to restart Gateway"""
    log_message("🚨 Gateway process not found! Triggering restart via watchdog...")
    try:
        result = subprocess.run(
            [f"{WORKSPACE_DIR}/scripts/gateway-watchdog.sh", "start"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            log_message("✅ Gateway restart initiated successfully")
        else:
            log_message(f"❌ Gateway restart failed: {result.stderr}")
    except Exception as e:
        log_message(f"❌ Failed to restart Gateway: {e}")

def get_latest_log_file():
    pattern = os.path.join(LOG_DIR, "openclaw-*.log")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def check_log_for_hang(log_file):
    try:
        output = subprocess.check_output(["tail", "-n", "1000", log_file]).decode("utf-8", errors="ignore")
        lines = output.splitlines()
    except Exception as e:
        print(f"Error reading log: {e}")
        return False

    if not lines:
        return False

    # Check last line timestamp
    # OpenClaw logs are JSON format with "time":"2026-02-12T02:45:43.752Z"
    last_line = lines[-1]
    
    # Try JSON format first (new format)
    try:
        json_data = json.loads(last_line)
        time_str = json_data.get("time") or json_data.get("_meta", {}).get("date")
        if time_str:
            # Parse ISO timestamp (handle both with and without Z)
            time_str = time_str.replace("Z", "+00:00")
            if "+" in time_str or "-" in time_str[10:]:
                # Has timezone info
                last_log_time = datetime.fromisoformat(time_str).timestamp()
            else:
                # No timezone, assume UTC
                last_log_time = datetime.strptime(time_str[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
        else:
            return False
    except (json.JSONDecodeError, ValueError, KeyError):
        # Fallback: try old format regex
        ts_match = re.search(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', last_line)
        if not ts_match:
            return False
        try:
            last_log_time = datetime.strptime(ts_match.group(1), "%Y-%m-%dT%H:%M:%S").timestamp()
        except ValueError:
            return False
        
    current_time = time.time()
    silence_duration = current_time - last_log_time
    
    # Logic: If system is silent for > TIMEOUT, check if it was left in a "busy" state
    if silence_duration > TIMEOUT_SECONDS:
        # Scan backwards to see if we are in a task
        for line in reversed(lines):
            if "Stream finished" in line or "reply completed" in line or "Stream error" in line:
                return False # Idle
            if "Stream started" in line or "Processing message" in line or "tool:call" in line:
                print(f"❌ HANG DETECTED: Task active but silent for {silence_duration:.1f}s")
                return True
                
    return False

def main():
    # First priority: check if Gateway process exists
    if not check_gateway_process():
        restart_gateway()
        return
    
    # Second: check for log hang (only if process is running)
    log_file = get_latest_log_file()
    if not log_file:
        return

    if check_log_for_hang(log_file):
        log_message("Triggering HOT RELOAD (SIGUSR1)...")
        # Send SIGUSR1 to openclaw-gateway to trigger Hot Reload
        subprocess.run(["pkill", "-USR1", "-f", "openclaw-gateway"])

if __name__ == "__main__":
    main()
