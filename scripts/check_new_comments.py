import json
import requests
import sys

# Configuration
TENANT_ACCESS_TOKEN = "t-g2062c25JSN3WMXOKYHMLD6XDKWDNHUMMK2R7HYY"
TRACKED_DOCS_PATH = "/home/ubuntu/.openclaw/workspace/data/tracked-docs.json"
COMMENT_STATE_PATH = "/home/ubuntu/.openclaw/workspace/data/comment-state.json"

def get_comments(token, file_token):
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{file_token}/comments?file_type=docx"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("data", {}).get("items", [])
    except Exception as e:
        print(f"Error fetching comments for {file_token}: {e}", file=sys.stderr)
        return []

def main():
    # Load data
    try:
        with open(TRACKED_DOCS_PATH, 'r') as f:
            tracked_docs = json.load(f)
        with open(COMMENT_STATE_PATH, 'r') as f:
            comment_state = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return

    new_comments_found = []

    print(f"Scanning {len(tracked_docs)} documents for new comments...")
    
    for doc in tracked_docs:
        if doc.get("file_type") != "docx":
            continue
            
        file_token = doc["id"] # Use id (obj_token) for docx
        doc_id = doc["id"] 
        
        # Determine valid ID for state lookup (some might be keyed by one or the other)
        # The state file uses the object token (id)
        
        current_comments = get_comments(TENANT_ACCESS_TOKEN, file_token)
        
        known_comment_ids = set(comment_state.get(file_token, []))
        
        for comment in current_comments:
            if not comment.get("is_solved") and comment["comment_id"] not in known_comment_ids:
                # Found a new unresolved comment
                new_comments_found.append({
                    "doc_name": doc.get("title", "Unknown"),
                    "doc_token": file_token,
                    "comment": comment
                })

    # Output results
    if new_comments_found:
        print(f"Found {len(new_comments_found)} new comments:")
        print(json.dumps(new_comments_found, indent=2, ensure_ascii=False))
    else:
        print("No new comments found.")

if __name__ == "__main__":
    main()
