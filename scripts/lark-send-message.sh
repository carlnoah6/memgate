#!/bin/bash
# 飞书消息发送脚本（支持 text 和 post 富文本格式）
# 用法:
#   ./lark-send-message.sh <chat_id> "纯文本消息"
#   ./lark-send-message.sh <chat_id> - < message.txt          (stdin 纯文本)
#   ./lark-send-message.sh <chat_id> --post < report.md       (stdin markdown → post 富文本)
#   ./lark-send-message.sh <chat_id> --post-json '{"zh_cn":...}'  (直接 post JSON)

CHAT_ID="$1"
MODE="$2"
MESSAGE="$3"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$CHAT_ID" ]; then
    echo "Usage: $0 <chat_id> <message>"
    echo "   or: echo 'message' | $0 <chat_id> -"
    echo "   or: cat report.md | $0 <chat_id> --post"
    echo "   or: $0 <chat_id> --post-json '{\"zh_cn\":{...}}'"
    exit 1
fi

MSG_TYPE="text"
POST_JSON=""

if [ "$MODE" = "--post" ]; then
    # Read markdown from stdin, convert to post format
    MSG_TYPE="post"
    POST_JSON=$(python3 "$SCRIPT_DIR/md-to-lark-post.py")
    MESSAGE=""
elif [ "$MODE" = "--post-json" ]; then
    # Direct post JSON
    MSG_TYPE="post"
    POST_JSON="$MESSAGE"
    MESSAGE=""
elif [ "$MODE" = "-" ]; then
    # Plain text from stdin
    MESSAGE=$(cat)
elif [ -n "$MODE" ] && [ "$MODE" != "-" ] && [ "$MODE" != "--post" ] && [ "$MODE" != "--post-json" ]; then
    # MODE is actually the message text (2-arg call: script <chat_id> "message")
    MESSAGE="$MODE"
fi

if [ "$MSG_TYPE" = "text" ] && [ -z "$MESSAGE" ]; then
    if [ -t 0 ]; then
        echo "ERROR: No message provided and stdin is a terminal"
        exit 1
    fi
    MESSAGE=$(cat)
fi

if [ "$MSG_TYPE" = "text" ] && [ -z "$MESSAGE" ]; then
    echo "ERROR: Empty message"
    exit 1
fi

if [ "$MSG_TYPE" = "post" ] && [ -z "$POST_JSON" ]; then
    echo "ERROR: Empty post content"
    exit 1
fi

# 用环境变量传递参数给 Python（使用 lark_common.py）
export LARK_CHAT_ID="$CHAT_ID"
export LARK_MESSAGE="$MESSAGE"
export LARK_MSG_TYPE="$MSG_TYPE"
export LARK_POST_JSON="$POST_JSON"
export LARK_SCRIPT_DIR="$SCRIPT_DIR"

python3 << 'PYEOF'
import os, sys

sys.path.insert(0, os.environ.get("LARK_SCRIPT_DIR", "/home/ubuntu/.openclaw/workspace/scripts"))
from lark_common import send_message, get_tenant_token, lark_api

chat_id = os.environ["LARK_CHAT_ID"]
msg_type = os.environ["LARK_MSG_TYPE"]

try:
    if msg_type == "post":
        content = os.environ["LARK_POST_JSON"]
        result = lark_api(
            "POST",
            "/im/v1/messages?receive_id_type=chat_id",
            body={
                "receive_id": chat_id,
                "msg_type": "post",
                "content": content,
            },
            token=get_tenant_token(),
        )
        print("OK: Message sent successfully")
    elif msg_type == "text":
        send_message(chat_id, os.environ["LARK_MESSAGE"])
        print("OK: Message sent successfully")
    else:
        print(f"ERROR: Unknown msg_type: {msg_type}", file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
