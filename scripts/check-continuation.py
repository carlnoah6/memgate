#!/usr/bin/env python3
"""
Check for restart continuation and output instructions for the LLM to follow.
Called by heartbeat after restart detection.

Output:
- JSON with has_continuation=true and full instructions if file exists
- JSON with has_continuation=false if no file
"""

import json
import sys
import os

CONTINUATION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "restart-continuation.json")

def main():
    if not os.path.exists(CONTINUATION_FILE):
        print(json.dumps({"has_continuation": False}))
        return

    try:
        with open(CONTINUATION_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(json.dumps({"has_continuation": False, "error": str(e)}))
        return

    retry_count = data.get("retry_count", 0)
    max_retries = data.get("max_retries", 3)
    
    if retry_count >= max_retries:
        # Exceeded max retries — abort
        os.remove(CONTINUATION_FILE)
        print(json.dumps({
            "has_continuation": True,
            "exceeded_max_retries": True,
            "context": data.get("context", ""),
            "retry_count": retry_count,
            "max_retries": max_retries,
            "chat_id": data.get("chat_id", ""),
        }))
        return

    print(json.dumps({
        "has_continuation": True,
        "exceeded_max_retries": False,
        "context": data.get("context", ""),
        "steps": data.get("steps", ""),
        "on_success": data.get("on_success", ""),
        "on_failure": data.get("on_failure", ""),
        "retry_count": retry_count,
        "max_retries": max_retries,
        "chat_id": data.get("chat_id", ""),
        "source_session": data.get("source_session", ""),
        "file": CONTINUATION_FILE,
    }))

if __name__ == "__main__":
    main()
