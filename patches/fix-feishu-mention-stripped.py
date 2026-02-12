#!/usr/bin/env python3
"""
Fix: Feishu @mention information is completely stripped from message text.

Bug: In processFeishuMessage(), the code replaces all mention.key placeholders
     (e.g. "@_user_1") with empty string "", removing ALL @mention context.
     When Carl sends "@QJunyi 你来lark后台创建下bot？", Luna only receives
     "你来lark后台创建下bot？" — losing who was being addressed.

Root cause (line ~71026 in plugin-sdk/index.js):
    for (const mention of mentions) if (mention.key) text = text.replace(mention.key, "").trim();

Fix: Replace mention.key with "@mention.name" to preserve mention context.
     "@_user_1 你来lark后台创建下bot？" → "@QJunyi 你来lark后台创建下bot？"

     Also adds MentionedUsers to the context object so downstream routing
     can distinguish bot mentions from user mentions.

Apply after every OpenClaw update.
"""

import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

# The exact old code that strips mentions
OLD_MENTION_STRIP = '\tfor (const mention of mentions) if (mention.key) text = text.replace(mention.key, "").trim();'

# New code: replace mention keys with @Name instead of stripping them
NEW_MENTION_REPLACE = """\t/* ── Patch: Preserve @mention names instead of stripping them ── */
\tfor (const mention of mentions) {
\t\tif (mention.key) {
\t\t\tconst replaceName = mention.name ? `@${mention.name}` : "";
\t\t\ttext = text.replace(mention.key, replaceName).trim();
\t\t}
\t}
\t/* ── End mention patch ── */"""

# Also add MentionedUsers to ctx
OLD_CTX_WASMENTION = "\t\tWasMentioned: isGroup ? wasMentioned : void 0\n\t};"

NEW_CTX_WASMENTION = """\t\tWasMentioned: isGroup ? wasMentioned : void 0,
\t\tMentionedUsers: mentions.filter((m) => m.name).map((m) => ({
\t\t\tname: m.name,
\t\t\tid: m.id?.open_id || m.id?.user_id || m.id?.union_id || "unknown"
\t\t}))
\t};"""


def apply_patch(path):
    with open(path, "r") as f:
        content = f.read()

    changed = False

    # Patch 1: mention key replacement
    if "Preserve @mention names" in content:
        print(f"  ✅ Mention replacement already patched in {path}")
    elif OLD_MENTION_STRIP not in content:
        print(f"  ⚠️ Cannot find mention stripping code in {path}")
        print(f"     Expected: {OLD_MENTION_STRIP[:80]}...")
    else:
        content = content.replace(OLD_MENTION_STRIP, NEW_MENTION_REPLACE)
        changed = True
        print(f"  🔧 Patched mention key replacement in {path}")

    # Patch 2: add MentionedUsers to ctx
    if "MentionedUsers:" in content:
        print(f"  ✅ MentionedUsers already in ctx in {path}")
    elif OLD_CTX_WASMENTION not in content:
        print(f"  ⚠️ Cannot find WasMentioned ctx block in {path}")
    else:
        content = content.replace(OLD_CTX_WASMENTION, NEW_CTX_WASMENTION)
        changed = True
        print(f"  🔧 Added MentionedUsers to ctx in {path}")

    if changed:
        with open(path, "w") as f:
            f.write(content)
        return True
    return False


if __name__ == "__main__":
    print("Feishu @mention preservation patch")
    print("=" * 50)

    changed = False
    for suffix in [""]:
        p = SDK_PATH + suffix
        try:
            if apply_patch(p):
                changed = True
        except FileNotFoundError:
            print(f"  ❌ File not found: {p}")

    if changed:
        print("\n✅ Patch applied successfully!")
        print("⚠️  Restart required: openclaw gateway restart")
    else:
        print("\nNo changes made.")
    sys.exit(0)
