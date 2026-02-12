import json
import requests
import sys
import os

# Load config
try:
    with open('data/tracked-docs.json') as f:
        docs = json.load(f)
    with open('data/comment-state.json') as f:
        processed_comments = json.load(f)
except FileNotFoundError:
    print("Error: Config files not found.")
    sys.exit(1)

# Get Tenant Token
def get_tenant_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": "cli_a90c3a6163785ed2",
        "app_secret": "***LARK_SECRET_REMOVED***"
    }
    resp = requests.post(url, headers=headers, json=data)
    return resp.json().get("tenant_access_token")

token = get_tenant_token()
if not token:
    print("Failed to get tenant token")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}"
}

new_comments = []

print(f"Checking {len(docs)} documents for new comments...")

for doc in docs:
    if doc.get('file_type') != 'docx':
        continue
        
    doc_token = doc['id'] # Using 'id' as obj_token
    # print(f"Checking {doc['title']} ({doc_token})...")
    
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments"
    params = {
        "file_type": "docx",
        "is_solved": "false"
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        
        if data.get('code') != 0:
            # print(f"Error checking {doc['title']}: {data}")
            continue
            
        comments = data.get('data', {}).get('items', [])
        
        # Check against state
        doc_processed = processed_comments.get(doc_token, [])
        
        for comment in comments:
            comment_id = comment['comment_id']
            if comment_id not in doc_processed:
                # Found a new comment!
                new_comments.append({
                    "doc_title": doc['title'],
                    "doc_token": doc_token,
                    "comment_id": comment_id,
                    "content": comment.get('content'),
                    "quote": comment.get('quote'),
                    "create_time": comment.get('create_time'),
                    "reply_list": comment.get('reply_list', [])
                })
                
    except Exception as e:
        print(f"Exception checking {doc['title']}: {e}")

print(json.dumps(new_comments, indent=2, ensure_ascii=False))
