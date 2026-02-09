#!/usr/bin/env python3
"""
Patch: Fix streaming card race condition (duplicate cards)

Root cause: onReplyStart, onPartialReply, and onReasoningStream are all async
callbacks that can call streamingSession.start() concurrently. Before the first
call's await completes, `streamingStarted` is still false and `this.state` is
still null, so subsequent calls also pass the guard and create duplicate cards.

Fix:
1. Add `_starting` flag to FeishuStreamingSession.start() to block concurrent calls
2. Set `streamingStarted = true` synchronously BEFORE awaiting start() in all callers
"""

import re

TARGET = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

def apply():
    with open(TARGET, "r") as f:
        code = f.read()

    changes = 0

    # === Fix 1: Add _starting guard to start() method ===
    old_start = '''\tasync start(receiveId, receiveIdType = "chat_id", title) {
\t\tif (this.state) {
\t\t\tlogger$2.warn("Streaming session already started");
\t\t\treturn;
\t\t}
\t\ttry {
\t\t\tconst { cardId } = await createStreamingCard(this.credentials, title);'''

    new_start = '''\tasync start(receiveId, receiveIdType = "chat_id", title) {
\t\t/* Patch: race condition guard — prevent concurrent start() calls */
\t\tif (this.state || this._starting) {
\t\t\tlogger$2.warn("Streaming session already started or starting");
\t\t\treturn;
\t\t}
\t\tthis._starting = true;
\t\t/* End patch */
\t\ttry {
\t\t\tconst { cardId } = await createStreamingCard(this.credentials, title);'''

    if old_start in code:
        code = code.replace(old_start, new_start, 1)
        changes += 1
        print("✅ Fix 1 applied: _starting guard in start()")
    elif "this._starting" in code and "race condition guard" in code:
        print("✅ Fix 1 already applied.")
    else:
        print("⚠️ Fix 1: Cannot find target code for start() method")

    # === Fix 1b: Reset _starting on error ===
    old_catch = '''\t\t} catch (err) {
\t\t\tlogger$2.error(`Failed to start streaming session: ${String(err)}`);
\t\t\tthrow err;
\t\t}
\t}
\t/**
\t* Update the streaming card with new text (appends to existing)'''

    new_catch = '''\t\t} catch (err) {
\t\t\tthis._starting = false; /* Patch: reset on failure */
\t\t\tlogger$2.error(`Failed to start streaming session: ${String(err)}`);
\t\t\tthrow err;
\t\t}
\t}
\t/**
\t* Update the streaming card with new text (appends to existing)'''

    if old_catch in code:
        code = code.replace(old_catch, new_catch, 1)
        changes += 1
        print("✅ Fix 1b applied: reset _starting on error")
    elif "this._starting = false; /* Patch: reset on failure */" in code:
        print("✅ Fix 1b already applied.")
    else:
        print("⚠️ Fix 1b: Cannot find target code for catch block")

    # === Fix 2: Set streamingStarted synchronously in onReplyStart ===
    old_reply_start = '''if (streamingSession && !streamingStarted) try {
\t\t\t\tawait streamingSession.start(chatId, "chat_id", options.botName);
\t\t\t\tstreamingStarted = true;
\t\t\t\tlogger$1.debug(`Started streaming card for chat ${chatId}`);
\t\t\t} catch (err) {
\t\t\t\tlogger$1.warn(`Failed to start streaming card: ${formatErrorMessage$1(err)}`);
\t\t\t}'''

    new_reply_start = '''if (streamingSession && !streamingStarted) {
\t\t\t\tstreamingStarted = true; /* Patch: set sync before await to prevent race */
\t\t\t\ttry {
\t\t\t\t\tawait streamingSession.start(chatId, "chat_id", options.botName);
\t\t\t\t\tlogger$1.debug(`Started streaming card for chat ${chatId}`);
\t\t\t\t} catch (err) {
\t\t\t\t\tstreamingStarted = false; /* Patch: reset on failure */
\t\t\t\t\tlogger$1.warn(`Failed to start streaming card: ${formatErrorMessage$1(err)}`);
\t\t\t\t}
\t\t\t}'''

    if old_reply_start in code:
        code = code.replace(old_reply_start, new_reply_start, 1)
        changes += 1
        print("✅ Fix 2 applied: sync streamingStarted in onReplyStart")
    elif 'streamingStarted = true; /* Patch: set sync before await to prevent race */' in code:
        print("✅ Fix 2 already applied.")
    else:
        print("⚠️ Fix 2: Cannot find target code for onReplyStart")

    # === Fix 3: Set streamingStarted synchronously in onPartialReply ===
    old_partial = '''if (!streamingSession.isActive() && !streamingStarted) {
\t\t\t\t\ttry {
\t\t\t\t\t\tawait streamingSession.start(chatId, "chat_id", options.botName);
\t\t\t\t\t\tstreamingStarted = true;
\t\t\t\t\t} catch (err) {
\t\t\t\t\t\tlogger$1.warn(`Failed to lazy-start streaming card: ${err}`);
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tif (!streamingSession.isActive()) return;
\t\t\t\t/* Luna fix v4'''

    new_partial = '''if (!streamingSession.isActive() && !streamingStarted) {
\t\t\t\t\tstreamingStarted = true; /* Patch: set sync before await to prevent race */
\t\t\t\t\ttry {
\t\t\t\t\t\tawait streamingSession.start(chatId, "chat_id", options.botName);
\t\t\t\t\t} catch (err) {
\t\t\t\t\t\tstreamingStarted = false; /* Patch: reset on failure */
\t\t\t\t\t\tlogger$1.warn(`Failed to lazy-start streaming card: ${err}`);
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tif (!streamingSession.isActive()) return;
\t\t\t\t/* Luna fix v4'''

    if old_partial in code:
        code = code.replace(old_partial, new_partial, 1)
        changes += 1
        print("✅ Fix 3 applied: sync streamingStarted in onPartialReply")
    elif new_partial in code:
        print("✅ Fix 3 already applied.")
    else:
        print("⚠️ Fix 3: Cannot find target code for onPartialReply")

    # === Fix 4: Set streamingStarted synchronously in onReasoningStream ===
    # Find the onReasoningStream lazy-start block
    old_reasoning = '''onReasoningStream: streamingSession ? async (payload) => {
\t\t\t\tif (!streamingSession || !payload.text) return;
\t\t\t\tdeferStreamingStart = false; /* Patch 8 */
\t\t\t\tif (!streamingSession.isActive() && !streamingStarted) {
\t\t\t\t\ttry {
\t\t\t\t\t\tawait streamingSession.start(chatId, "chat_id", options.botName);
\t\t\t\t\t\tstreamingStarted = true;
\t\t\t\t\t} catch (err) {
\t\t\t\t\t\tlogger$1.warn(`Failed to lazy-start streaming card: ${err}`);
\t\t\t\t\t\treturn;
\t\t\t\t\t}'''

    new_reasoning = '''onReasoningStream: streamingSession ? async (payload) => {
\t\t\t\tif (!streamingSession || !payload.text) return;
\t\t\t\tdeferStreamingStart = false; /* Patch 8 */
\t\t\t\tif (!streamingSession.isActive() && !streamingStarted) {
\t\t\t\t\tstreamingStarted = true; /* Patch: set sync before await to prevent race */
\t\t\t\t\ttry {
\t\t\t\t\t\tawait streamingSession.start(chatId, "chat_id", options.botName);
\t\t\t\t\t} catch (err) {
\t\t\t\t\t\tstreamingStarted = false; /* Patch: reset on failure */
\t\t\t\t\t\tlogger$1.warn(`Failed to lazy-start streaming card: ${err}`);
\t\t\t\t\t\treturn;
\t\t\t\t\t}'''

    if old_reasoning in code:
        code = code.replace(old_reasoning, new_reasoning, 1)
        changes += 1
        print("✅ Fix 4 applied: sync streamingStarted in onReasoningStream")
    elif new_reasoning in code:
        print("✅ Fix 4 already applied.")
    else:
        print("⚠️ Fix 4: Cannot find target code for onReasoningStream")

    if changes > 0:
        with open(TARGET, "w") as f:
            f.write(code)
        print(f"\n🔧 Applied {changes} fixes. Restart required.")
    else:
        print("\n✅ All patches already applied.")

    return changes

if __name__ == "__main__":
    apply()
