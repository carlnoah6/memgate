#!/usr/bin/env python3
"""
Fix: Streaming card cross-session contamination via onAgentEvent.

Bug: onAgentEvent is a GLOBAL event emitter. When the tool status handler
     is registered per-message in processFeishuMessage, it receives events
     from ALL sessions, not just its own. This causes tool execution from
     the main session to show up on group chat streaming cards (and vice versa).

Fix: Add sessionKey filter. Compute the expected session key from context
     (group: agent:main:feishu:group:<chatId>, DM: agent:main:main) and
     only process events matching that key.

Apply after every OpenClaw update.
"""

import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

OLD = '''\t/* ── Patch: Tool status in streaming card ── */
\tconst toolStatusCleanup = streamingSession ? onAgentEvent((evt) => {
\t\tif (evt?.stream === "tool" && evt?.data?.phase === "start" && streamingSession.isActive()) {'''

NEW = '''\t/* ── Patch: Tool status in streaming card ── */
\t/* ── Patch fix: filter by session key to prevent cross-session contamination ── */
\tconst expectedSessionKey = isGroup ? `agent:main:feishu:group:${chatId}` : "agent:main:main";
\tconst toolStatusCleanup = streamingSession ? onAgentEvent((evt) => {
\t\tif (evt?.stream === "tool" && evt?.data?.phase === "start" && streamingSession.isActive() && evt?.sessionKey === expectedSessionKey) {'''

def apply_patch(path):
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return False

    if "expectedSessionKey" in content:
        print(f"✅ Patch already applied to {path}")
        return False

    if OLD not in content:
        print(f"⚠️ Cannot find target code in {path} — may need manual review")
        return False

    content = content.replace(OLD, NEW)
    with open(path, "w") as f:
        f.write(content)
    print(f"🔧 Patch applied to {path}")
    return True

if __name__ == "__main__":
    changed = False
    for suffix in ["", ".bak"]:
        p = SDK_PATH + suffix
        if apply_patch(p):
            changed = True

    if changed:
        print("\n⚠️ Restart required: bash scripts/restart-gateway.sh \"fix streaming card cross-session contamination\"")
    sys.exit(0)
