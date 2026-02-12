import requests
import json
import os

# Configuration
SPACE_ID = "7604150806383693538"
PARENT_NODE_TOKEN = "OZmqwn4yviwsY2k1JBblkgTYg5c"
TITLE = "Tokenizer Training MVP"

# Read Token
with open("data/lark-user-token.json", "r") as f:
    token_data = json.load(f)
    ACCESS_TOKEN = token_data["access_token"]

# Read Code
with open("scripts/train_tokenizer.py", "r") as f:
    code_content = f.read()

def create_wiki_node():
    url = f"https://open.larksuite.com/open-apis/wiki/v2/spaces/{SPACE_ID}/nodes"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "obj_type": "docx",
        "parent_node_token": PARENT_NODE_TOKEN,
        "node_type": "origin",
        "origin_node_type": "docx",
        "title": TITLE
    }
    
    print("🚀 Creating Wiki Node...")
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"❌ Failed to create node: {resp.text}")
        return None
    
    data = resp.json()
    if data.get("code") != 0:
        print(f"❌ API Error: {data}")
        return None
        
    node = data["data"]["node"]
    print(f"✅ Node Created: {node['node_token']} (obj_token: {node['obj_token']})")
    return node["obj_token"]

def write_wiki_content(document_id):
    url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    children = [
        {
            "block_type": 4, # Heading 2
            "heading2": {"elements": [{"text_run": {"content": "Configuration"}}]}
        },
        {
            "block_type": 13, # Ordered List (used as bullet points here effectively)
            "ordered": {"elements": [{"text_run": {"content": "Vocab Size: 100,000"}}]}
        },
        {
            "block_type": 13,
            "ordered": {"elements": [{"text_run": {"content": "Model Type: BPE (SentencePiece)"}}]}
        },
        {
            "block_type": 13,
            "ordered": {"elements": [{"text_run": {"content": "Character Coverage: 0.9995"}}]}
        },
        {
            "block_type": 13,
            "ordered": {"elements": [{"text_run": {"content": "Input Data: FineWeb-Edu Sample (30,000 sentences used to fit memory)"}}]}
        },
        {
            "block_type": 4, # Heading 2
            "heading2": {"elements": [{"text_run": {"content": "Training Code"}}]}
        },
        {
            "block_type": 14, # Code
            "code": {
                "language": 16, # Python
                "elements": [{"text_run": {"content": code_content}}]
            }
        },
        {
            "block_type": 4, # Heading 2
            "heading2": {"elements": [{"text_run": {"content": "Verification Results"}}]}
        },
        {
            "block_type": 2, # Text
            "text": {"elements": [{"text_run": {"content": "Test Sentence: \"The quick brown fox jumps over the lazy dog.\""}}]}
        },
        {
            "block_type": 2, # Text
            "text": {"elements": [{"text_run": {"content": "Token Reconstruction: Successful ✅"}}]}
        },
        {
            "block_type": 2, # Text
            "text": {"elements": [{"text_run": {"content": "Generated: data/tokenizer.model, data/tokenizer.vocab"}}]}
        }
    ]
    
    payload = {
        "children": children,
        "index": -1
    }
    
    print("📝 Writing Content...")
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print("✅ Content synced successfully.")
    else:
        print(f"❌ Failed to write content: {resp.text}")

if __name__ == "__main__":
    doc_token = create_wiki_node()
    if doc_token:
        write_wiki_content(doc_token)
