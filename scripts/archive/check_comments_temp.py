import json
import requests
import sys

# Load tracked docs
with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json', 'r') as f:
    docs = json.load(f)

# Load comment state
try:
    with open('/home/ubuntu/.openclaw/workspace/data/comment-state.json', 'r') as f:
        state = json.load(f)
        processed_ids = set()
        for doc_ids in state.values():
            if isinstance(doc_ids, list):
                processed_ids.update(doc_ids)
except FileNotFoundError:
    processed_ids = set()

token = "t-g2062a693CDQ5M6UE4ZFWF6TP5YYWJHDPR6CDILM"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json; charset=utf-8"
}

new_comments = []

print(f"Checking {len(docs)} documents...")

for doc in docs:
    if doc.get('file_type') != 'docx':
        continue
        
    doc_token = doc['id'] # Use id (obj_token)
    
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments?file_type=docx"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching {doc['title']}: {response.text}")
            continue
            
        data = response.json()
        if data.get('code') != 0:
            print(f"API Error {doc['title']}: {data}")
            continue
            
        items = data.get('data', {}).get('items', [])
        
        for item in items:
            if item['is_solved']:
                continue
                
            comment_id = item['comment_id']
            if comment_id in processed_ids:
                continue
                
            # Found a new unresolved comment
            new_comments.append({
                'doc_id': doc_token,
                'doc_title': doc['title'],
                'comment_id': comment_id,
                'content': item['content'], # Rich text structure
                'quote': item.get('quote', ''),
                'create_time': item['create_time']
            })
            
    except Exception as e:
        print(f"Exception checking {doc['title']}: {e}")

print(json.dumps(new_comments, indent=2, ensure_ascii=False))
