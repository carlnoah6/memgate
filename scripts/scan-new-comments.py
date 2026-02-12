import json
import sys
import requests
import os

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scan-new-comments.py <tenant_access_token>")
        sys.exit(1)

    token = sys.argv[1]
    tracked_docs_path = '/home/ubuntu/.openclaw/workspace/data/tracked-docs.json'
    state_path = '/home/ubuntu/.openclaw/workspace/data/comment-state.json'

    docs = load_json(tracked_docs_path)
    state = load_json(state_path)
    
    # Ensure state is a dict
    if isinstance(state, list):
        state = {}

    new_comments = []

    headers = {
        'Authorization': f'Bearer {token}'
    }

    for doc in docs:
        if doc.get('file_type') != 'docx':
            continue

        doc_token = doc.get('node_token') or doc.get('id')
        if not doc_token:
            continue

        url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments?file_type=docx"
        
        try:
            response = requests.get(url, headers=headers)
            res_json = response.json()
            
            if res_json.get('code') != 0:
                # print(f"Error fetching comments for {doc.get('title')}: {res_json}", file=sys.stderr)
                continue

            items = res_json.get('data', {}).get('items', [])
            
            processed_ids = state.get(doc_token, [])
            
            for item in items:
                if item.get('is_solved'):
                    continue
                
                comment_id = item.get('comment_id')
                if comment_id in processed_ids:
                    continue

                # Get the first reply/content to determine intent if needed, 
                # but mainly we need the content of the comment itself.
                # The 'content' field in the item is usually the *first* message in the thread.
                
                content = item.get('content', '')
                quote = item.get('quote', '')
                
                # If there are replies, we might need to check if *we* replied, 
                # but for now we trust the state file. 
                # If it's not in state and not solved, it's new.

                new_comments.append({
                    'doc_id': doc_token,
                    'doc_title': doc.get('title'),
                    'comment_id': comment_id,
                    'content': content,
                    'quote': quote,
                    'create_time': item.get('create_time')
                })

        except Exception as e:
            print(f"Exception processing {doc.get('title')}: {e}", file=sys.stderr)

    print(json.dumps(new_comments, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
