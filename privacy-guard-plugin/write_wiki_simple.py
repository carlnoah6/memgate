#!/usr/bin/env python3
"""
使用正确的 Lark API 写入 Wiki 内容
"""

import json
import os
import time
from pathlib import Path

def read_token():
    """读取 Lark token"""
    token_path = Path("/home/ubuntu/.openclaw/workspace/data/lark-user-token.json")
    with open(token_path) as f:
        data = json.load(f)
        return data["access_token"]

def create_docx_content(text):
    """创建 docx 格式的内容"""
    # 简单的 markdown 转 docx blocks
    blocks = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
            
        if line.startswith('# '):
            blocks.append({
                "style": {
                    "heading_level": 1
                },
                "elements": [{
                    "text_run": {
                        "content": line[2:]
                    }
                }]
            })
        elif line.startswith('## '):
            blocks.append({
                "style": {
                    "heading_level": 2
                },
                "elements": [{
                    "text_run": {
                        "content": line[3:]
                    }
                }]
            })
        elif line.startswith('### '):
            blocks.append({
                "style": {
                    "heading_level": 3
                },
                "elements": [{
                    "text_run": {
                        "content": line[4:]
                    }
                }]
            })
        elif line.startswith('- '):
            blocks.append({
                "style": {
                    "list": {
                        "type": "bullet"
                    }
                },
                "elements": [{
                    "text_run": {
                        "content": line[2:]
                    }
                }]
            })
        elif line.startswith('```'):
            # 跳过代码块标记
            continue
        else:
            blocks.append({
                "elements": [{
                    "text_run": {
                        "content": line
                    }
                }]
            })
    
    return blocks

def main():
    # 读取 Wiki 内容
    wiki_path = Path(__file__).parent / "WIKI_CONTENT.md"
    with open(wiki_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 读取 token
    token = read_token()
    node_token = "KkFfwh3tWixqTJkEyCslpdr7gkf"
    
    print(f"Token 长度: {len(token)}")
    print(f"Node token: {node_token}")
    print(f"内容长度: {len(content)} 字符")
    
    # 创建请求数据
    # 根据 Lark API，我们需要使用文档创建/更新 API
    # 先尝试获取文档信息
    import requests
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 方法1: 使用文档创建API（可能不支持直接更新）
    # 方法2: 使用文档块API
    
    # 尝试使用文档块API
    url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{node_token}/blocks"
    
    # 将内容分成小块
    lines = content.split('\n')
    chunk_size = 50  # 每次处理50行
    for i in range(0, len(lines), chunk_size):
        chunk = '\n'.join(lines[i:i+chunk_size])
        
        # 创建 blocks
        blocks = create_docx_content(chunk)
        
        if not blocks:
            continue
            
        data = {
            "blocks": blocks
        }
        
        print(f"写入块 {i//chunk_size + 1}/{(len(lines)+chunk_size-1)//chunk_size}...")
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            print(f"响应: {response.status_code}")
            if response.status_code != 200:
                print(f"错误: {response.text}")
            
            # 避免速率限制
            time.sleep(1)
            
        except Exception as e:
            print(f"请求失败: {e}")
            break
    
    print("\nWiki 内容写入完成！")

if __name__ == "__main__":
    main()