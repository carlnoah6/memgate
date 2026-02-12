#!/usr/bin/env python3
"""
Fix: Feishu streaming card UX improvements (3 fixes).

Fix 1: Remove card title "Luna" (redundant with bot name in chat)
  - Remove options.botName from streamingSession.start() calls (3 places)

Fix 2: close() deletes card for short/silent content, keeps for long content
  - Short (< 100 chars) or silent (NO_REPLY/HEARTBEAT_OK): delete card
  - Long content: close normally (keep for history/process viewing)

Fix 3: Final reply always sends a text message
  - Remove `return` from the `info?.kind === "final"` branch in deliver()
  - After close(), streamingSession.isActive() returns false, so sendMessageFeishu executes

Apply after every OpenClaw update.
"""

import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

PATCHES = []

# ── Fix 1: Remove title from streamingSession.start() calls (3 places) ──
PATCHES.append({
    "name": "Fix 1: Remove card title",
    "check": lambda c: 'streamingSession.start(chatId, "chat_id", options.botName)' not in c,
    "old": 'streamingSession.start(chatId, "chat_id", options.botName)',
    "new": 'streamingSession.start(chatId, "chat_id")',
    "replace_all": True,
})

# ── Fix 2: close() — short/silent delete, long keep ──
# This patch handles two possible source states:
#   (a) Original OpenClaw code (Patch 7 style)
#   (b) Previous "always delete" patch

# Check: is our new version already applied?
FIX2_MARKER = "Delete card for silent/short content, keep for long content"

FIX2_NEW = (
    '\t\tconst text = finalText ?? this.state.currentText;\n'
    '\t\t/* ── Patch: Delete card for silent/short content, keep for long content ── */\n'
    '\t\tconst isSilentContent = !text || !text.trim() || /^\\s*NO_REPLY\\s*$/i.test(text) || /^\\s*HEARTBEAT_OK\\s*$/i.test(text);\n'
    '\t\tconst isShortContent = text && text.trim().length > 0 && text.trim().length < 100;\n'
    '\t\tif ((isSilentContent || isShortContent) && this.state.messageId) {\n'
    '\t\t\ttry {\n'
    '\t\t\t\tawait this.client.im.message.delete({ path: { message_id: this.state.messageId } });\n'
    '\t\t\t\tlogger$2.info(`Deleted short/silent streaming card: messageId=${this.state.messageId}`);\n'
    '\t\t\t} catch (err) {\n'
    '\t\t\t\tlogger$2.debug(`Failed to delete streaming card: ${String(err)}`);\n'
    '\t\t\t}\n'
    '\t\t\treturn;\n'
    '\t\t}\n'
    '\t\t/* Long content: finalize card normally (keep visible for history) */\n'
    '\t\tthis.state.sequence += 1;\n'
    '\t\ttry {\n'
    '\t\t\tawait updateStreamingCardText(this.credentials, this.state.cardId, this.state.elementId, text || " ", this.state.sequence);\n'
    '\t\t\tthis.state.sequence += 1;\n'
    '\t\t\tawait closeStreamingMode(this.credentials, this.state.cardId, this.state.sequence, summary ?? truncateForSummary(text));\n'
    '\t\t\tlogger$2.info(`Closed streaming session: cardId=${this.state.cardId}`);\n'
    '\t\t} catch (err) {\n'
    '\t\t\tlogger$2.error(`Failed to close streaming session: ${String(err)}`);\n'
    '\t\t}'
)

# Source (a): original OpenClaw Patch 7 style
FIX2_OLD_ORIGINAL = (
    '\t\tconst text = finalText ?? this.state.currentText;\n'
    '\t\t/* ── Patch 7: Delete zombie "Thinking..." cards ── */\n'
    '\t\t/* ── Patch: Also delete cards showing silent reply tokens (NO_REPLY, HEARTBEAT_OK) ── */\n'
    '\t\tconst isSilentContent = !text || !text.trim() || /^\\s*NO_REPLY\\s*$/i.test(text) || /^\\s*HEARTBEAT_OK\\s*$/i.test(text);\n'
    '\t\tif (isSilentContent && this.state.messageId) {\n'
    '\t\t\ttry {\n'
    '\t\t\t\tawait this.client.im.message.delete({ path: { message_id: this.state.messageId } });\n'
    '\t\t\t\tlogger$2.info(`Deleted empty streaming card (no content): messageId=${this.state.messageId}`);\n'
    '\t\t\t} catch (err) {\n'
    '\t\t\t\tlogger$2.debug(`Failed to delete empty streaming card: ${String(err)}`);\n'
    '\t\t\t}\n'
    '\t\t\treturn;\n'
    '\t\t}\n'
    '\t\t/* ── End Patch 7 ── */\n'
    '\t\tthis.state.sequence += 1;\n'
    '\t\ttry {\n'
    '\t\t\tawait updateStreamingCardText(this.credentials, this.state.cardId, this.state.elementId, text || " ", this.state.sequence);\n'
    '\t\t\tthis.state.sequence += 1;\n'
    '\t\t\tawait closeStreamingMode(this.credentials, this.state.cardId, this.state.sequence, summary ?? truncateForSummary(text));\n'
    '\t\t\tlogger$2.info(`Closed streaming session: cardId=${this.state.cardId}`);\n'
    '\t\t} catch (err) {\n'
    '\t\t\tlogger$2.error(`Failed to close streaming session: ${String(err)}`);\n'
    '\t\t}'
)

