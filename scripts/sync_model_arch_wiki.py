import json
import requests
import sys
import os

# Configuration
SPACE_ID = "7604150806383693538"
PARENT_NODE_TOKEN = "OZmqwn4yviwsY2k1JBblkgTYg5c"
TITLE = "Model Architecture (7B Llama-style)"

def get_token():
    with open("data/lark-user-token.json", "r") as f:
        data = json.load(f)
        return data["access_token"]

def read_file(path):
    with open(path, "r") as f:
        return f.read()

def create_wiki_node(access_token):
    url = f"https://open.larksuite.com/open-apis/wiki/v2/spaces/{SPACE_ID}/nodes"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "obj_type": "docx",
        "parent_node_token": PARENT_NODE_TOKEN,
        "node_type": "origin",
        "origin": {
            "title": TITLE,
            "obj_type": "docx"
        }
    }
    
    print(f"Creating wiki node under {PARENT_NODE_TOKEN}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Failed to create node: {response.text}")
        sys.exit(1)
        
    data = response.json()
    if data["code"] != 0:
        print(f"API Error: {data}")
        sys.exit(1)
        
    obj_token = data["data"]["node"]["obj_token"]
    print(f"Node created. Object Token (Doc ID): {obj_token}")
    return obj_token

def update_doc_content(access_token, doc_token):
    url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    config_code = read_file("model/configuration.py")
    model_code = read_file("model/modeling.py")
    
    children = [
        {
            "block_type": 4, # Heading 2
            "heading2": {"elements": [{"text_run": {"content": "Overview", "text_style": {}}}]}
        },
        {
            "block_type": 2, # Text
            "text": {"elements": [{"text_run": {"content": "This document outlines the implementation of the 7B Llama-style model architecture using PyTorch. The model features Grouped Query Attention (GQA), RoPE embeddings, and SwiGLU activation. \n\nNote: With `n_kv_heads=8` (GQA), the actual parameter count is approximately 6.49B, reduced from the standard 7B (MHA).", "text_style": {}}}]}
        },
        {
            "block_type": 4, # Heading 2
            "heading2": {"elements": [{"text_run": {"content": "Model Configuration", "text_style": {}}}]}
        },
        {
            "block_type": 14, # Code
            "code": {
                "language": 16, # Python
                "elements": [{"text_run": {"content": config_code, "text_style": {}}}]
            }
        },
        {
            "block_type": 4, # Heading 2
            "heading2": {"elements": [{"text_run": {"content": "Model Implementation", "text_style": {}}}]}
        },
        {
            "block_type": 14, # Code
            "code": {
                "language": 16, # Python
                "elements": [{"text_run": {"content": model_code, "text_style": {}}}]
            }
        }
    ]
    
    payload = {
        "children": children,
        "index": -1
    }
    
    print("Uploading content...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Failed to upload content: {response.text}")
    else:
        print("Content uploaded successfully.")

def main():
    token = get_token()
    doc_token = create_wiki_node(token)
    update_doc_content(token, doc_token)

if __name__ == "__main__":
    main()
