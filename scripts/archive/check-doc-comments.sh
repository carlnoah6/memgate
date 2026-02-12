#!/bin/bash
# 检查 Lark 文档的未解决评论
# 返回未解决评论的 JSON 列表

APP_ID="cli_a90c3a6163785ed2"
APP_SECRET="***LARK_SECRET_REMOVED***"

# 获取 token
TOKEN=$(curl -s -X POST "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "{\"app_id\": \"$APP_ID\", \"app_secret\": \"$APP_SECRET\"}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))")

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to get token"
  exit 1
fi

# 已知文档列表文件
DOC_LIST="/home/ubuntu/.openclaw/workspace/data/tracked-docs.json"

if [ ! -f "$DOC_LIST" ]; then
  echo "[]"
  exit 0
fi

# 检查每个文档的未解决评论
export TOKEN
python3 << 'PYEOF'
import json, subprocess, sys, os

doc_list_path = "/home/ubuntu/.openclaw/workspace/data/tracked-docs.json"
state_path = "/home/ubuntu/.openclaw/workspace/data/comment-state.json"
token = os.environ.get("TOKEN", sys.argv[1] if len(sys.argv) > 1 else "")

# 读取文档列表
with open(doc_list_path) as f:
    docs = json.load(f)

# 读取已知评论状态
known_comments = {}
if os.path.exists(state_path):
    with open(state_path) as f:
        known_comments = json.load(f)

new_comments = []

for doc in docs:
    doc_id = doc["id"]
    doc_title = doc.get("title", doc_id)
    
    # 获取评论
    import urllib.request
    req = urllib.request.Request(
        f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_id}/comments?file_type=docx",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"ERROR checking {doc_id}: {e}", file=sys.stderr)
        continue
    
    if data.get("code") != 0:
        continue
    
    items = data.get("data", {}).get("items", [])
    
    for item in items:
        comment_id = item["comment_id"]
        is_solved = item.get("is_solved", False)
        
        if not is_solved and comment_id not in known_comments.get(doc_id, []):
            # 提取评论内容
            replies = item.get("reply_list", {}).get("replies", [])
            comment_text = ""
            for reply in replies:
                elements = reply.get("content", {}).get("elements", [])
                for el in elements:
                    if el.get("type") == "text_run":
                        comment_text += el.get("text_run", {}).get("text", "")
            
            quote = item.get("quote", "")
            
            new_comments.append({
                "doc_id": doc_id,
                "doc_title": doc_title,
                "comment_id": comment_id,
                "quote": quote,
                "text": comment_text,
                "user_id": item.get("user_id", "")
            })

# 输出新评论
print(json.dumps(new_comments, ensure_ascii=False, indent=2))
PYEOF
