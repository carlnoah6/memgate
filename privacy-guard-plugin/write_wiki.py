#!/usr/bin/env python3
"""
将 Wiki 内容分段写入到 Lark Wiki
每段不超过 4500 字符
"""

import json
import os
import re
from pathlib import Path

def read_token():
    """读取 Lark token"""
    token_path = Path("/home/ubuntu/.openclaw/workspace/data/lark-user-token.json")
    with open(token_path) as f:
        data = json.load(f)
        return data["access_token"]

def split_content(content, max_chars=4500):
    """将内容分段，每段不超过 max_chars 字符"""
    # 按标题分割
    sections = []
    current_section = []
    current_length = 0
    
    lines = content.split('\n')
    for line in lines:
        line_length = len(line) + 1  # +1 for newline
        
        # 如果当前段加上这行会超过限制，且当前段不为空，则保存当前段
        if current_length + line_length > max_chars and current_section:
            sections.append('\n'.join(current_section))
            current_section = [line]
            current_length = line_length
        else:
            current_section.append(line)
            current_length += line_length
    
    # 添加最后一段
    if current_section:
        sections.append('\n'.join(current_section))
    
    return sections

def create_blocks_for_section(text):
    """为文本段创建 blocks"""
    blocks = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
            
        # 判断 block 类型
        if line.startswith('# '):
            # 标题1
            blocks.append({
                "block_type": 3,  # Heading1
                "text": line[2:]
            })
        elif line.startswith('## '):
            # 标题2
            blocks.append({
                "block_type": 4,  # Heading2
                "text": line[3:]
            })
        elif line.startswith('### '):
            # 标题3
            blocks.append({
                "block_type": 5,  # Heading3
                "text": line[4:]
            })
        elif line.startswith('- '):
            # 无序列表
            blocks.append({
                "block_type": 12,  # Bullet
                "text": line[2:]
            })
        elif re.match(r'^\d+\. ', line):
            # 有序列表
            blocks.append({
                "block_type": 13,  # Ordered
                "text": line[line.find('. ')+2:]
            })
        elif line.startswith('```'):
            # 代码块 - 需要特殊处理
            continue  # 跳过代码块标记，在下面的逻辑中处理
        elif '```' in line:
            # 代码块内容
            code_content = line.replace('```', '').strip()
            if code_content:
                blocks.append({
                    "block_type": 14,  # Code
                    "text": code_content
                })
        elif line.strip() == '---' or line.strip() == '***':
            # 分隔线
            blocks.append({
                "block_type": 22  # Divider
            })
        else:
            # 普通文本
            blocks.append({
                "block_type": 2,  # Text
                "text": line
            })
    
    return blocks

def main():
    # 读取 Wiki 内容
    wiki_path = Path(__file__).parent / "WIKI_CONTENT.md"
    with open(wiki_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分段
    sections = split_content(content, max_chars=4000)
    
    print(f"内容已分为 {len(sections)} 段")
    
    # 读取 token
    token = read_token()
    print(f"Token 长度: {len(token)}")
    
    # 文档节点 token
    node_token = "KkFfwh3tWixqTJkEyCslpdr7gkf"
    
    # 为每段创建 blocks
    all_blocks = []
    for i, section in enumerate(sections):
        print(f"\n处理第 {i+1}/{len(sections)} 段，长度: {len(section)} 字符")
        blocks = create_blocks_for_section(section)
        all_blocks.extend(blocks)
    
    print(f"\n总共创建了 {len(all_blocks)} 个 blocks")
    
    # 保存 blocks 到文件，供后续使用
    blocks_file = Path(__file__).parent / "wiki_blocks.json"
    with open(blocks_file, 'w', encoding='utf-8') as f:
        json.dump(all_blocks, f, ensure_ascii=False, indent=2)
    
    print(f"\nBlocks 已保存到: {blocks_file}")
    
    # 生成写入脚本
    script_content = f'''#!/bin/bash

TOKEN="{token}"
NODE_TOKEN="{node_token}"
API_URL="https://open.larksuite.com/open-apis/wiki/v2/spaces/7604126789916479197/nodes/$NODE_TOKEN/blocks"

echo "开始写入 Wiki 内容..."

# 读取 blocks
BLOCKS=$(cat {blocks_file})

# 写入内容
curl -s -X POST "$API_URL" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d "$BLOCKS"

echo "Wiki 内容写入完成！"
'''
    
    script_file = Path(__file__).parent / "write_wiki_content.sh"
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    os.chmod(script_file, 0o755)
    print(f"写入脚本已生成: {script_file}")
    print("\n运行以下命令写入 Wiki 内容:")
    print(f"  {script_file}")

if __name__ == "__main__":
    main()