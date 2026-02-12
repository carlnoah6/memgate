import json
import requests
import sys
import os

# Load tracked docs
try:
    with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json', 'r') as f:
        docs = json.load(f)
except Exception as e:
    print(f"Error loading tracked docs: {e}")
    sys.exit(1)

# Load comment state
state_path = '/home/ubuntu/.openclaw/workspace/data/comment-state.json'
if os.path.exists(state_path):
    with open(state_path, 'r') as f:
        comment_state = json.load(f)
else:
    comment_state = {}

# Get Tenant Access Token
app_id = "cli_a90c3a6163785ed2"
app_secret = "***LARK_SECRET_REMOVED***"
url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
headers = {"Content-Type": "application/json"}
req_body = {"app_id": app_id, "app_secret": app_secret}
resp = requests.post(url, headers=headers, json=req_body)
tenant_token = resp.json().get("tenant_access_token")

if not tenant_token:
    print("Failed to get tenant token")
    sys.exit(1)

# Scan docs
new_comments = []

for doc in docs:
    if doc['file_type'] != 'docx':
        continue
        
    token = doc['id']
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{token}/comments?file_type=docx"
    headers = {"Authorization": f"Bearer {tenant_token}"}
    
    try:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        
        if data.get('code') != 0:
            print(f"Error fetching comments for {token}: {data}")
            continue
            
        items = data.get('data', {}).get('items', [])
        
        for item in items:
            comment_id = item['comment_id']
            # Check if solved
            if item.get('is_solved'):
                continue
                
            # Check if already processed
            if comment_id in comment_state:
                continue
            
            # Found new comment
            new_comments.append({
                "doc_id": token,
                "doc_title": doc.get('title', 'Unknown'),
                "comment_id": comment_id,
                "content": item.get('content'),
                "quote": item.get('quote'),
                "reply_list": item.get('reply_list', []),
                "author_id": item.get('user_id')
            })
            
    except Exception as e:
        print(f"Exception checking {token}: {e}")

print(json.dumps(new_comments, indent=2, ensure_ascii=False))
