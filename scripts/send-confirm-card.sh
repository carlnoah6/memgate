#!/bin/bash
# 发送确认卡片到 Lark 聊天
# 用法: send-confirm-card.sh <chat_id> <title> <content> [button1_label:button1_value] [button2_label:button2_value] ...
# 示例: send-confirm-card.sh oc_xxx "确认重启" "要重启 Gateway 吗？" "✅ 执行:approve" "❌ 取消:reject"
# 
# 如果不传按钮参数，默认生成 ✅确认 / ❌取消 两个按钮
# 用户点击后，Luna 会收到: [按钮] <value>

set -e

CHAT_ID="$1"
TITLE="$2"
CONTENT="$3"
shift 3 || { echo "用法: $0 <chat_id> <title> <content> [label:value ...]"; exit 1; }

# 获取 tenant_access_token via lark_common
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TENANT_TOKEN=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from lark_common import get_tenant_token; print(get_tenant_token())")

# 构建按钮 JSON
BUTTONS="[]"
if [ $# -gt 0 ]; then
  # 用传入的按钮参数
  BUTTON_ARGS=("$@")
  BUTTONS=$(python3 -c "
import json, sys
buttons = []
args = sys.argv[1:]
colors = ['primary', 'danger', 'default', 'default', 'default']
for i, arg in enumerate(args):
    parts = arg.split(':', 1)
    label = parts[0]
    value = parts[1] if len(parts) > 1 else parts[0]
    color = colors[i] if i < len(colors) else 'default'
    buttons.append({
        'tag': 'button',
        'text': {'content': label, 'tag': 'plain_text'},
        'type': color,
        'value': {'action': value}
    })
print(json.dumps(buttons))
" "${BUTTON_ARGS[@]}")
else
  # 默认按钮
  BUTTONS='[{"tag":"button","text":{"content":"✅ 确认","tag":"plain_text"},"type":"primary","value":{"action":"approve"}},{"tag":"button","text":{"content":"❌ 取消","tag":"plain_text"},"type":"danger","value":{"action":"reject"}}]'
fi

# 构建卡片 JSON
CARD_JSON=$(python3 -c "
import json, sys
title = sys.argv[1]
content = sys.argv[2]
buttons = json.loads(sys.argv[3])
card = {
    'header': {
        'title': {'content': title, 'tag': 'plain_text'},
        'template': 'blue'
    },
    'elements': [
        {'tag': 'markdown', 'content': content},
        {'tag': 'action', 'actions': buttons}
    ]
}
print(json.dumps(card, ensure_ascii=False))
" "$TITLE" "$CONTENT" "$BUTTONS")

# 发送
RESULT=$(curl -s -X POST "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id" \
  -H "Authorization: Bearer $TENANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, sys
print(json.dumps({
    'receive_id': sys.argv[1],
    'msg_type': 'interactive',
    'content': sys.argv[2]
}))
" "$CHAT_ID" "$CARD_JSON")")

CODE=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('code', -1))")
if [ "$CODE" = "0" ]; then
  MSG_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('message_id',''))")
  echo "OK: $MSG_ID"
else
  echo "ERROR: $RESULT" >&2
  exit 1
fi
