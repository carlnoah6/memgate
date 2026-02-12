import json
import requests
import sys
import os

# 1. Get Tenant Access Token
def get_tenant_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": "cli_a90c3a6163785ed2",
        "app_secret": "***LARK_SECRET_REMOVED***"
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]

# 2. Load Data
try:
    with open("/home/ubuntu/.openclaw/workspace/data/tracked-docs.json", "r") as f:
        tracked_docs = json.load(f)
except FileNotFoundError:
    print("[]")
    sys.exit(0)

try:
    with open("/home/ubuntu/.openclaw/workspace/data/comment-state.json", "r") as f:
        comment_state = json.load(f)
except FileNotFoundError:
    comment_state = {}

token = get_tenant_token()
new_comments = []

# 3. Iterate Docs
for doc in tracked_docs:
    if doc.get("file_type") != "docx":
        continue
        
    doc_token = doc["id"] # Assuming 'id' is the token used for API
    doc_title = doc.get("title", "Untitled")
    
    # 4. Fetch Comments
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments"
    params = {"file_type": "docx"}
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            # sys.stderr.write(f"Error fetching {doc_title}: {resp.text}\n")
            continue
            
        data = resp.json()
        if data.get("code") != 0:
            continue
            
        items = data.get("data", {}).get("items", [])
        if not items:
            continue
            
        # 5. Filter New Comments
        known_ids = comment_state.get(doc_token, [])
        
        for item in items:
            if item.get("is_solved"):
                continue
                
            comment_id = item["comment_id"]
            if comment_id in known_ids:
                continue
                
            # Found a new unresolved comment
            new_comments.append({
                "doc_token": doc_token,
                "doc_title": doc_title,
                "comment_id": comment_id,
                "content": item.get("content"),
                "quote": item.get("quote"),
                "create_time": item.get("create_time"),
                "reply_id": item.get("reply_id") # If it's a reply to a comment, logic might differ, but usually we track threads
            })
            
    except Exception as e:
        sys.stderr.write(f"Exception processing {doc_title}: {e}\n")

print(json.dumps(new_comments, ensure_ascii=False, indent=2))
