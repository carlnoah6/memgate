#!/usr/bin/env python3
"""
Markdown → Lark Wiki DocX blocks 转换 + 上传
将 markdown 文件转换为 Lark DocX blocks 并写入 Wiki 文档

用法:
    python3 scripts/md-to-lark-wiki.py <obj_token> < report.md
    python3 scripts/md-to-lark-wiki.py <obj_token> --file report.md
    
    # 创建新文档并写入:
    python3 scripts/md-to-lark-wiki.py --create --space <space_id> --parent <parent_token> --title "标题" < report.md
"""

import json, urllib.request, urllib.error, re, sys, time, argparse

def get_token():
    with open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json') as f:
        return json.load(f)['access_token']

BASE = "https://open.larksuite.com/open-apis"

def api(token, method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"API error {e.code}: {err[:200]}", file=sys.stderr)
        return {"code": e.code, "error": err}

def parse_inline(text):
    """Parse **bold** and `code` into Lark text_run elements with proper styling"""
    elements = []
    pos = 0
    for m in re.finditer(r'\*\*(.+?)\*\*|`(.+?)`', text):
        if m.start() > pos:
            elements.append({"text_run": {"content": text[pos:m.start()]}})
        if m.group(1):  # **bold**
            elements.append({"text_run": {"content": m.group(1), "text_element_style": {"bold": True}}})
        elif m.group(2):  # `code`
            elements.append({"text_run": {"content": m.group(2), "text_element_style": {"inline_code": True}}})
        pos = m.end()
    if pos < len(text):
        elements.append({"text_run": {"content": text[pos:]}})
    return elements if elements else [{"text_run": {"content": text}}]

def md_to_blocks(md_text):
    """Convert markdown text to Lark DocX blocks"""
    blocks = []
    for line in md_text.strip().split('\n'):
        s = line.strip()
        if not s:
            continue
        # Skip ugly separator lines
        if re.match(r'^[—─━\-]{5,}$', s):
            blocks.append({"block_type": 22, "divider": {}})
            continue
        # Headings
        if s.startswith('# '):
            blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": s[2:]}}]}})
        elif s.startswith('## '):
            blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": s[3:]}}]}})
        elif s.startswith('### '):
            blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": s[4:]}}]}})
        # Blockquote → italic text (type 15 unreliable for creation)
        elif s.startswith('> '):
            blocks.append({"block_type": 2, "text": {"elements": [
                {"text_run": {"content": s[2:], "text_element_style": {"italic": True}}}
            ]}})
        # Bullet
        elif s.startswith('• ') or s.startswith('- ') or (s.startswith('* ') and not s.startswith('**')):
            blocks.append({"block_type": 12, "bullet": {"elements": parse_inline(s[2:])}})
        # Indented bullet
        elif re.match(r'^\s+[•\-\*]', s):
            text = re.sub(r'^\s+[•\-\*]\s*', '', s)
            blocks.append({"block_type": 12, "bullet": {"elements": parse_inline(text)}})
        # Numbered list
        elif re.match(r'^(\d+)\.\s+(.+)', s):
            m = re.match(r'^(\d+)\.\s+(.+)', s)
            blocks.append({"block_type": 13, "ordered": {"elements": parse_inline(m.group(2))}})
        # Regular text
        else:
            blocks.append({"block_type": 2, "text": {"elements": parse_inline(s)}})
    return blocks

def clear_document(token, obj_token):
    """Remove all content from a document"""
    resp = api(token, "GET", f"/docx/v1/documents/{obj_token}/blocks?page_size=200")
    if resp.get("code") != 0:
        return False
    items = resp.get("data", {}).get("items", [])
    root = items[0] if items else None
    if root and root.get("children"):
        api(token, "DELETE", f"/docx/v1/documents/{obj_token}/blocks/{root['block_id']}/children/batch_delete", {
            "start_index": 0, "end_index": len(root["children"])
        })
        time.sleep(0.5)
    return True

def write_blocks(token, obj_token, blocks):
    """Write blocks to document in batches"""
    idx = 0
    batch_size = 30
    success = True
    while idx < len(blocks):
        batch = blocks[idx:idx+batch_size]
        result = api(token, "POST", f"/docx/v1/documents/{obj_token}/blocks/{obj_token}/children", {
            "children": batch, "index": idx
        })
        code = result.get("code", -1)
        if code == 429:
            print("Rate limited, waiting 2s...", file=sys.stderr)
            time.sleep(2)
            continue  # Retry same batch
        if code != 0:
            print(f"Failed batch {idx}-{idx+len(batch)}: {result.get('error','')[:200]}", file=sys.stderr)
            success = False
            break
        idx += len(batch)
        time.sleep(0.3)
    return success

def create_wiki_node(token, space_id, parent_token, title):
    """Create a new Wiki node and return (node_token, obj_token)"""
    result = api(token, "POST", f"/wiki/v2/spaces/{space_id}/nodes", {
        "obj_type": "docx",
        "parent_node_token": parent_token,
        "title": title
    })
    if result.get("code") == 0:
        node = result["data"]["node"]
        return node["node_token"], node["obj_token"]
    print(f"Failed to create wiki node: {result}", file=sys.stderr)
    return None, None

def main():
    parser = argparse.ArgumentParser(description='Markdown → Lark Wiki DocX')
    parser.add_argument('obj_token', nargs='?', help='Existing document obj_token')
    parser.add_argument('--file', '-f', help='Input markdown file (default: stdin)')
    parser.add_argument('--create', action='store_true', help='Create new Wiki node')
    parser.add_argument('--space', help='Wiki space ID (for --create)')
    parser.add_argument('--parent', help='Parent node token (for --create)')
    parser.add_argument('--title', help='Document title (for --create)')
    args = parser.parse_args()

    # Read input
    if args.file:
        with open(args.file) as f:
            md_text = f.read()
    else:
        md_text = sys.stdin.read()

    token = get_token()
    blocks = md_to_blocks(md_text)
    print(f"Converted to {len(blocks)} blocks")

    # Create or use existing document
    obj_token = args.obj_token
    node_token = None
    if args.create:
        if not all([args.space, args.parent, args.title]):
            print("--create requires --space, --parent, and --title", file=sys.stderr)
            sys.exit(1)
        node_token, obj_token = create_wiki_node(token, args.space, args.parent, args.title)
        if not obj_token:
            sys.exit(1)
        print(f"Created wiki node: node={node_token} obj={obj_token}")
    
    if not obj_token:
        print("No obj_token provided", file=sys.stderr)
        sys.exit(1)

    # Clear and write
    clear_document(token, obj_token)
    if write_blocks(token, obj_token, blocks):
        print(f"OK: {len(blocks)} blocks written to {obj_token}")
        if node_token:
            print(f"URL: https://fg9w9yu3odc.sg.larksuite.com/wiki/{node_token}")
    else:
        print("FAILED: Some blocks could not be written", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
