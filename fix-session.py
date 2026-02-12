#!/usr/bin/env python3
import json
import sys

sessions_file = "/home/ubuntu/.openclaw/agents/main/sessions/sessions.json"

with open(sessions_file, 'r') as f:
    data = json.load(f)

# Find and fix the main session
if "agent:main:main" in data:
    session = data["agent:main:main"]
    print(f"Before: systemSent={session.get('systemSent')}, totalTokens={session.get('totalTokens', 'N/A')}")
    
    # Reset systemSent to false
    session["systemSent"] = False
    
    # Reset totalTokens if it exists (it's an integer)
    if "totalTokens" in session:
        session["totalTokens"] = 0
    
    print(f"After: systemSent={session.get('systemSent')}, totalTokens={session.get('totalTokens', 'N/A')}")
    
    # Write back
    with open(sessions_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("Session fixed successfully!")
else:
    print("Main session not found!")
    sys.exit(1)