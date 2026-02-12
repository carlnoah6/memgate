#!/usr/bin/env bash
# send-diagram.sh — Generate a diagram and send to Lark chat
#
# Usage:
#   send-diagram.sh <chat_id> <diagram_text>
#   send-diagram.sh <chat_id> --file <file.d2|file.mmd>
#   echo "x -> y" | send-diagram.sh <chat_id> --stdin
#   send-diagram.sh --auto <message_id> --file <file.d2>  # auto-detect chat from message
#
# Environment variables:
#   DIAGRAM_TYPE  — d2 (default) | mermaid | graphviz | plantuml
#   D2_LAYOUT     — dagre (default) | elk
#   D2_THEME      — 1 (Neutral Grey, default) | 0 | 200 (dark) | ...
#   OUTPUT_FORMAT  — png (default) | svg
#
# Requires: d2 (~/.local/bin/d2), Lark Bot im:resource permission

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Handle --auto mode: resolve chat_id from message_id
if [ "${1:-}" = "--auto" ]; then
    MSG_ID="${2:?Usage: send-diagram.sh --auto <message_id> ...}"
    CHAT_ID=$(python3 "$SCRIPT_DIR/get-source-chat.py" "$MSG_ID")
    if [ -z "$CHAT_ID" ]; then
        echo "ERROR: Could not resolve chat_id from message $MSG_ID" >&2
        exit 1
    fi
    echo "🎯 Auto-detected chat: $CHAT_ID"
    shift 2
else
    CHAT_ID="${1:?Usage: send-diagram.sh <chat_id|--auto MSG_ID> <text|--file FILE|--stdin>}"
    shift
fi

APP_ID=""  # credentials managed by lark_common.py
APP_SECRET=""
DIAGRAM_TYPE="${DIAGRAM_TYPE:-d2}"
D2_LAYOUT="${D2_LAYOUT:-dagre}"
D2_THEME="${D2_THEME:-1}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-png}"
D2_BIN="${HOME}/.local/bin/d2"

# Read diagram source
if [[ "${1:-}" == "--file" ]]; then
    DIAGRAM_FILE="${2:?--file requires a path}"
    DIAGRAM_SRC=$(cat "$DIAGRAM_FILE")
    # Auto-detect type from extension
    case "$DIAGRAM_FILE" in
        *.d2) DIAGRAM_TYPE="d2" ;;
        *.mmd|*.mermaid) DIAGRAM_TYPE="mermaid" ;;
        *.dot|*.gv) DIAGRAM_TYPE="graphviz" ;;
        *.puml) DIAGRAM_TYPE="plantuml" ;;
    esac
elif [[ "${1:-}" == "--stdin" ]]; then
    DIAGRAM_SRC=$(cat)
else
    DIAGRAM_SRC="$*"
fi

if [[ -z "$DIAGRAM_SRC" ]]; then
    echo "❌ No diagram source provided" >&2
    exit 1
fi

TMPFILE=$(mktemp /tmp/diagram-XXXXXX.png)
trap "rm -f $TMPFILE /tmp/_diagram_src.*" EXIT

# ─── Render ───────────────────────────────────────────────
if [[ "$DIAGRAM_TYPE" == "d2" ]]; then
    # D2: local rendering
    SRCFILE=$(mktemp /tmp/_diagram_src.XXXXXX.d2)
    echo "$DIAGRAM_SRC" > "$SRCFILE"
    echo "🎨 Rendering D2 (layout=$D2_LAYOUT, theme=$D2_THEME)..." >&2
    "$D2_BIN" --layout="$D2_LAYOUT" --theme="$D2_THEME" --pad=40 "$SRCFILE" "$TMPFILE" >&2
else
    # Mermaid/GraphViz/PlantUML: Kroki.io cloud
    echo "🎨 Rendering $DIAGRAM_TYPE via Kroki.io..." >&2
    HTTP_CODE=$(curl -s -w "%{http_code}" -o "$TMPFILE" \
        -X POST "https://kroki.io/${DIAGRAM_TYPE}/${OUTPUT_FORMAT}" \
        -H "Content-Type: text/plain" \
        -H "User-Agent: Mozilla/5.0" \
        --data-binary @- <<< "$DIAGRAM_SRC")
    if [[ "$HTTP_CODE" != "200" ]]; then
        echo "❌ Kroki returned HTTP $HTTP_CODE" >&2
        cat "$TMPFILE" >&2
        exit 1
    fi
fi

SIZE=$(stat -c%s "$TMPFILE" 2>/dev/null || stat -f%z "$TMPFILE" 2>/dev/null)
echo "✅ Rendered: ${SIZE} bytes" >&2

# ─── Upload & Send ────────────────────────────────────────
TAT=$(python3 -c "import sys; sys.path.insert(0, '$(dirname "$0")'); from lark_common import get_tenant_token; print(get_tenant_token())")

IMAGE_KEY=$(curl -s -X POST "https://open.larksuite.com/open-apis/im/v1/images" \
    -H "Authorization: Bearer $TAT" \
    -F "image_type=message" \
    -F "image=@$TMPFILE" \
    | python3 -c "import sys,json;r=json.load(sys.stdin);print(r.get('data',{}).get('image_key',''))" 2>/dev/null)

if [[ -z "$IMAGE_KEY" ]]; then
    echo "❌ Image upload failed" >&2
    exit 1
fi

SEND_RESULT=$(curl -s -X POST "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id" \
    -H "Authorization: Bearer $TAT" \
    -H "Content-Type: application/json" \
    -d "{
        \"receive_id\": \"$CHAT_ID\",
        \"msg_type\": \"image\",
        \"content\": \"{\\\"image_key\\\": \\\"$IMAGE_KEY\\\"}\"
    }")

CODE=$(echo "$SEND_RESULT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('code',99))" 2>/dev/null)

if [[ "$CODE" == "0" ]]; then
    echo "✅ Sent to $CHAT_ID" >&2
    echo "$IMAGE_KEY"
else
    echo "❌ Send failed: $SEND_RESULT" >&2
    exit 1
fi
