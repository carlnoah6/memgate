import json
import requests
import sys
import os

def check_comments(tenant_token):
    try:
        with open('data/tracked-docs.json', 'r') as f:
            docs = json.load(f)
    except FileNotFoundError:
        print("Error: data/tracked-docs.json not found")
        return

    # Filter for docx only
    docs = [d for d in docs if d.get('file_type') == 'docx']
    
    # Load state
    processed_comments = set()
    if os.path.exists('data/comment-state.json'):
        try:
            with open('data/comment-state.json', 'r') as f:
                state = json.load(f)
                processed_comments = set(state.keys())
        except:
            pass

    headers = {
        "Authorization": f"Bearer {tenant_token}",
        "Content-Type": "application/json"
    }

    new_comments = []

    for doc in docs:
        token = doc['id']
        url = f"https://open.larksuite.com/open-apis/drive/v1/files/{token}/comments?file_type=docx&is_solved=false"
        
        try:
            response = requests.get(url, headers=headers)
            res = response.json()
            
            if res.get('code') == 0:
                items = res.get('data', {}).get('items', [])
                if not items:
                    continue
                    
                for comment in items:
                    cid = comment['comment_id']
                    if cid not in processed_comments:
                        new_comments.append({
                            'doc_token': token,
                            'doc_title': doc['title'],
                            'comment_id': cid,
                            'quote': comment.get('quote', ''),
                            'content': comment.get('content', ''),
                            'reply_id': comment.get('reply_id', '') 
                        })
            else:
                # Silently fail on permission errors or just continue
                pass
        except Exception as e:
            # print(f"Error checking {doc['title']}: {e}", file=sys.stderr)
            pass

    print(json.dumps(new_comments, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 check_comments.py <tenant_token>")
        sys.exit(1)
    
    check_comments(sys.argv[1])
