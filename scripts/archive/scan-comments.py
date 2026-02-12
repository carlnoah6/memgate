import json
import requests
import sys

# Config
TRACKED_DOCS_FILE = "/home/ubuntu/.openclaw/workspace/data/tracked-docs.json"
COMMENT_STATE_FILE = "/home/ubuntu/.openclaw/workspace/data/comment-state.json"
TENANT_TOKEN = "t-g2062a7EMQBQ56RGAROOWXP4CW6NGDZ72JF4HEKD"

def get_tracked_docs():
    try:
        with open(TRACKED_DOCS_FILE) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading tracked docs: {e}", file=sys.stderr)
        return []

def get_comment_state():
    try:
        with open(COMMENT_STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error reading comment state: {e}", file=sys.stderr)
        return {}

def check_comments():
    docs = get_tracked_docs()
    state = get_comment_state()
    
    new_comments = []
    
    headers = {
        "Authorization": f"Bearer {TENANT_TOKEN}"
    }
    
    print(f"Scanning {len(docs)} documents for new comments...", file=sys.stderr)
    
    for doc in docs:
        if doc.get('file_type') != 'docx':
            continue
            
        token = doc['node_token'] # actually usually we use obj_token (doc['id']) for drive API, let's check tracked-docs structure.
        # tracked-docs.json has "id" which looks like obj_token (TvIod...) and "node_token" (EZY2...). 
        # The prompt says: GET https://open.larksuite.com/open-apis/drive/v1/files/{obj_token}/comments
        # So we should use doc['id'].
        
        file_token = doc['id']
        
        url = f"https://open.larksuite.com/open-apis/drive/v1/files/{file_token}/comments?file_type=docx"
        
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"Failed to fetch comments for {doc['title']} ({file_token}): {resp.text}", file=sys.stderr)
                continue
                
            data = resp.json()
            if data.get('code') != 0:
                 # Ignore frequent permission errors for external docs
                if data.get('code') != 1061001: 
                    print(f"API Error for {doc['title']}: {data}", file=sys.stderr)
                continue
                
            items = data.get('data', {}).get('items', [])
            
            # Check previously known comments for this doc
            known_comments = state.get(file_token, [])
            
            for comment in items:
                if comment.get('is_solved'):
                    continue
                    
                comment_id = comment['comment_id']
                if comment_id in known_comments:
                    continue
                
                # It's a new unsolved comment
                print(f"Found new comment in {doc['title']}: {comment_id}", file=sys.stderr)
                new_comments.append({
                    "doc_title": doc['title'],
                    "doc_token": file_token,
                    "comment_id": comment_id,
                    "content": comment.get('content', ''),
                    "quote": comment.get('quote', ''),
                    "reply_id": comment.get('reply_id') # If it's a reply
                })
                
        except Exception as e:
            print(f"Exception checking {doc['title']}: {e}", file=sys.stderr)

    print(json.dumps(new_comments, indent=2))

if __name__ == "__main__":
    check_comments()
