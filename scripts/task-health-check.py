#!/usr/bin/env python3
"""Luna OS - Task Board Health Check

心跳时运行，检查任务面板健康状况。
Wrapper around TaskEngine.health_check().

输出格式：
{"stale": [...], "active": [...], "cleaned": N}
"""

import json
import sys
import os
from pathlib import Path

# Ensure we can import task_engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_engine import TaskEngine

def check_health():
    engine = TaskEngine()
    try:
        result = engine.health_check()
        
        # Check planner pending advances (kept separate as it's not strictly board logic)
        pending_dir = Path("/home/ubuntu/.openclaw/workspace/data/planner-pending")
        if pending_dir.exists():
            pending_files = list(pending_dir.glob("*.json"))
            if pending_files:
                result["planner_pending"] = [f.stem for f in pending_files]
        
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        # Fallback error output
        print(json.dumps({"error": str(e), "stale": [], "active": []}, ensure_ascii=False))

if __name__ == "__main__":
    check_health()
