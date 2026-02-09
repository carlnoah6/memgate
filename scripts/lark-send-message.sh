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
elif [ "$MODE" = "-" ] || [ -z "$MODE" ]; then
    # Plain text from stdin
    if [ "$MODE" = "-" ]; then
        MESSAGE=$(cat)
    fi
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

# 用环境变量传递参数给 Python
export LARK_CHAT_ID="$CHAT_ID"
export LARK_MESSAGE="$MESSAGE"
export LARK_MSG_TYPE="$MSG_TYPE"
export LARK_POST_JSON="$POST_JSON"
export LARK_APP_ID="cli_a90c3a6163785ed2"
export LARK_APP_SECRET="***LARK_SECRET_REMOVED***"

python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.error

chat_id = os.environ["LARK_CHAT_ID"]
app_id = os.environ["LARK_APP_ID"]
app_secret = os.environ["LARK_APP_SECRET"]
msg_type = os.environ["LARK_MSG_TYPE"]

BASE = "https://open.larksuite.com/open-apis"

# 获取 tenant_access_token
token_req = urllib.request.Request(
    f"{BASE}/auth/v3/tenant_access_token/internal",
    data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(token_req) as resp:
        token_data = json.loads(resp.read())
except Exception as e:
    print(f"ERROR: Failed to get token: {e}", file=sys.stderr)
    sys.exit(1)

tenant_token = token_data.get("tenant_access_token", "")
if not tenant_token:
    print(f"ERROR: No tenant_access_token in response: {token_data}", file=sys.stderr)
    sys.exit(1)

# 构建消息内容
if msg_type == "post":
    content = os.environ["LARK_POST_JSON"]
elif msg_type == "text":
    content = json.dumps({"text": os.environ["LARK_MESSAGE"]})
else:
    print(f"ERROR: Unknown msg_type: {msg_type}", file=sys.stderr)
    sys.exit(1)

# 发送消息
send_body = json.dumps({
    "receive_id": chat_id,
    "msg_type": msg_type,
    "content": content
})

send_req = urllib.request.Request(
    f"{BASE}/im/v1/messages?receive_id_type=chat_id",
    data=send_body.encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {tenant_token}"
    }
)

try:
    with urllib.request.urlopen(send_req) as resp:
        send_data = json.loads(resp.read())
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"ERROR: HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

code = send_data.get("code", -1)
if code == 0:
    print("OK: Message sent successfully")
else:
    print(f"ERROR: code={code} msg={send_data.get('msg', 'unknown')}", file=sys.stderr)
    sys.exit(1)
PYEOF
