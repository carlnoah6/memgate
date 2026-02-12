#!/usr/bin/env python3
"""Fix: Feishu plugin doesn't set CommandAuthorized, so /new and /reset don't work.

Root cause: The normalizer defaults CommandAuthorized to false when not explicitly set.
For plugins with allowFrom: ["*"], this means no one can use /new or /reset.

Fix: Default CommandAuthorized to true when it's not explicitly set (undefined/null).
Only set to false when it's explicitly set to false.

Original:  normalized.CommandAuthorized = normalized.CommandAuthorized === true;
Patched:   normalized.CommandAuthorized = normalized.CommandAuthorized !== false;
"""

import sys
import os

TARGET = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/loader-BAZoAqqR.js"

ORIGINAL = 'normalized.CommandAuthorized = normalized.CommandAuthorized === true;'
PATCHED  = 'normalized.CommandAuthorized = normalized.CommandAuthorized !== false; /* patched: default true for plugins */'

def main():
    if not os.path.exists(TARGET):
        print(f"❌ Target file not found: {TARGET}")
        sys.exit(1)
    
    with open(TARGET, 'r') as f:
        content = f.read()
    
    if PATCHED in content:
        print("✅ Patch already applied.")
        return
    
    if ORIGINAL not in content:
        print("⚠️ Original pattern not found. Code may have changed.")
        sys.exit(1)
    
    content = content.replace(ORIGINAL, PATCHED)
    
    with open(TARGET, 'w') as f:
        f.write(content)
    
    print("🔧 Patch applied: CommandAuthorized now defaults to true for plugins.")
    print("   /new and /reset will work in Feishu chats.")
    print("   Restart required: openclaw gateway restart")

if __name__ == "__main__":
    main()
