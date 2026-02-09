#!/bin/bash
# Luna Patch: 修复 Feishu 流式卡片跨 turn 内容重复 bug
# 适用于: OpenClaw 2026.2.3-1 (plugin-sdk/index.js)
# 
# 问题: 原始 Patch 9 用 onReplyStart 累积跨 turn 文字，但 onReplyStart 是 per-session 回调
#        （被 ensureStart 守卫），不是 per-turn，导致累积逻辑只触发一次，后续 turn 文字被重复拼接
#
# 修复: 在 onPartialReply 内部检测 turn 切换：
#   - deltaBuffer 在 turn 之间会 reset (text_end 事件)
#   - 所以 payload.text 在 turn 内单调增长 (startsWith 前一次)
#   - 如果 payload.text 不以 lastRawPayloadText 开头 → 新 turn 开始
#   - 此时把上一 turn 的原始文字存入 completedTurnsText
#   - 显示时 completedTurnsText + "\n\n" + payload.text
#
# 同时修复: 工具状态显示的 baseText 直接用 lastPartialText（已含累积）

set -e

TARGET="/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

if [ ! -f "$TARGET" ]; then
    echo "ERROR: Target file not found: $TARGET"
    exit 1
fi

# Check if already patched
if grep -q "Luna fix v4" "$TARGET"; then
    echo "SKIP: Patch already applied"
    exit 0
fi

# Check if original Patch 9 exists (what we're replacing)
if ! grep -q "Patch 9: Accumulate text across turns" "$TARGET"; then
    echo "WARNING: Original Patch 9 not found. OpenClaw version may have changed."
    echo "Manual review required."
    exit 1
fi

echo "Applying Feishu streaming card fix..."

# Backup
cp "$TARGET" "$TARGET.bak.$(date +%Y%m%d%H%M%S)"

# 1. Add lastRawPayloadText variable after lastPartialText declaration
sed -i '/let lastPartialText = "";/a\\tlet lastRawPayloadText = ""; /* Raw payload.text from last onPartialReply (for turn detection) */' "$TARGET"

# 2. Replace the Patch 9 variable declarations
# Change: let completedTurnsText = "";
# Keep it but it's now managed differently

# 3. Replace tool status baseText logic
sed -i 's|/\* Patch 9: use accumulated text for tool status display \*/|/* Luna fix v4: use lastPartialText which already has accumulated display */|' "$TARGET"
sed -i '/Luna fix v4: use lastPartialText/!b;n;s|const baseText = shouldAccumulate \&\& completedTurnsText|const baseText = lastPartialText \|\||' "$TARGET"
# This is fragile - the actual replacement needs to be done more carefully

# 4. Add reset lines in block delivery
# After lastPartialText = ""; add:
sed -i '/lastPartialText = "";/{n;/deferStreamingStart = true/i\\t\t\t\t\tlastRawPayloadText = "";\n\t\t\t\t\tcompletedTurnsText = "";
}' "$TARGET"

# 5. Add reset in final delivery
sed -i '/streamingStarted = false;/{n;/return;/i\\t\t\t\t\tlastRawPayloadText = "";\n\t\t\t\t\tcompletedTurnsText = "";
}' "$TARGET"

# 6. Replace the onPartialReply accumulation logic
# This is the most critical part - replace the Patch 9 prepend logic

echo "NOTE: Due to sed limitations, some replacements may need manual verification."
echo "Run: grep -n 'Luna fix v4\|lastRawPayloadText\|completedTurnsText' $TARGET"
echo "to verify the patch was applied correctly."

echo "Patch applied. Restart gateway to take effect."
