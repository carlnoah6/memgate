#!/bin/bash
# 飞书消息发送脚本 — 给子任务用
# 用法: ./lark-send-message.sh <chat_id> "<消息内容>"
#   或: echo "长消息内容" | ./lark-send-message.sh <chat_id> -
# 例: ./lark-send-message.sh oc_453c88ec52dd029845c46249837e3ba0 "✅ 研究完成！"

CHAT_ID="$1"
MESSAGE="$2"

if [ -z "$CHAT_ID" ]; then
    echo "Usage: $0 <chat_id> <message>"
    echo "   or: echo 'message' | $0 <chat_id> -"
    exit 1
fi

# 支持 stdin 输入（用 - 表示从 stdin 读取）
if [ "$MESSAGE" = "-" ] || [ -z "$MESSAGE" ]; then
    if [ -t 0 ]; then
        echo "ERROR: No message provided and stdin is a terminal"
        exit 1
    fi
    MESSAGE=$(cat)
fi

if [ -z "$MESSAGE" ]; then
    echo "ERROR: Empty message"
    exit 1
fi

# 用环境变量传递参数给 Python，避免 shell 转义问题
export LARK_CHAT_ID="$CHAT_ID"
export LARK_MESSAGE="$MESSAGE"
export LARK_APP_ID="cli_a90c3a6163785ed2"
export LARK_APP_SECRET="***LARK_SECRET_REMOVED***"

python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.error

chat_id = os.environ["LARK_CHAT_ID"]
app_id = os.environ["LARK_APP_ID"]
app_secret = os.environ["LARK_APP_SECRET"]
message = os.environ["LARK_MESSAGE"]

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

# 发送消息 — json.dumps 自动处理换行、引号等特殊字符
send_body = json.dumps({
    "receive_id": chat_id,
    "msg_type": "text",
    "content": json.dumps({"text": message})
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
