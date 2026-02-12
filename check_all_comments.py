#!/usr/bin/env python3
import json
import subprocess
import sys

# 获取 user_access_token
with open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json', 'r') as f:
    user_token_data = json.load(f)
    user_token = user_token_data['access_token']

# 读取 tracked docs
with open('/home/ubuntu/.openclaw/workspace/data/tracked-docs.json', 'r') as f:
    tracked_docs = json.load(f)

# 读取 comment state
with open('/home/ubuntu/.openclaw/workspace/data/comment-state.json', 'r') as f:
    comment_state = json.load(f)

print("检查文档评论状态...")

for doc in tracked_docs[:10]:  # 先检查前10个文档
    if doc['file_type'] != 'docx':
        continue
    
    doc_id = doc['id']
    node_token = doc['node_token']
    title = doc['title']
    
    print(f"\n文档: {title}")
    print(f"  ID: {doc_id}")
    print(f"  Token: {node_token}")
    
    # 获取评论
    result = subprocess.run([
        'curl', '-s', '-X', 'GET',
        f'https://open.larksuite.com/open-apis/drive/v1/files/{node_token}/comments?file_type=docx',
        '-H', f'Authorization: Bearer {user_token}'
    ], capture_output=True, text=True)
    
    try:
        comments_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  错误: 无法解析JSON响应")
        print(f"  响应: {result.stdout[:200]}")
        continue
    
    if comments_data.get('code') != 0:
        print(f"  API 错误: {comments_data.get('msg')}")
        continue
    
    items = comments_data.get('data', {}).get('items', [])
    if not items:
        print(f"  无评论")
        continue
    
    print(f"  找到 {len(items)} 条评论")
    
    # 检查未解决的评论
    unsolved = [c for c in items if not c.get('is_solved', False)]
    if unsolved:
        print(f"  ⚠️ 有 {len(unsolved)} 条未解决评论")
        for comment in unsolved[:3]:  # 只显示前3条
            comment_id = comment.get('comment_id')
            print(f"    - ID: {comment_id}, 内容: {comment.get('content', '')[:50]}...")
    else:
        print(f"  ✅ 所有评论已解决")