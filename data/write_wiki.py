#!/usr/bin/env python3
"""Write markdown content to Lark docx documents as text blocks."""
import json
import requests
import sys
import time

TOKEN = "***TOKEN_REMOVED***"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def split_into_paragraphs(md_content):
    """Split markdown into paragraphs (by double newline), preserving structure."""
    # Split by lines, group into paragraphs
    lines = md_content.strip().split('\n')
    paragraphs = []
    current = []
    
    for line in lines:
        if line.strip() == '' and current:
            paragraphs.append('\n'.join(current))
            current = []
        elif line.strip() == '---':
            if current:
                paragraphs.append('\n'.join(current))
                current = []
            paragraphs.append('───────────────────────────')
        else:
            current.append(line)
    
    if current:
        paragraphs.append('\n'.join(current))
    
    # Filter empty and skip the title (first heading)
    result = []
    for p in paragraphs:
        stripped = p.strip()
        if not stripped:
            continue
        # Clean markdown formatting for plain text
        result.append(stripped)
    
    return result

def create_text_block(content):
    """Create a text block (block_type=2) payload."""
    return {
        "block_type": 2,
        "text": {
            "elements": [
                {
                    "text_run": {
                        "content": content,
                        "text_element_style": {}
                    }
                }
            ],
            "style": {}
        }
    }

def write_to_doc(doc_id, md_content):
    """Write markdown content to a docx document."""
    paragraphs = split_into_paragraphs(md_content)
    
    # Lark API allows batch creating children blocks
    # POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children
    # The block_id is the page block (same as doc_id for root)
    
    url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    
    # Batch in groups of 50 (API limit)
    batch_size = 50
    total = 0
    for i in range(0, len(paragraphs), batch_size):
        batch = paragraphs[i:i+batch_size]
        children = [create_text_block(p) for p in batch]
        
        payload = {
            "children": children,
            "index": -1  # append at end
        }
        
        resp = requests.post(url, headers=HEADERS, json=payload)
        data = resp.json()
        
        if data.get("code") != 0:
            print(f"  ERROR batch {i//batch_size + 1}: {data.get('msg', 'unknown')}")
            print(f"  Full response: {json.dumps(data, indent=2)}")
            return False
        else:
            total += len(batch)
            print(f"  Batch {i//batch_size + 1}: wrote {len(batch)} blocks (total: {total}/{len(paragraphs)})")
        
        time.sleep(0.3)  # rate limit
    
    print(f"  ✅ Done: {total} blocks written to {doc_id}")
    return True

def main():
    docs = [
        {
            "doc_id": "W9UcdpVmwoFehdxqYCvl6EytgcT",
            "file": "/home/ubuntu/.openclaw/workspace/memory/research/tokenizer-design-2026-02-08.md",
            "title": "Tokenizer 设计"
        },
        {
            "doc_id": "RmIzdrsnpomzPrxhcsIl6rBughc",
            "file": "/home/ubuntu/.openclaw/workspace/memory/research/llm-training-framework-comparison-2026-02-08.md",
            "title": "训练框架对比"
        },
        {
            "doc_id": "QTf1d0WMVoezB6xVVeLlEQmEgcb",
            "file": "/home/ubuntu/.openclaw/workspace/memory/research/hardware-cost-analysis-2026-02-08.md",
            "title": "硬件与成本分析"
        }
    ]
    
    for doc in docs:
        print(f"\n📝 Writing: {doc['title']} → {doc['doc_id']}")
        with open(doc['file'], 'r') as f:
            content = f.read()
        
        # Skip the first line (title) since the doc already has it
        lines = content.split('\n')
        # Find the first non-title content (skip # Title line)
        start = 0
        for j, line in enumerate(lines):
            if line.startswith('# '):
                start = j + 1
                break
        content = '\n'.join(lines[start:])
        
        success = write_to_doc(doc['doc_id'], content)
        if not success:
            print(f"  ❌ Failed to write {doc['title']}")
            sys.exit(1)
        time.sleep(0.5)
    
    print("\n✅ All 3 documents written successfully!")

if __name__ == "__main__":
    main()
