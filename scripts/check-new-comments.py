import json
import requests
import sys
import os

# Configuration
TRACKED_DOCS_PATH = '/home/ubuntu/.openclaw/workspace/data/tracked-docs.json'
COMMENT_STATE_PATH = '/home/ubuntu/.openclaw/workspace/data/comment-state.json'
TENANT_TOKEN = sys.argv[1]

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def get_comments(doc_token, file_type):
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments"
    params = {'file_type': file_type, 'page_size': 50}
    headers = {'Authorization': f'Bearer {TENANT_TOKEN}'}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json().get('data', {}).get('items', [])
    except Exception as e:
        print(f"Error fetching comments for {doc_token}: {e}", file=sys.stderr)
        return []

def main():
    tracked_docs = load_json(TRACKED_DOCS_PATH)
    comment_state = load_json(COMMENT_STATE_PATH)
    
    new_comments = []

    for doc in tracked_docs:
        if doc.get('file_type') != 'docx':
            continue
            
        doc_token = doc['node_token'] # API uses node_token as token for docx usually, or the obj token. 
        # tracked-docs has 'id' (obj_token) and 'node_token'. 
        # API endpoint: /drive/v1/files/{file_token}/comments
        # For docx, usually use the document ID (obj_token).
        file_token = doc['id']
        
        # Get processed IDs for this doc
        processed_ids = set(comment_state.get(file_token, []))
        
        comments = get_comments(file_token, 'docx')
        
        for comment in comments:
            # Check if solved
            if comment.get('is_solved'):
                continue
                
            comment_id = comment['comment_id']
            
            # Check if processed
            if comment_id in processed_ids:
                continue
                
            # It's a new, unresolved comment
            new_comments.append({
                'doc_name': doc['title'],
                'doc_token': file_token,
                'comment_id': comment_id,
                'content': comment.get('content', ''),
                'quote': comment.get('quote', ''),
                'create_time': comment.get('create_time'),
                'reply_id': comment.get('reply_id') # If it's a reply
            })

    print(json.dumps(new_comments, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
