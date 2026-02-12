#!/usr/bin/env python3
"""
Patch: Skip subagent announce when child reply is NO_REPLY/HEARTBEAT_OK.

Root cause: Even when sub-task replies with NO_REPLY, runSubagentAnnounceFlow still
triggers - it sends a trigger message to the main session asking it to "summarize".
This causes cross-session routing issues because the announce targets the main session's
current delivery context, not the task's source_chat.

Fix: If the child's last reply is NO_REPLY or HEARTBEAT_OK, skip the announce entirely.
The task-manager.py complete/fail already handles notifications to the correct chat.
"""

import sys
import shutil
from datetime import datetime

TARGET = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
PATCH_MARKER = "/* Luna Patch: skip announce for NO_REPLY */"

def apply():
    with open(TARGET, 'r') as f:
        content = f.read()

    if PATCH_MARKER in content:
        print("✅ Patch already applied.")
        return False

    # Find the point after reply is read but before the announce is sent
    old = '''\t\tif (!reply) reply = await readLatestAssistantReply({ sessionKey: params.childSessionKey });
\t\tif (!outcome) outcome = { status: "unknown" };'''

    new = f'''\t\tif (!reply) reply = await readLatestAssistantReply({{ sessionKey: params.childSessionKey }});
\t\t{PATCH_MARKER}
\t\tif (reply && /^\\s*(NO_REPLY|HEARTBEAT_OK)\\s*$/i.test(reply.trim())) {{
\t\t\tdefaultRuntime.log?.(`Skipping announce for ${{params.label || params.childSessionKey}}: child replied NO_REPLY`);
\t\t\treturn false;
\t\t}}
\t\tif (!outcome) outcome = {{ status: "unknown" }};'''

    if old not in content:
        print("❌ Cannot find target code in runSubagentAnnounceFlow")
        sys.exit(1)

    backup = TARGET + f".backup-announce-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(TARGET, backup)
    print(f"📦 Backup: {backup}")

    content = content.replace(old, new)
    with open(TARGET, 'w') as f:
        f.write(content)

    print("🔧 Patch applied: skip announce for NO_REPLY")
    return True

if __name__ == "__main__":
    if "--check" in sys.argv:
        with open(TARGET) as f:
            print("✅ Applied" if PATCH_MARKER in f.read() else "⚠️ Not applied")
        sys.exit(0)
    apply()