# Source (b): "always delete" patch (previous version of this patch)
FIX2_OLD_ALWAYS_DELETE = (
    '\t\t/* ── Patch: Always delete streaming card — card is process indicator only ── */\n'
    '\t\tif (this.state.messageId) {\n'
    '\t\t\ttry {\n'
    '\t\t\t\tawait this.client.im.message.delete({ path: { message_id: this.state.messageId } });\n'
    '\t\t\t\tlogger$2.info(`Deleted streaming card after close: messageId=${this.state.messageId}`);\n'
    '\t\t\t} catch (err) {\n'
    '\t\t\t\tlogger$2.debug(`Failed to delete streaming card: ${String(err)}`);\n'
    '\t\t\t}\n'
    '\t\t}'
)


def apply_fix2(content):
    """Apply Fix 2 with multiple source pattern matching"""
    if FIX2_MARKER in content:
        print("  ✅ Fix 2: close() short/long split: already applied")
        return content, False

    if FIX2_OLD_ALWAYS_DELETE in content:
        content = content.replace(FIX2_OLD_ALWAYS_DELETE, FIX2_NEW, 1)
        print("  🔧 Fix 2: close() short/long split: applied (replaced 'always delete' version)")
        return content, True

    if FIX2_OLD_ORIGINAL in content:
        content = content.replace(FIX2_OLD_ORIGINAL, FIX2_NEW, 1)
        print("  🔧 Fix 2: close() short/long split: applied (replaced original Patch 7)")
        return content, True

    print("  ⚠️ Fix 2: close() target code not found — may need manual review")
    return content, False


# ── Fix 3: Remove return from final branch ──
PATCHES.append({
    "name": "Fix 3: Don't return after final close",
    "check": lambda c: "// Don't return — let sendMessageFeishu send the final text message" in c,
    "old": (
        '\t\t\t\tif (streamingSession?.isActive() && info?.kind === "final") {\n'
        '\t\t\t\t\tawait streamingSession.close(payload.text);\n'
        '\t\t\t\t\tstreamingStarted = false;\n'
        '\t\t\t\t\tlastRawPayloadText = "";\n'
        '\t\t\t\t\tcompletedTurnsText = "";\n'
        '\t\t\t\t\treturn;\n'
        '\t\t\t\t}'
    ),
    "new": (
        '\t\t\t\tif (streamingSession?.isActive() && info?.kind === "final") {\n'
        '\t\t\t\t\tawait streamingSession.close(payload.text);\n'
        '\t\t\t\t\tstreamingStarted = false;\n'
        '\t\t\t\t\tlastRawPayloadText = "";\n'
        '\t\t\t\t\tcompletedTurnsText = "";\n'
        "\t\t\t\t\t// Don't return — let sendMessageFeishu send the final text message\n"
        '\t\t\t\t}'
    ),
    "replace_all": False,
})


def apply_patches(path):
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
        return False

    applied = 0
    skipped = 0

    # Fix 1: title removal
    patch1 = {
        "name": "Fix 1: Remove card title",
        "check": lambda c: 'streamingSession.start(chatId, "chat_id", options.botName)' not in c,
        "old": 'streamingSession.start(chatId, "chat_id", options.botName)',
        "new": 'streamingSession.start(chatId, "chat_id")',
    }
    if patch1["check"](content):
        print(f"  ✅ {patch1['name']}: already applied")
        skipped += 1
    elif patch1["old"] in content:
        count = content.count(patch1["old"])
        content = content.replace(patch1["old"], patch1["new"])
        print(f"  🔧 {patch1['name']}: applied ({count} replacements)")
        applied += 1
    else:
        print(f"  ⚠️ {patch1['name']}: target not found")

    # Fix 2: close() short/long split
    content, fix2_applied = apply_fix2(content)
    if fix2_applied:
        applied += 1
    else:
        skipped += 1

    # Fix 3: remove return from final
    for patch in PATCHES:
        name = patch["name"]
        if patch["check"](content):
            print(f"  ✅ {name}: already applied")
            skipped += 1
            continue

        if patch["old"] not in content:
            print(f"  ⚠️ {name}: target code not found")
            continue

        content = content.replace(patch["old"], patch["new"], 1)
        print(f"  🔧 {name}: applied")
        applied += 1

    if applied > 0:
        with open(path, "w") as f:
            f.write(content)
        print(f"\n✅ {applied} patch(es) applied, {skipped} already present")
        return True
    elif skipped >= 3:
        print(f"\n✅ All patches already applied")
        return False
    else:
        print(f"\n⚠️ No patches applied")
        return False


if __name__ == "__main__":
    print(f"Patching {SDK_PATH} ...")
    changed = apply_patches(SDK_PATH)

    if changed:
        print("\n⚠️ Restart required: bash scripts/restart-gateway.sh \"fix streaming card UX\"")
    sys.exit(0)
