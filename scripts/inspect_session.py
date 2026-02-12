#!/usr/bin/env python3
import sys
import os
import json
import re
import time
from collections import deque
from pathlib import Path
from datetime import datetime

# OpenClaw Session Storage Path (Kernel Level Access)
SESSION_DIR = Path("/home/ubuntu/.openclaw/agents/main/sessions")

# Only allow hex characters and dashes (UUID format)
_SAFE_SESSION_ID = re.compile(r'^[a-f0-9-]+$')

def _resolve_session_id(session_key):
    """Resolve session key to actual sessionId via sessions.json."""
    sessions_file = SESSION_DIR / "sessions.json"
    if not sessions_file.exists():
        return None
    try:
        data = json.load(open(sessions_file))
        entry = data.get(session_key, {})
        return entry.get("sessionId")
    except Exception:
        return None

def get_session_file(session_id_or_key):
    # If full key provided (agent:main:subagent:UUID), resolve via sessions.json
    if "agent:main:" in session_id_or_key:
        # First try resolving through sessions.json (key → sessionId)
        real_id = _resolve_session_id(session_id_or_key)
        if real_id:
            session_id = real_id
        else:
            # Fallback: extract last segment (works if key UUID == sessionId)
            parts = session_id_or_key.split(":")
            session_id = parts[-1]
    else:
        session_id = session_id_or_key

    # P0: Validate session_id to prevent path traversal
    if not session_id or not _SAFE_SESSION_ID.match(session_id):
        return None

    # Direct match
    f = SESSION_DIR / f"{session_id}.jsonl"
    if f.exists():
        return f
    
    return None

def tail_jsonl(filepath, lines=1):
    """Read last N valid JSON lines from file using deque."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            last_lines = deque(f, maxlen=lines)
            valid_jsons = []
            for line in last_lines:
                if not line.strip(): continue
                try:
                    valid_jsons.append(json.loads(line))
                except Exception:
                    continue
            return valid_jsons
    except Exception as e:
        return []

def analyze_session(session_id_or_key):
    f = get_session_file(session_id_or_key)
    if not f:
        return {"error": "Session file not found", "path": str(SESSION_DIR)}
    
    # Read last 50 lines to find usage and content (tool outputs can be long)
    last_msgs = tail_jsonl(f, 50)
    if not last_msgs:
        return {"status": "empty", "file": str(f)}

    # 1. Get Timestamp from the VERY last message
    last_msg = last_msgs[-1]
    ts_raw = last_msg.get("timestamp", 0)
    if isinstance(ts_raw, str):
        try:
            if ts_raw.endswith("Z"): ts_raw = ts_raw[:-1]
            timestamp = datetime.fromisoformat(ts_raw).timestamp()
        except Exception: timestamp = 0
    else:
        timestamp = ts_raw / 1000.0

    now = time.time()
    ago = now - timestamp
    
    if ago < 60: status = "🟢 Running"
    elif ago < 600: status = "🟡 Stalled"
    else: status = "🔴 Dead"

    # 2. Scan backwards for Usage and Content
    total_tokens = 0
    preview = ""
    
    for msg in reversed(last_msgs):
        # Find latest usage (check root and inside message)
        if total_tokens == 0:
            usage = msg.get("usage") or msg.get("message", {}).get("usage")
            if usage and usage.get("totalTokens", 0) > 0:
                total_tokens = usage.get("totalTokens", 0)
        
        # Find latest content preview
        if not preview:
            # Check 'message.content' (standard) or 'content' (legacy/other)
            content = msg.get("message", {}).get("content") or msg.get("content")
            
            if content:
                if isinstance(content, list):
                    parts = []
                    for p in content:
                        if p.get("type") == "text":
                            parts.append(p.get("text", "")[:50])
                        elif p.get("type") == "toolCall":
                            parts.append(f"[Tool: {p.get('name')}]")
                        elif p.get("type") == "toolResult":
                            parts.append(f"[Result: {p.get('toolName')}]")
                    if parts:
                        preview = " | ".join(parts)
                elif isinstance(content, str):
                    preview = content[:50]
        
        if total_tokens > 0 and preview:
            break

    return {
        "status": status,
        "age_seconds": ago,
        "last_active_ago": f"{ago:.1f}s",
        "last_active_time": datetime.fromtimestamp(timestamp).strftime("%H:%M:%S"),
        "total_tokens": total_tokens,
        "last_action": preview,
        "session_id": f.stem
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: inspect-session.py <session_id_or_key>")
        sys.exit(1)
        
    result = analyze_session(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
