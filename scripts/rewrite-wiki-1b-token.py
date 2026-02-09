#!/usr/bin/env python3
"""
Rewrite the 1B Token Club Wiki document with proper Lark formatting.
- Headings → heading blocks (type 3-8)
- Tables → table blocks (type 31) with populated cells
- Bullet lists → bullet blocks (type 12)
- Numbered lists → ordered blocks (type 13)
- Regular text → text blocks (type 2)
- Dividers → divider blocks (type 22)
"""

import json
import re
import sys
import time
import requests

DOC_ID = "GtIudQ8sPoCtBVxc47olz1dPgMb"
API_BASE = "https://open.larksuite.com/open-apis"
SOURCE_FILE = "/home/ubuntu/.openclaw/workspace/memory/research/1b-token-daily-architecture-2026-02-09.md"
TOKEN_FILE = "/home/ubuntu/.openclaw/workspace/data/lark-user-token.json"

def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["access_token"]

def api_call(method, path, data=None, token=None):
    """Make API call with retry."""
    if token is None:
        token = get_token()
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for attempt in range(5):
        try:
            resp = requests.request(method, url, headers=headers, json=data if data else None)
            # Handle HTTP-level rate limiting (429)
            if resp.status_code == 429:
                wait = min(5 * (attempt + 1), 15)
                print(f"  Rate limited (429), waiting {wait}s (attempt {attempt+1})", file=sys.stderr)
                time.sleep(wait)
                continue
            if not resp.text.strip():
                print(f"  Empty response (attempt {attempt+1}), status={resp.status_code}", file=sys.stderr)
                if attempt < 2:
                    time.sleep(2)
                    continue
                return {"code": -1, "msg": "Empty response"}
            result = resp.json()
        except Exception as e:
            print(f"  Request error (attempt {attempt+1}): {e}", file=sys.stderr)
            if attempt < 2:
                time.sleep(2)
                continue
            return {"code": -1, "msg": str(e)}
        if result.get("code") == 0:
            return result
        # API-level rate limit
        if result.get("code") == 99991400:
            wait = min(5 * (attempt + 1), 15)
            print(f"  API rate limited, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        print(f"  API error (attempt {attempt+1}): {result.get('code')} {result.get('msg')}", file=sys.stderr)
        if attempt < 4:
            time.sleep(2)
    return result

def delete_all_blocks():
    """Delete all existing blocks from the document."""
    print("Step 1: Deleting existing blocks...")
    token = get_token()
    # Get all blocks
    resp = api_call("GET", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children?page_size=500", token=token)
    items = resp.get("data", {}).get("items", [])
    total = len(items)
    print(f"  Found {total} blocks to delete")
    
    if total == 0:
        return
    
    # Delete all at once using batch_delete with full range
    # Delete in batches of 50 from the end
    remaining = total
    while remaining > 0:
        batch_size = min(50, remaining)
        start = remaining - batch_size
        result = api_call("DELETE", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children/batch_delete",
                         {"start_index": start, "end_index": remaining}, token=token)
        if result.get("code") != 0:
            print(f"  Warning: Failed to batch delete [{start}:{remaining}]: {result.get('msg')}")
            # Fall back to single delete
            for i in range(remaining - 1, start - 1, -1):
                r = api_call("DELETE", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children/batch_delete",
                             {"start_index": i, "end_index": i + 1}, token=token)
                if r.get("code") != 0:
                    print(f"    Warning: Failed to delete index {i}: {r.get('msg')}")
                time.sleep(0.5)
            remaining = start
        else:
            remaining = start
            print(f"  Deleted batch, remaining: {remaining}")
        time.sleep(1)  # Rate limit between batches
    
    # Verify
    resp = api_call("GET", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children?page_size=10", token=token)
    remaining = len(resp.get("data", {}).get("items", []))
    print(f"  Remaining blocks: {remaining}")

def parse_text_with_bold(text):
    """Parse markdown bold (**text**) into Lark elements with bold styling."""
    elements = []
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            content = part[2:-2]
            elements.append({
                "text_run": {
                    "content": content,
                    "text_element_style": {"bold": True}
                }
            })
        else:
            elements.append({"text_run": {"content": part}})
    return elements if elements else [{"text_run": {"content": text}}]

def make_text_block(text, bold=False):
    """Create a text block (type 2)."""
    if bold:
        return {"block_type": 2, "text": {"elements": [{"text_run": {"content": text, "text_element_style": {"bold": True}}}]}}
    elements = parse_text_with_bold(text)
    return {"block_type": 2, "text": {"elements": elements}}

def make_heading_block(text, level):
    """Create a heading block. level 1→type 3, level 2→type 4, etc."""
    block_type = level + 2  # H1=3, H2=4, H3=5, H4=6
    field_name = f"heading{level}"
    elements = parse_text_with_bold(text)
    return {"block_type": block_type, field_name: {"elements": elements}}

def make_bullet_block(text):
    """Create a bullet list block (type 12)."""
    elements = parse_text_with_bold(text)
    return {"block_type": 12, "bullet": {"elements": elements}}

def make_ordered_block(text):
    """Create an ordered list block (type 13)."""
    elements = parse_text_with_bold(text)
    return {"block_type": 13, "ordered": {"elements": elements}}

def make_divider_block():
    """Create a divider block (type 22)."""
    return {"block_type": 22, "divider": {}}

def parse_markdown(filepath):
    """
    Parse markdown into a list of operations.
    Each op is one of:
    - ("block", block_dict)      — a simple block to write
    - ("table", headers, rows)   — a table to create
    """
    with open(filepath) as f:
        lines = f.readlines()
    
    ops = []
    i = 0
    
    while i < len(lines):
        line = lines[i].rstrip('\n')
        
        # Skip empty lines
        if not line.strip():
            i += 1
            continue
        
        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            ops.append(("block", make_heading_block(text, level)))
            i += 1
            continue
        
        # Table detection
        if line.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[-|: ]+\|', lines[i + 1]):
            # Parse table
            headers = [cell.strip() for cell in line.strip('|').split('|')]
            i += 2  # Skip header and separator
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [cell.strip() for cell in lines[i].strip().rstrip('|').lstrip('|').split('|')]
                rows.append(row)
                i += 1
            ops.append(("table", headers, rows))
            continue
        
        # Horizontal rule
        if re.match(r'^---+$', line):
            ops.append(("block", make_divider_block()))
            i += 1
            continue
        
        # Bullet list (- or *)
        bullet_match = re.match(r'^[\-\*]\s+(.+)', line)
        if bullet_match:
            text = bullet_match.group(1).strip()
            ops.append(("block", make_bullet_block(text)))
            i += 1
            continue
        
        # Ordered list
        ordered_match = re.match(r'^\d+\.\s+(.+)', line)
        if ordered_match:
            text = ordered_match.group(1).strip()
            ops.append(("block", make_ordered_block(text)))
            i += 1
            continue
        
        # Code block (skip entirely — not useful for Wiki display)
        if line.startswith('```'):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1  # Skip closing ```
            continue
        
        # Regular text
        # Collect consecutive text lines into one paragraph
        para_lines = [line]
        i += 1
        while i < len(lines):
            next_line = lines[i].rstrip('\n')
            if not next_line.strip():
                break
            if next_line.startswith('#') or next_line.startswith('|') or next_line.startswith('-') or next_line.startswith('*') or next_line.startswith('```') or re.match(r'^\d+\.', next_line):
                break
            para_lines.append(next_line)
            i += 1
        
        text = ' '.join(para_lines)
        ops.append(("block", make_text_block(text)))
    
    return ops

def write_blocks(blocks, index, token=None):
    """Write a batch of blocks at the given index. Max 50 per call."""
    if not blocks:
        return index
    if token is None:
        token = get_token()
    
    # Batch in groups of 50
    for batch_start in range(0, len(blocks), 50):
        batch = blocks[batch_start:batch_start + 50]
        result = api_call("POST", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children",
                         {"children": batch, "index": index}, token=token)
        if result.get("code") != 0:
            print(f"  Error writing batch at index {index}: {result.get('msg')}", file=sys.stderr)
            # Try one by one
            for block in batch:
                result = api_call("POST", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children",
                                 {"children": [block], "index": index}, token=token)
                if result.get("code") == 0:
                    index += 1
                else:
                    print(f"  Skipping block: {result.get('msg')}", file=sys.stderr)
                time.sleep(0.2)
        else:
            written = len(result.get("data", {}).get("children", []))
            index += written
        time.sleep(0.3)
    
    return index

def create_table(headers, rows, index, token=None):
    """Create a table with headers and rows at the given index.
    Lark API limits tables to 9 rows max per creation call.
    For larger tables, split into multiple tables (header repeated).
    """
    if token is None:
        token = get_token()
    
    MAX_DATA_ROWS = 8  # 8 data rows + 1 header = 9 total rows
    num_cols = len(headers)
    tables_created = 0
    
    # Split rows into chunks
    for chunk_start in range(0, len(rows), MAX_DATA_ROWS):
        chunk_rows = rows[chunk_start:chunk_start + MAX_DATA_ROWS]
        num_rows = len(chunk_rows) + 1  # +1 for header
        
        if chunk_start > 0:
            print(f"  Creating continuation table: {num_rows}x{num_cols} (rows {chunk_start+1}-{chunk_start+len(chunk_rows)})")
        else:
            print(f"  Creating table: {num_rows}x{num_cols} ({len(rows)} total data rows)")
        
        # Create the table structure
        result = api_call("POST", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children",
                         {"children": [{"block_type": 31, "table": {"property": {"row_size": num_rows, "column_size": num_cols}}}],
                          "index": index + tables_created}, token=token)
        
        if result.get("code") != 0:
            print(f"  Failed to create table: {result.get('msg')}", file=sys.stderr)
            continue
        
        table_block = result["data"]["children"][0]
        cell_ids = table_block["table"]["cells"]
        tables_created += 1
        
        # Populate header row (bold)
        for col_idx, header_text in enumerate(headers):
            cell_id = cell_ids[col_idx]
            elements = parse_text_with_bold(header_text)
            for el in elements:
                if "text_run" in el:
                    if "text_element_style" not in el["text_run"]:
                        el["text_run"]["text_element_style"] = {}
                    el["text_run"]["text_element_style"]["bold"] = True
            
            api_call("POST", f"/docx/v1/documents/{DOC_ID}/blocks/{cell_id}/children",
                    {"children": [{"block_type": 2, "text": {"elements": elements}}], "index": 0}, token=token)
            time.sleep(0.15)
        
        # Populate data rows
        for row_idx, row in enumerate(chunk_rows):
            for col_idx in range(min(len(row), num_cols)):
                cell_id = cell_ids[(row_idx + 1) * num_cols + col_idx]
                cell_text = row[col_idx]
                elements = parse_text_with_bold(cell_text)
                api_call("POST", f"/docx/v1/documents/{DOC_ID}/blocks/{cell_id}/children",
                        {"children": [{"block_type": 2, "text": {"elements": elements}}], "index": 0}, token=token)
                time.sleep(0.15)
            
            if (row_idx + 1) % 5 == 0:
                print(f"    Populated {row_idx + 1}/{len(chunk_rows)} rows...")
        
        time.sleep(0.5)
    
    return index + tables_created

def main():
    print("=" * 60)
    print("Rewriting 1B Token Club Wiki Document")
    print("=" * 60)
    
    # Step 1: Delete existing blocks
    delete_all_blocks()
    
    # Step 2: Parse markdown
    print("\nStep 2: Parsing markdown source...")
    ops = parse_markdown(SOURCE_FILE)
    
    block_count = sum(1 for op in ops if op[0] == "block")
    table_count = sum(1 for op in ops if op[0] == "table")
    print(f"  Parsed: {block_count} blocks, {table_count} tables")
    
    # Step 3: Write content
    print("\nStep 3: Writing content...")
    token = get_token()
    current_index = 0
    pending_blocks = []
    total_written = 0
    
    for op_idx, op in enumerate(ops):
        if op[0] == "block":
            pending_blocks.append(op[1])
            # Flush when we have 50 blocks or this is the last op
            if len(pending_blocks) >= 50 or op_idx == len(ops) - 1:
                current_index = write_blocks(pending_blocks, current_index, token)
                total_written += len(pending_blocks)
                print(f"  Written {total_written} blocks so far...")
                pending_blocks = []
        elif op[0] == "table":
            # Flush pending blocks first
            if pending_blocks:
                current_index = write_blocks(pending_blocks, current_index, token)
                total_written += len(pending_blocks)
                pending_blocks = []
            
            headers, rows = op[1], op[2]
            current_index = create_table(headers, rows, current_index, token)
            total_written += 1
            print(f"  Written {total_written} items so far (incl tables)...")
    
    # Flush remaining
    if pending_blocks:
        current_index = write_blocks(pending_blocks, current_index, token)
        total_written += len(pending_blocks)
    
    # Step 4: Verify
    print(f"\nStep 4: Verifying...")
    resp = api_call("GET", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children?page_size=500", token=token)
    final_count = len(resp.get("data", {}).get("items", []))
    print(f"  Final document has {final_count} top-level blocks")
    
    print(f"\n{'=' * 60}")
    print(f"Done! Total items written: {total_written}")
    print(f"Wiki URL: https://fg9w9yu3odc.sg.larksuite.com/wiki/V2hNwrjTtipsdLk0fVKlBjGQgcz")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
