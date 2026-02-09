import json
import requests
import sys
import os

# Load arguments
if len(sys.argv) < 2:
    print("Usage: python3 scan_comments.py <tenant_token>")
    sys.exit(1)

tenant_token = sys.argv[1]

# Load Data
workspace = "/home/ubuntu/.openclaw/workspace"
with open(f"{workspace}/data/tracked-docs.json") as f:
    docs = json.load(f)

state_path = f"{workspace}/data/comment-state.json"
if os.path.exists(state_path):
    with open(state_path) as f:
        state = json.load(f)
else:
    state = {}

new_comments_found = []

headers = {
    'Authorization': f'Bearer {tenant_token}'
}

print(f"Scanning {len(docs)} documents for new comments...")

for doc in docs:
    if doc['file_type'] != 'docx':
        continue
    
    token = doc['node_token'] # docx uses node_token as the file token in drive v1 usually, or we might need the object token. 
    # Actually tracked-docs has 'id' (obj_token) and 'node_token'. 
    # The prompt says: GET .../files/{obj_token}/comments?file_type=docx
    # So we use doc['id'].
    
    obj_token = doc['id']
    doc_title = doc.get('title', 'Untitled')
    
    # print(f"Checking {doc_title} ({obj_token})...")
    
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{obj_token}/comments"
    params = {
        'file_type': 'docx',
        'is_solved': 'false', # Only interest in unsolved
        'page_size': 50
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            # print(f"  Error {resp.status_code}: {resp.text}")
            continue
            
        data = resp.json()
        items = data.get('data', {}).get('items', [])
        
        # Check known state for this doc
        known_ids = state.get(obj_token, [])
        
        for item in items:
            comment_id = item['comment_id']
            if comment_id in known_ids:
                continue
                
            # It's NEW!
            # Get the content
            content = item.get('content', {}).get('elements', [{}])[0].get('text_run', {}).get('text', '')
            quote = item.get('quote', '')
            
            # If content is empty/complex, try to dump whole thing
            if not content:
                content = "[Complex Content]"
                
            new_comment = {
                'doc_id': obj_token,
                'doc_title': doc_title,
                'comment_id': comment_id,
                'quote': quote,
                'content': content,
                'reply_token': item.get('reply_token') # Might be needed? Actually ID is enough usually.
            }
            new_comments_found.append(new_comment)
            print(f"🔴 NEW COMMENT in [{doc_title}]: {content} (on '{quote}')")
            
    except Exception as e:
        print(f"  Exception checking {doc_title}: {e}")

# Output results as JSON for the agent to parse easily if needed, or just rely on the print above.
if new_comments_found:
    print("\n--- JSON OUTPUT ---")
    print(json.dumps(new_comments_found, indent=2))
else:
    print("\n✅ No new comments found.")
