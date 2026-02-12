import json
import urllib.request
import urllib.error

# Configuration
token_path = '/home/ubuntu/.openclaw/workspace/data/lark-user-token.json'
changelog_path = '/home/ubuntu/.openclaw/workspace/memgate/CHANGELOG.md'
space_id = '7604126789916479197'
parent_node_token = 'IUBdwFzDhisMDrkm1fAltnOhgGd'

def get_access_token():
    with open(token_path, 'r') as f:
        data = json.load(f)
        return data['access_token']

def create_wiki_node(token):
    url = f"https://open.larksuite.com/open-apis/wiki/v2/spaces/{space_id}/nodes"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "obj_type": "docx",
        "node_type": "origin",
        "parent_node_token": parent_node_token,
        "title": "MemGate v0.1.0 Release Note"
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('code') != 0:
                raise Exception(f"API Error: {result}")
            return result['data']['node']['obj_token']
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise

def write_content(token, obj_token, content):
    url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{obj_token}/blocks/{obj_token}/children"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Structure from instructions: block_type 14 (Code)
    data = {
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
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            print("Content written successfully.")
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise

def main():
    print("Reading token...")
    token = get_access_token()
    
    print("Reading changelog...")
    with open(changelog_path, 'r') as f:
        content = f.read()
        
    print("Creating Wiki node...")
    obj_token = create_wiki_node(token)
    print(f"Node created with obj_token: {obj_token}")
    
    print("Writing content to Wiki...")
    write_content(token, obj_token, content)
    print("Done.")

if __name__ == "__main__":
    main()
