#!/usr/bin/env python3
"""
更新 Wiki 文档内容
使用正确的 Lark API
"""

import json
import requests
import time
from pathlib import Path

def read_token():
    """读取 Lark token"""
    token_path = Path("/home/ubuntu/.openclaw/workspace/data/lark-user-token.json")
    with open(token_path) as f:
        data = json.load(f)
        return data["access_token"]

def create_blocks_from_markdown(content):
    """将 markdown 转换为 Lark 文档 blocks"""
    blocks = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        if not line:
            i += 1
            continue
            
        # 标题
        if line.startswith('# '):
            blocks.append({
                "block_type": 3,  # Heading1
                "heading1": {
                    "elements": [{
                        "text_run": {
                            "content": line[2:]
                        }
                    }]
                }
            })
        elif line.startswith('## '):
            blocks.append({
                "block_type": 4,  # Heading2
                "heading2": {
                    "elements": [{
                        "text_run": {
                            "content": line[3:]
                        }
                    }]
                }
            })
        elif line.startswith('### '):
            blocks.append({
                "block_type": 5,  # Heading3
                "heading3": {
                    "elements": [{
                        "text_run": {
                            "content": line[4:]
                        }
                    }]
                }
            })
        # 代码块
        elif line.startswith('```'):
            # 收集代码块内容
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].rstrip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            if code_lines:
                blocks.append({
                    "block_type": 14,  # Code
                    "code": {
                        "language": 1,  # Plain text
                        "elements": [{
                            "text_run": {
                                "content": '\n'.join(code_lines)
                            }
                        }]
                    }
                })
        # 列表
        elif line.startswith('- '):
            blocks.append({
                "block_type": 12,  # Bullet
                "bullet": {
                    "elements": [{
                        "text_run": {
                            "content": line[2:]
                        }
                    }]
                }
            })
        elif line.startswith('1. ') or line.startswith('2. ') or line.startswith('3. '):
            # 简单处理有序列表
            blocks.append({
                "block_type": 13,  # Ordered
                "ordered": {
                    "elements": [{
                        "text_run": {
                            "content": line[line.find('. ')+2:]
                        }
                    }]
                }
            })
        # 普通文本
        else:
            blocks.append({
                "block_type": 2,  # Text
                "text": {
                    "elements": [{
                        "text_run": {
                            "content": line
                        }
                    }]
                }
            })
        
        i += 1
    
    return blocks

def main():
    # 读取 Wiki 内容
    wiki_path = Path(__file__).parent / "WIKI_CONTENT.md"
    with open(wiki_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 读取 token
    token = read_token()
    obj_token = "FfUEdLWICoHO6ExKWBxlykvhgHd"  # 文档对象 token
    
    print(f"Token 长度: {len(token)}")
    print(f"文档 token: {obj_token}")
    print(f"内容长度: {len(content)} 字符")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 创建 blocks
    print("创建 blocks...")
    blocks = create_blocks_from_markdown(content)
    print(f"创建了 {len(blocks)} 个 blocks")
    
    # 分批上传 blocks（每次最多20个）
    batch_size = 20
    for batch_start in range(0, len(blocks), batch_size):
        batch_end = min(batch_start + batch_size, len(blocks))
        batch = blocks[batch_start:batch_end]
        
        print(f"上传 blocks {batch_start+1}-{batch_end}/{len(blocks)}...")
        
        # 构建请求数据
        data = {
            "blocks": batch
        }
        
        # 尝试使用文档块API
        url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{obj_token}/blocks/batch_create"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            print(f"响应状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    print(f"  ✓ 成功上传 {len(batch)} 个 blocks")
                else:
                    print(f"  ⚠️  API 错误: {result.get('msg')}")
                    print(f"    详情: {result}")
            else:
                print(f"  ❌ HTTP 错误: {response.text}")
                
        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
        
        # 避免速率限制
        if batch_end < len(blocks):
            time.sleep(1)
    
    print("\nWiki 内容更新完成！")
    print(f"文档 URL: https://open.larksuite.com/wiki/{obj_token}")

if __name__ == "__main__":
    main()