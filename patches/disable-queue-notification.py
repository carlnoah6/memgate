#!/usr/bin/env python3
"""
Fix: Disable the misleading "⏳ 收到，前一条消息还在处理中" queue notification.

Bug: A 3-second setTimeout fires if `replyStarted` hasn't been set yet.
     With thinking models (Claude Opus + thinking), the LLM often takes >3s
     to start generating output (system prompt construction, thinking phase).
     This causes the notification to fire even when there IS no queue — 
     it's just normal processing latency.

Fix: Disable the timer entirely. The streaming card already provides
     real-time feedback (thinking status, tool status).

Apply after every OpenClaw update.
"""

import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

OLD = '''\t/* ── Patch: Queue notification ── */
\tlet queueNotified = false;
\tlet replyStarted = false;
\tconst queueTimer = setTimeout(async () => {
\t\tif (!replyStarted && !queueNotified) {
\t\t\tqueueNotified = true;
\t\t\ttry {
\t\t\t\tawait sendMessageFeishu(client, chatId, { text: "⏳ 收到，前一条消息还在处理中，请稍候…" }, { msgType: "text", receiveIdType: "chat_id" });
\t\t\t\tlogger$1.debug(`Sent queue notification for chat ${chatId}`);
\t\t\t} catch (err) {
\t\t\t\tlogger$1.debug(`Failed to send queue notification: ${err}`);
\t\t\t}
\t\t}
\t}, 3000);
\t/* ── End patch ── */'''

NEW = '''\t/* ── Patch: Queue notification (DISABLED — causes false positives with thinking models) ── */
\tlet queueNotified = false;
\tlet replyStarted = false;
\tconst queueTimer = null; /* Timer disabled: streaming card provides real-time feedback */
\t/* ── End patch ── */'''

def apply_patch(path):
    with open(path, "r") as f:
        content = f.read()

    if NEW in content:
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
        try:
            if apply_patch(p):
                changed = True
        except FileNotFoundError:
            pass

    if changed:
        print("\n⚠️ Restart required: bash scripts/restart-gateway.sh \"disable queue notification\"")
    sys.exit(0)
