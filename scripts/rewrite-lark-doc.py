#!/usr/bin/env python3
"""Rewrite 1B Token Club Wiki doc on Lark with proper formatting.

Correct Lark Docx block_type mapping:
  1  = Page (root)
  2  = Text (paragraph)
  3  = Heading1 → "heading1"
  4  = Heading2 → "heading2"
  5  = Heading3 → "heading3"
  6  = Heading4 → "heading4"
  12 = Bullet   → "bullet"
  13 = Ordered  → "ordered"
  14 = Code     → "code"
  15 = Quote    → "quote"
  22 = Divider  → "divider"
"""

import json
import time
import re
import requests
import sys

TOKEN = json.load(open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json'))['access_token']
DOC_ID = "GtIudQ8sPoCtBVxc47olz1dPgMb"
BASE = "https://open.larksuite.com/open-apis/docx/v1"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Heading level → (block_type, field_name)
HEADING_MAP = {
    1: (3, "heading1"),
    2: (4, "heading2"),
    3: (5, "heading3"),
    4: (6, "heading4"),
    5: (7, "heading5"),
    6: (8, "heading6"),
}

def api_get(path):
    r = requests.get(f"{BASE}{path}", headers=HEADERS)
    return r.json()

def api_post(path, data):
    r = requests.post(f"{BASE}{path}", headers=HEADERS, json=data)
    try:
        return r.json()
    except:
        return {"code": -1, "msg": f"HTTP {r.status_code}: {r.text[:200]}"}

def api_delete(path, data):
    r = requests.request("DELETE", f"{BASE}{path}", headers=HEADERS, json=data)
    try:
        return r.json()
    except:
        return {"code": -1, "msg": f"HTTP {r.status_code}"}

# --- Step 1: Clear document ---
def clear_document():
    resp = api_get(f"/documents/{DOC_ID}/blocks/{DOC_ID}")
    if resp.get("code") != 0:
        print(f"Error: {resp}")
        return False
    children = resp.get("data", {}).get("block", {}).get("children", [])
    count = len(children)
    print(f"Found {count} children blocks to delete")
    if count == 0:
        return True
    # Delete from end to start
    for i in range(count - 1, -1, -1):
        api_delete(f"/documents/{DOC_ID}/blocks/{DOC_ID}/children/batch_delete",
                   {"start_index": i, "end_index": i + 1})
        time.sleep(0.2)
    print("All blocks deleted")
    return True

# --- Block builders ---

def text_run(content, bold=False, italic=False, inline_code=False):
    run = {"content": content}
    style = {}
    if bold: style["bold"] = True
    if italic: style["italic"] = True
    if inline_code: style["inline_code"] = True
    if style:
        run["text_element_style"] = style
    return {"text_run": run}

def parse_inline(text):
    """Parse inline markdown formatting into text_run elements."""
    elements = []
    pattern = r'(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|~~(.+?)~~)'
    last_end = 0
    for m in re.finditer(pattern, text):
        if m.start() > last_end:
            plain = text[last_end:m.start()]
            if plain:
                elements.append(text_run(plain))
        if m.group(2):      # ***bold italic***
            elements.append(text_run(m.group(2), bold=True, italic=True))
        elif m.group(3):    # **bold**
            elements.append(text_run(m.group(3), bold=True))
        elif m.group(4):    # *italic*
            elements.append(text_run(m.group(4), italic=True))
        elif m.group(5):    # `code`
            elements.append(text_run(m.group(5), inline_code=True))
        elif m.group(6):    # ~~strikethrough~~
            elements.append(text_run(m.group(6)))
        last_end = m.end()
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            elements.append(text_run(remaining))
    if not elements:
        elements.append(text_run(text if text else " "))
    return elements

def make_heading(text, level):
    bt, field = HEADING_MAP.get(level, (4, "heading2"))
    return {"block_type": bt, field: {"elements": parse_inline(text)}}

def make_paragraph(text):
    if not text.strip():
        return None
    return {"block_type": 2, "text": {"elements": parse_inline(text)}}

def make_bullet(text):
    return {"block_type": 12, "bullet": {"elements": parse_inline(text)}}

def make_ordered(text):
    return {"block_type": 13, "ordered": {"elements": parse_inline(text)}}

def make_divider():
    return {"block_type": 22, "divider": {}}

def make_quote(text):
    return {"block_type": 15, "quote": {"elements": parse_inline(text)}}

# --- Parse markdown ---

def parse_table_to_blocks(table_lines):
    """Convert markdown table to paragraph blocks (since Lark API doesn't support table creation easily)."""
    blocks = []
    rows = []
    for line in table_lines:
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if all(re.match(r'^[-:]+$', c) for c in cells):
            continue  # Skip separator
        rows.append(cells)
    
    if not rows:
        return blocks
    
    # First row as bold header
    header = rows[0]
    header_text = " | ".join(header)
    blocks.append({"block_type": 2, "text": {"elements": [text_run(header_text, bold=True)]}})
    
    # Data rows as bullets for readability
    for row in rows[1:]:
        # Pair with headers if available
        if len(header) == len(row):
            parts = []
            for h, v in zip(header, row):
                parts.append(f"{h}: {v}")
            row_text = " | ".join(parts)
        else:
            row_text = " | ".join(row)
        b = make_bullet(row_text)
        if b:
            blocks.append(b)
    
    return blocks

def parse_markdown(md_text):
    blocks = []
    lines = md_text.split('\n')
    i = 0
    in_code_block = False
    code_content = []
    code_lang = ""
    table_lines = []
    in_table = False
    
    while i < len(lines):
        line = lines[i]
        
        # Code block toggle
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block - convert to paragraphs (skip architecture diagrams)
                # Only include if it looks like meaningful code, not ASCII art
                is_ascii_art = any('┌' in l or '└' in l or '│' in l or '─' in l for l in code_content)
                if not is_ascii_art and code_content:
                    # Add code as quote blocks for visual distinction
                    for cl in code_content:
                        if cl.strip():
                            blocks.append(make_quote(cl))
                code_content = []
                code_lang = ""
                in_code_block = False
            else:
                if in_table and table_lines:
                    blocks.extend(parse_table_to_blocks(table_lines))
                    table_lines = []
                    in_table = False
                in_code_block = True
                lang_match = re.match(r'^```(\w+)', line.strip())
                code_lang = lang_match.group(1) if lang_match else ""
            i += 1
            continue
        
        if in_code_block:
            code_content.append(line)
            i += 1
            continue
        
        # Table detection
        if line.strip().startswith('|') and '|' in line.strip()[1:]:
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            i += 1
            continue
        elif in_table:
            blocks.extend(parse_table_to_blocks(table_lines))
            table_lines = []
            in_table = False
        
        # Empty line - skip
        if not line.strip():
            i += 1
            continue
        
        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            txt = heading_match.group(2).strip()
            blocks.append(make_heading(txt, level))
            i += 1
            continue
        
        # Divider
        if re.match(r'^---+\s*$', line.strip()):
            blocks.append(make_divider())
            i += 1
            continue
        
        # Blockquote
        if line.strip().startswith('>'):
            quote_text = line.strip()[1:].strip()
            if quote_text:
                blocks.append(make_quote(quote_text))
            i += 1
            continue
        
        # Unordered list
        bullet_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        if bullet_match:
            txt = bullet_match.group(2)
            blocks.append(make_bullet(txt))
            i += 1
            continue
        
        # Ordered list
        ordered_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if ordered_match:
            txt = ordered_match.group(2)
            blocks.append(make_ordered(txt))
            i += 1
            continue
        
        # Regular paragraph - collect consecutive lines
        para_lines = [line]
        i += 1
        while i < len(lines):
            nl = lines[i]
            if (not nl.strip() or
                nl.strip().startswith('#') or
                nl.strip().startswith('```') or
                nl.strip().startswith('|') or
                re.match(r'^\s*[-*+]\s', nl) or
                nl.strip().startswith('>') or
                re.match(r'^---+\s*$', nl.strip()) or
                re.match(r'^\s*\d+\.\s', nl)):
                break
            para_lines.append(nl)
            i += 1
        
        para_text = ' '.join(l.strip() for l in para_lines)
        block = make_paragraph(para_text)
        if block:
            blocks.append(block)
    
    # Flush remaining table
    if in_table and table_lines:
        blocks.extend(parse_table_to_blocks(table_lines))
    
    return blocks

# --- Write blocks in batches ---
def write_blocks(blocks, batch_size=30):
    total = len(blocks)
    print(f"Total blocks to write: {total}")
    
    written = 0
    batch_num = 0
    errors = 0
    
    while written < total:
        batch = blocks[written:written + batch_size]
        batch_num += 1
        
        # Try writing the batch
        payload = {"children": batch, "index": written}
        result = api_post(f"/documents/{DOC_ID}/blocks/{DOC_ID}/children", payload)
        
        if result.get("code") == 0:
            print(f"  Batch {batch_num}: wrote {len(batch)} blocks ({written}-{written+len(batch)-1}) ✓")
            written += len(batch)
        else:
            print(f"  Batch {batch_num} failed: {result.get('msg', '')} - trying one by one...")
            # Write one by one
            for j, single_block in enumerate(batch):
                single_payload = {"children": [single_block], "index": written + j}
                single_result = api_post(f"/documents/{DOC_ID}/blocks/{DOC_ID}/children", single_payload)
                if single_result.get("code") != 0:
                    errors += 1
                    bt = single_block.get("block_type")
                    print(f"    Error at {written+j} (type={bt}): {single_result.get('msg', '')}")
                    # Try to get more detail
                    if 'error' in single_result:
                        err = single_result['error']
                        print(f"      Detail: {json.dumps(err, ensure_ascii=False)[:300]}")
                time.sleep(0.15)
            written += len(batch)
        
        time.sleep(0.4)
    
    print(f"\nDone! Wrote {total} blocks ({errors} errors)")
    return errors

# --- Main ---
if __name__ == "__main__":
    with open('/home/ubuntu/.openclaw/workspace/memory/research/1b-token-daily-architecture-2026-02-09.md', 'r') as f:
        md_content = f.read()
    
    print("=" * 50)
    print("STEP 1: Clear document")
    print("=" * 50)
    clear_document()
    time.sleep(1)
    
    print("\n" + "=" * 50)
    print("STEP 2: Parse markdown")
    print("=" * 50)
    blocks = parse_markdown(md_content)
    print(f"Parsed {len(blocks)} blocks")
    
    # Preview
    type_counts = {}
    for b in blocks:
        bt = b.get("block_type")
        type_counts[bt] = type_counts.get(bt, 0) + 1
    print(f"Block types: {type_counts}")
    
    print("\n" + "=" * 50)
    print("STEP 3: Write blocks")
    print("=" * 50)
    errors = write_blocks(blocks, batch_size=30)
    
    if errors == 0:
        print("\n✅ Document rewrite complete!")
    else:
        print(f"\n⚠️ Document rewrite complete with {errors} errors")
