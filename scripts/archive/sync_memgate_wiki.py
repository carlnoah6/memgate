import json
import requests
import os

# Configuration
TOKEN = "***TOKEN_REMOVED***"
SPACE_ID = "7604126789916479197"
PARENT_NODE_TOKEN = "IUBdwFzDhisMDrkm1fAltnOhgGd"
README_PATH = "/home/ubuntu/.openclaw/workspace/memgate/README.md"
TITLE = "MemGate 文档 (v0.1.0)"

def create_wiki_node():
    url = f"https://open.larksuite.com/open-apis/wiki/v2/spaces/{SPACE_ID}/nodes"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "obj_type": "docx",
        "node_type": "origin",
        "parent_node_token": PARENT_NODE_TOKEN,
        "title": TITLE
    }
    
    print(f"Creating Wiki Node: {TITLE}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error creating node: {response.text}")
        return None
        
    data = response.json()
    if data.get("code") != 0:
        print(f"API Error: {data}")
        return None
        
    node = data.get("data", {}).get("node", {})
    obj_token = node.get("obj_token")
    print(f"Node created. Object Token: {obj_token}")
    return obj_token

def write_content(obj_token, content):
    url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{obj_token}/blocks/{obj_token}/children"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Wrap content in a Code Block (Type 14) as per instructions
    # Language 1 is Plain Text / Markdown-ish
    payload = {
        "children": [
            {
                "block_type": 14,
                "code": {
                    "style": {"language": 1},
                    "elements": [{"text_run": {"content": content}}]
                }
            }
        ],
        "index": 0
    }
    
    print(f"Writing content to document {obj_token}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error writing content: {response.text}")
        return False
        
    data = response.json()
    if data.get("code") != 0:
        print(f"API Error: {data}")
        return False
        
    print("Content successfully written.")
    return True

def main():
    # 1. Read README
    try:
        with open(README_PATH, "r") as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read README: {e}")
        return

    # 2. Create Node
    obj_token = create_wiki_node()
    if not obj_token:
        return

    # 3. Write Content
    # Ensure content isn't too large for a single block (limit is usually high but good to keep in mind)
    # The instructions mentioned <4500 chars per block, README is ~4000 bytes, so it should fit.
    if len(content) > 4000:
        print("Warning: Content length might be close to limit. Truncating slightly if needed is not implemented.")
    
    success = write_content(obj_token, content)
    if success:
        print("Wiki sync completed successfully.")
    else:
        print("Wiki sync failed.")

if __name__ == "__main__":
    main()
