import json
import sys
import requests
import os
import concurrent.futures

def get_tenant_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": "cli_a90c3a6163785ed2",
        "app_secret": "***LARK_SECRET_REMOVED***"
    }
    resp = requests.post(url, headers=headers, json=data)
    return resp.json().get("tenant_access_token")

def check_doc(doc, token, solved_state):
    if doc.get('file_type') != 'docx':
        return []
        
    doc_token = doc['node_token']
    url = f"https://open.larksuite.com/open-apis/drive/v1/files/{doc_token}/comments"
    params = {"file_type": "docx", "is_solved": "false"}
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        
        if data.get('code') != 0:
            return []
            
        items = data.get('data', {}).get('items', [])
        new_comments = []
        
        # solved_state structure: {"doc_id": ["comment_id1", ...]}
        # But wait, the json file usually has doc_token as key?
        # Let's check how the file is structured. 
        # The previous tool output showed: "BY57drV7Uo1bwnxeWAmlSwAtgCb": ["7604...", ...]
        # So keys are doc_tokens.
        
        doc_solved = solved_state.get(doc_token, [])
        
        for item in items:
            comment_id = item['comment_id']
            if comment_id in doc_solved:
                continue
                
            # Extract text content
            content = ""
            try:
                # Lark comment content is a rich text JSON structure
                # We try to grab the first text run
                content = item['content']['elements'][0]['text_run']['text']
            except:
                content = json.dumps(item.get('content', {}))
                
            quote = item.get('quote', "")
            
            new_comments.append({
                "doc_token": doc_token,
                "doc_title": doc['title'],
                "comment_id": comment_id,
                "content": content,
                "quote": quote,
                "reply_id": item.get('reply_id')
            })
            
        return new_comments
    except Exception as e:
        return []

def main():
    try:
        with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json') as f:
            docs = json.load(f)
            
        try:
            with open('/home/ubuntu/.openclaw/workspace/data/comment-state.json') as f:
                state = json.load(f)
        except FileNotFoundError:
            state = {}
            
        token = get_tenant_token()
        all_new_comments = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check_doc, doc, token, state) for doc in docs]
            for future in concurrent.futures.as_completed(futures):
                all_new_comments.extend(future.result())
                
        print(json.dumps(all_new_comments, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
