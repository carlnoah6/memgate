#!/usr/bin/env python3
"""Patch: Suppress subagent announce when sub-task's final reply is NO_REPLY.

Root cause: sessions_spawn announce routes through main session's deliveryContext,
which is bound to whatever chat was last active → messages go to wrong chat (串台).

Fix: If the sub-task's final reply is NO_REPLY (meaning it already handled notification
via lark-send-message.sh / planner callbacks), skip the announce entirely.

Insertion point: in runSubagentAnnounceFlow(), after reply is determined,
check if it's NO_REPLY and return early.
"""

import re
import sys
from pathlib import Path

TARGET = Path("/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/reply-DpTyb3Hh.js")

# The pattern we want to find (after reply is determined, before stats are built)
OLD = """\t\tif (!reply) reply = await readLatestAssistantReply({ sessionKey: params.childSessionKey });
\t\tif (!outcome) outcome = { status: "unknown" };"""

NEW = """\t\tif (!reply) reply = await readLatestAssistantReply({ sessionKey: params.childSessionKey });
\t\t// [Luna patch] Suppress announce when sub-task returns NO_REPLY
\t\t// Sub-tasks that handle their own notification (via planner/lark-send-message)
\t\t// end with NO_REPLY — no need to announce through main session (avoids 串台).
\t\tif (reply && reply.trim() === "NO_REPLY") {
\t\t\tdefaultRuntime.info?.(`Subagent announce suppressed (NO_REPLY) for ${params.childSessionKey}`);
\t\t\treturn true;
\t\t}
\t\tif (!outcome) outcome = { status: "unknown" };"""


def main():
    if not TARGET.exists():
        print(f"❌ Target not found: {TARGET}", file=sys.stderr)
        sys.exit(1)

    content = TARGET.read_text()

    # Check if already patched
    if "Suppress announce when sub-task returns NO_REPLY" in content:
        print("✅ Patch already applied.")
        return

    if OLD not in content:
        print("❌ Could not find patch target. OpenClaw may have been updated.", file=sys.stderr)
        # Try looser match
        if "readLatestAssistantReply" in content and "outcome = { status: \"unknown\" }" in content:
            print("⚠️ Target strings exist but exact match failed. Manual patch needed.", file=sys.stderr)
        sys.exit(1)

    content = content.replace(OLD, NEW, 1)
    TARGET.write_text(content)
    print("🔧 Patch applied: suppress announce when sub-task returns NO_REPLY")
    print("   → Requires gateway restart to take effect")


if __name__ == "__main__":
    main()
