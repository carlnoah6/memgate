#!/usr/bin/env python3
"""
Write a restart continuation file.
After gateway restart, heartbeat will detect this file and execute the instructions automatically.

Usage:
    python3 scripts/write-continuation.py --context "Patching X" --steps "1. Test Y\n2. Check Z" [--on-success "..."] [--on-failure "..."] [--max-retries 3] [--chat-id "oc_xxx"]
    
Or from Python:
    from write_continuation import write_continuation
    write_continuation(context="...", steps="...", ...)
"""

import json
import sys
import os
from datetime import datetime

CONTINUATION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "restart-continuation.json")

def write_continuation(context: str, steps: str, on_success: str = "", on_failure: str = "", 
                       max_retries: int = 3, retry_count: int = 0, chat_id: str = "", 
                       source_session: str = ""):
    """Write a continuation file that will be picked up after restart."""
    data = {
        "context": context,
        "steps": steps,
        "on_success": on_success,
        "on_failure": on_failure,
        "max_retries": max_retries,
        "retry_count": retry_count,
        "chat_id": chat_id,
        "source_session": source_session,
        "created_at": datetime.now().isoformat(),
    }
    os.makedirs(os.path.dirname(CONTINUATION_FILE), exist_ok=True)
    with open(CONTINUATION_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Continuation written: {CONTINUATION_FILE}")
    return CONTINUATION_FILE

def read_continuation():
    """Read and return continuation data, or None if no file exists."""
    if not os.path.exists(CONTINUATION_FILE):
        return None
    try:
        with open(CONTINUATION_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def clear_continuation():
    """Delete the continuation file after it's been processed."""
    if os.path.exists(CONTINUATION_FILE):
        os.remove(CONTINUATION_FILE)
        print(f"✅ Continuation cleared: {CONTINUATION_FILE}")

def bump_retry():
    """Increment retry count and return updated data. Returns None if max retries exceeded."""
    data = read_continuation()
    if not data:
        return None
    data["retry_count"] = data.get("retry_count", 0) + 1
    if data["retry_count"] > data.get("max_retries", 3):
        clear_continuation()
        return None  # Exceeded max retries
    with open(CONTINUATION_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Write restart continuation")
    parser.add_argument("action", nargs="?", default="write", choices=["write", "read", "clear", "bump"])
    parser.add_argument("--context", default="")
    parser.add_argument("--steps", default="")
    parser.add_argument("--on-success", default="")
    parser.add_argument("--on-failure", default="")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--source-session", default="")
    args = parser.parse_args()
    
    if args.action == "write":
        write_continuation(
            context=args.context,
            steps=args.steps,
            on_success=args.on_success,
            on_failure=args.on_failure,
            max_retries=args.max_retries,
            chat_id=args.chat_id,
            source_session=args.source_session,
        )
    elif args.action == "read":
        data = read_continuation()
        if data:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print("No continuation file found.")
    elif args.action == "clear":
        clear_continuation()
    elif args.action == "bump":
        data = bump_retry()
        if data:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print("Max retries exceeded or no continuation file.")
    sys.exit(0)
