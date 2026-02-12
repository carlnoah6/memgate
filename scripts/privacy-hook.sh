#!/bin/bash
# Privacy Guard — OpenClaw Hook
#
# Called at session start to inject privacy context into system prompt.
#
# Usage:
#   ./scripts/privacy-hook.sh <channel-type> <participants>
#
# Examples:
#   ./scripts/privacy-hook.sh dm "carl"
#   ./scripts/privacy-hook.sh group "carl,alex,bob"
#
# Returns: Privacy context text (to append to system prompt)

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="${WORKSPACE}/scripts/privacy-check.py"

CHANNEL_TYPE="${1:-dm}"
PARTICIPANTS="${2:-carl}"

# Get context as JSON and extract the system_prompt_injection field
RESULT=$(python3 "$SCRIPT" context \
    --channel-type "$CHANNEL_TYPE" \
    --participants "$PARTICIPANTS" 2>/dev/null) || {
    echo "⚠️ Privacy Guard 不可用，使用默认规则"
    exit 0
}

# Extract the system_prompt_injection field
echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('system_prompt_injection', ''))
" 2>/dev/null || echo "⚠️ Privacy Guard 解析错误"
