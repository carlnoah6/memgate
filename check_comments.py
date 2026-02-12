#!/usr/bin/env python3
import json
import subprocess
import sys

# 获取 tenant_access_token
result = subprocess.run([
    'curl', '-s', '-X', 'POST', 'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal',
    '-H', 'Content-Type: application/json',
    '-d', '{"app_id":"cli_a90c3a6163785ed2","app_secret":"***LARK_SECRET_REMOVED***"}'
], capture_output=True, text=True)
tenant_token = json.loads(result.stdout)['tenant_access_token']

# 读取 tracked docs
with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json', 'r') as f:
    tracked_docs = json.load(f)

# 读取 comment state
with open('/home/ubuntu/.openclaw/workspace/data/comment-state.json', 'r') as f:
    comment_state = json.load(f)

new_comments_found = False

for doc in tracked_docs:
    if doc['file_type'] != 'docx':
        continue
    
    doc_id = doc['id']
    node_token = doc['node_token']
    
    print(f"\n检查文档: {doc['title']} ({doc_id})")
    
    # 获取评论
    result = subprocess.run([
        'curl', '-s', '-X', 'GET',
        f'https://open.larksuite.com/open-apis/drive/v1/files/{node_token}/comments?file_type=docx',
        '-H', f'Authorization: Bearer {tenant_token}'
    ], capture_output=True, text=True)
    
    try:
        comments_data = json.loads(result.stdout)
    except:
        print(f"  错误: 无法解析响应")
        continue
    
    if comments_data.get('code') != 0:
        print(f"  API 错误: {comments_data.get('msg')}")
        continue
    
    items = comments_data.get('data', {}).get('items', [])
    if not items:
        print(f"  无评论")
        continue
    
    # 获取已处理的评论ID
    processed_ids = comment_state.get(doc_id, [])
    
    for comment in items:
        comment_id = comment.get('comment_id')
        if not comment_id:
            continue
            
        if comment_id in processed_ids:
            continue
            
        # 新评论！
        new_comments_found = True
        print(f"  🆕 新评论 ID: {comment_id}")
        print(f"     创建者: {comment.get('creator', {}).get('name', '未知')}")
        print(f"     内容: {comment.get('content', '')}")
        print(f"     引用: {comment.get('quote', '')}")
        print(f"     是否已解决: {comment.get('is_solved', False)}")
        
        # 检查回复
        replies = comment.get('reply_list', {}).get('items', [])
        if replies:
            print(f"     已有回复: {len(replies)} 条")

if not new_comments_found:
    print("\n✅ 没有发现新评论")