#!/usr/bin/env python3
"""
Fix: FeishuStreamingSession.close() leaks silent reply tokens (NO_REPLY, HEARTBEAT_OK).

Bug: When the LLM outputs "NO_REPLY" or "HEARTBEAT_OK":
  1. onPartialReply shows it on the streaming card
  2. normalizeReplyPayload correctly filters it out → deliver callback never called
  3. But the cleanup `streamingSession.close()` uses `this.state.currentText` as fallback
  4. "NO_REPLY" is not empty → card closes with "NO_REPLY" as visible content

Fix: In close(), check if the final text matches silent reply tokens.
     If so, delete the card (same as empty content behavior).

Apply after every OpenClaw update.
"""

import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

# The original code checks only for empty text
OLD = '''\t\tconst text = finalText ?? this.state.currentText;
\t\t/* ── Patch 7: Delete zombie "Thinking..." cards ── */
\t\tif ((!text || !text.trim()) && this.state.messageId) {'''

# Extended to also catch silent reply tokens
NEW = '''\t\tconst text = finalText ?? this.state.currentText;
\t\t/* ── Patch 7: Delete zombie "Thinking..." cards ── */
\t\t/* ── Patch: Also delete cards showing silent reply tokens (NO_REPLY, HEARTBEAT_OK) ── */
\t\tconst isSilentContent = !text || !text.trim() || /^\\s*NO_REPLY\\s*$/i.test(text) || /^\\s*HEARTBEAT_OK\\s*$/i.test(text);
\t\tif (isSilentContent && this.state.messageId) {'''

def apply_patch(path):
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return False

    if "isSilentContent" in content:
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
        print("\n⚠️ Restart required: bash scripts/restart-gateway.sh \"fix NO_REPLY leak in streaming cards\"")
    sys.exit(0)
