import json
import requests
import sys
import os

# Load tracked docs
try:
    with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json', 'r') as f:
        tracked_docs = json.load(f)
except Exception as e:
    print(f"Error loading tracked docs: {e}")
    sys.exit(1)

# Load comment state
state_file = '/home/ubuntu/.openclaw/workspace/data/comment-state.json'
try:
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            comment_state = json.load(f)
    else:
        comment_state = {}
except Exception as e:
    print(f"Error loading comment state: {e}")
    sys.exit(1)

# Get Tenant Token
try:
    token_cmd = """curl -s -X POST "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal" \
      -H "Content-Type: application/json" \
      -d '{"app_id":"cli_a90c3a6163785ed2","app_secret":"***LARK_SECRET_REMOVED***"}'"""
    import subprocess
    result = subprocess.check_output(token_cmd, shell=True)
    tenant_token = json.loads(result)['tenant_access_token']
except Exception as e:
    print(f"Error getting tenant token: {e}")
    sys.exit(1)

new_comments = []

for doc in tracked_docs:
    if doc['file_type'] != 'docx':
        continue
        
    doc_token = doc['id'] # doc['id'] is the obj_token/doc_token needed for API 
    # The prompt says: GET https://open.larksuite.com/open-apis/drive/v1/files/{obj_token}/comments?file_type=docx
    # In tracked-docs.json, "node_token" is usually the token for docx.
    
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments?file_type=docx"
    headers = {
        "Authorization": f"Bearer {tenant_token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        res_json = response.json()
        
        if res_json.get('code') != 0:
            print(f"Error fetching comments for {doc['title']}: {res_json.get('msg')}")
            continue
            
        items = res_json.get('data', {}).get('items', [])
        
        known_ids = comment_state.get(doc['id'], []) # Use doc['id'] as key in state file as seen in previous read
        
        current_doc_comments = []
        
        for comment in items:
            comment_id = comment['comment_id']
            is_solved = comment.get('is_solved', False)
            
            # Update state list for this doc (to keep track of all current comments)
            current_doc_comments.append(comment_id)
            
            if is_solved:
                continue
                
            if comment_id not in known_ids:
                # New unsolved comment found!
                print(f"NEW COMMENT in {doc['title']}: {comment_id}")
                content = comment.get('content', '')
                quote = comment.get('quote', '')
                reply_list = comment.get('reply_list', {}).get('replies', [])
                
                new_comments.append({
                    "doc_id": doc['id'],
                    "doc_token": doc_token,
                    "doc_title": doc['title'],
                    "comment_id": comment_id,
                    "content": content,
                    "quote": quote,
                    "replies": reply_list
                })
        
        # Optionally update state (not saving yet, just logic)
        
    except Exception as e:
        print(f"Request error for {doc['title']}: {e}")

# Output results
if new_comments:
    print(f"Found {len(new_comments)} new comments.")
    print(json.dumps(new_comments, indent=2, ensure_ascii=False))
else:
    print("No new comments found.")
