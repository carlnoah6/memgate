import json
import sys
import requests
import os

# Load config
try:
    with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json', 'r') as f:
        docs = json.load(f)
    
    # Ensure comment state exists
    state_path = '/home/ubuntu/.openclaw/workspace/data/comment-state.json'
    if not os.path.exists(state_path):
        with open(state_path, 'w') as f:
            json.dump({}, f)
    
    with open(state_path, 'r') as f:
        state = json.load(f)
except Exception as e:
    print(f"Error loading config: {e}")
    sys.exit(1)

# Get Tenant Token
app_id = "cli_a90c3a6163785ed2"
app_secret = "***LARK_SECRET_REMOVED***"
url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
tenant_token = resp.json().get("tenant_access_token")

if not tenant_token:
    print("Failed to get tenant token")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {tenant_token}"
}

pending_comments = []

print(f"Scanning {len(docs)} documents for new comments...")

for doc in docs:
    if doc.get('file_type') != 'docx':
        continue
        
    token = doc['node_token'] # tracked-docs uses node_token as the identifier usually, or token. The example used obj_token.
    # In tracked-docs.json, "node_token" is the file token for docx usually.
    
    # Check comments
    # GET /drive/v1/files/{token}/comments?file_type=docx
    c_url = f"https://open.larksuite.com/open-apis/drive/v1/files/{token}/comments?file_type=docx"
    try:
        c_resp = requests.get(c_url, headers=headers)
        if c_resp.status_code != 200:
            # print(f"Error fetching comments for {doc['title']}: {c_resp.text}")
            continue
            
        data = c_resp.json().get('data', {})
        items = data.get('items', [])
        
        processed_ids = state.get(token, [])
        
        for item in items:
            comment_id = item['comment_id']
            if item.get('is_solved'):
                continue
                
            if comment_id in processed_ids:
                continue
                
            # Found a new unresolved comment
            pending_comments.append({
                "doc_title": doc['title'],
                "doc_token": token,
                "comment_id": comment_id,
                "content": item.get('content', ''), # Rich text usually
                "quote": item.get('quote', ''),
                "reply_count": len(item.get('replies', []))
            })
            
    except Exception as e:
        print(f"Exception checking {doc['title']}: {e}")

# Output results as JSON for the agent to parse
print(json.dumps(pending_comments, indent=2, ensure_ascii=False))
