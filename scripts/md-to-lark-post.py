#!/usr/bin/env python3
"""
Markdown → Lark Post 格式转换器
将 markdown 日报转换为 Lark "post" 消息格式（富文本：粗体、链接、换行）

用法:
    python3 scripts/md-to-lark-post.py < report.md
    cat report.md | python3 scripts/md-to-lark-post.py

输出: JSON 字符串，可直接用于 msg_type=post 的 content 字段
"""

import sys
import json
import re


def parse_inline(text):
    """解析行内格式：**bold**、`code`、[link](url)"""
    elements = []
    pos = 0
    # Pattern: **bold** or `code` or [text](url)
    pattern = re.compile(r'\*\*(.+?)\*\*|`(.+?)`|\[(.+?)\]\((.+?)\)')
    
    for m in pattern.finditer(text):
        # Add preceding plain text
        if m.start() > pos:
            elements.append({"tag": "text", "text": text[pos:m.start()]})
        
        if m.group(1):  # **bold**
            elements.append({"tag": "text", "text": m.group(1), "style": ["bold"]})
        elif m.group(2):  # `code`
            elements.append({"tag": "text", "text": m.group(2), "style": ["bold"]})
        elif m.group(3):  # [text](url)
            elements.append({"tag": "a", "text": m.group(3), "href": m.group(4)})
        
        pos = m.end()
    
    # Remaining text
    if pos < len(text):
        elements.append({"tag": "text", "text": text[pos:]})
    
    return elements if elements else [{"tag": "text", "text": text}]


def md_to_post(md_text):
    """Convert markdown to Lark post format"""
    lines = md_text.strip().split('\n')
    content = []  # list of paragraphs (each is a list of elements)
    title = ""
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines (add spacing)
        if not stripped:
            content.append([{"tag": "text", "text": ""}])
            continue
        
        # Skip ugly separators
        if re.match(r'^[—─━-]{5,}$', stripped):
            continue
        
        # H1: # Title → extract as post title
        if stripped.startswith('# ') and not title:
            title = stripped[2:].strip()
            continue
        
        # H2: ## Section → bold line
        if stripped.startswith('## '):
            heading = stripped[3:].strip()
            content.append([{"tag": "text", "text": f"\n━━ {heading} ━━", "style": ["bold"]}])
            continue
        
        # H3: ### Subsection → bold
        if stripped.startswith('### '):
            heading = stripped[4:].strip()
            content.append([{"tag": "text", "text": f"\n{heading}", "style": ["bold"]}])
            continue
        
        # Blockquote: > text
        if stripped.startswith('> '):
            text = stripped[2:].strip()
            content.append(parse_inline(f"📎 {text}"))
            continue
        
        # Bullet: • or - or *
        if stripped.startswith('• ') or stripped.startswith('- ') or (stripped.startswith('* ') and not stripped.startswith('**')):
            text = stripped[2:].strip()
            content.append(parse_inline(f"  • {text}"))
            continue
        
        # Indented bullet
        if re.match(r'^\s+[•\-\*]', stripped):
            text = re.sub(r'^\s+[•\-\*]\s*', '', stripped)
            content.append(parse_inline(f"    ◦ {text}"))
            continue
        
        # Numbered list: 1. text
        m = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if m:
            content.append(parse_inline(f"  {m.group(1)}. {m.group(2)}"))
            continue
        
        # Horizontal rule
        if re.match(r'^---+$', stripped):
            content.append([{"tag": "text", "text": "─────────────────"}])
            continue
        
        # Regular text
        content.append(parse_inline(stripped))
    
    # Build post structure
    post = {
        "zh_cn": {
            "title": title or "日报",
            "content": content
        }
    }
    
    return json.dumps(post, ensure_ascii=False)


if __name__ == "__main__":
    md_text = sys.stdin.read()
    print(md_to_post(md_text))
