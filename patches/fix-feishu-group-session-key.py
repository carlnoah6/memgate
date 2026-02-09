#!/usr/bin/env python3
"""
Fix: Feishu group messages use sender's open_id as session key instead of chat_id.

Bug: In processFeishuMessage(), ctx.From is always set to senderId (sender's open_id).
     resolveGroupSessionKey() uses ctx.From to build the group session key.
     This causes all groups with the same sender to share one session.

Fix: For group messages, set From = chatId (the group's chat_id) instead of senderId.
     The sender info is preserved in SenderId field.

Apply after every OpenClaw update.
"""

import re
import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

def apply_patch(path):
    with open(path, "r") as f:
        content = f.read()

    old = "\t\tFrom: senderId,\n\t\tTo: chatId,\n\t\tSenderId: senderId,"
    new = "\t\tFrom: isGroup ? chatId : senderId,\n\t\tTo: chatId,\n\t\tSenderId: senderId,"

    if new in content:
        print(f"✅ Patch already applied to {path}")
        return False

    if old not in content:
        print(f"⚠️ Cannot find target code in {path} — may need manual review")
        return False

    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print(f"🔧 Patch applied to {path}")
    return True

if __name__ == "__main__":
    changed = False
    for suffix in ["", ".bak"]:
        p = SDK_PATH + suffix
        try:
            if apply_patch(p):
                changed = True
        except FileNotFoundError:
            pass

    if changed:
        print("\n⚠️ Restart required: openclaw gateway restart")
    sys.exit(0)
