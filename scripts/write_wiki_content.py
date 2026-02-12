import json
import requests
import sys

# Configuration
NODE_TOKEN = "Q0xGw5to6ijDGokUkNklVN69gxc"
OBJ_TOKEN = "N4RGdLxetot6vyx9KU6lZeobgWb"

# Load Token
try:
    with open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json', 'r') as f:
        ACCESS_TOKEN = json.load(f)['access_token']
except Exception as e:
    print(f"Error loading token: {e}")
    sys.exit(1)

# Helper to create blocks with correct keys
def create_block(content, block_type):
    # Mapping block_type ID to the specific key required by Lark API
    # 2=Text, 3=H1, 4=H2, 5=H3, 12=Bullet, 14=Code
    type_key_map = {
        2: "text",
        3: "heading1",
        4: "heading2",
        5: "heading3",
        12: "bullet",
        14: "code"
    }
    
    key = type_key_map.get(block_type)
    if not key:
        print(f"Unknown block type: {block_type}")
        return None

    block = {
        "block_type": block_type,
        key: {
            "elements": [{"text_run": {"content": content}}]
        }
    }
    
    # Special handling if needed (e.g., code language), but defaults often suffice.
    # For code blocks, Lark sometimes expects a language, but let's try basic first.
    if block_type == 14:
        block[key]["language"] = 1 # 1 = Plain Text usually, or just omit if optional
        
    return block

# Content Structure
blocks_data = [
    ("1. Overview", 3), # H1
    ("Target: Pre-training dataset size of 5 Trillion tokens.\nFocus: High-quality filtering, massive-scale deduplication, and efficient tokenization pipeline.", 2),
    
    ("2. Data Sources & Composition", 3), # H1
    ("Common Crawl (web dumps): 60-70%", 12),
    ("High-Quality Code (GitHub, StackOverflow): 10-15%", 12),
    ("Academic & Books (arXiv, PubMed, Copyright-free books): 10%", 12),
    ("Conversational & Encyclopedic (Wikipedia, Reddit - filtered): 5-10%", 12),

    ("3. Processing Pipeline Architecture", 3), # H1
    ("3.1 Ingestion & Normalization", 4), # H2
    ("Standardize all inputs to a unified JSONL/Parquet format. Extract text from HTML (WARC) using trafilatura or resiliparse.", 2),
    
    ("3.2 Deduplication (Crucial)", 4), # H2
    ("Exact Deduplication: SHA-256 over documents to remove identical copies.", 12),
    ("Fuzzy Deduplication: MinHash LSH (Locality Sensitive Hashing) to remove near-duplicates and SEO spam.", 12),
    
    ("3.3 Quality Filtering", 4), # H2
    ("Heuristic: Line length, symbol-to-text ratio, stop-word presence.", 12),
    ("Model-based: Train a light BERT/fastText classifier on high-quality data (Wikipedia/Books) vs low-quality (random CC).", 12),
    
    ("3.4 Safety & Redaction", 4), # H2
    ("PII Removal: Regex + NER to remove emails, phone numbers, IPs.", 12),
    ("Toxic Content Filtering: Blocklist-based and classifier-based removal.", 12),

    ("4. Infrastructure Estimates", 3), # H1
    ("Storage:\n- Raw Data (Compressed WARC): ~1.5 PB\n- Text Only (JSONL/Parquet): ~30-50 TB\n- Tokenized Data (uint16): ~10 TB\n\nCompute:\n- Framework: Ray Data or Apache Spark on K8s\n- Scale: 500-1000 nodes for 2-3 weeks processing time.", 14),
    
    ("5. Implementation Roadmap", 3), # H1
    ("Week 1: Pipeline Setup (Ray/Spark) & small scale test (100B tokens).", 12),
    ("Week 2-3: Full Common Crawl processing & Deduplication.", 12),
    ("Week 4: Quality Filtering & Tokenization.", 12),
]

children = [create_block(c, t) for c, t in blocks_data]

# Send Request
url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{OBJ_TOKEN}/blocks/{OBJ_TOKEN}/children"
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json; charset=utf-8"
}

payload = {
    "children": children,
    "index": 0
}

# print(json.dumps(payload, indent=2)) # Debug

response = requests.post(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")
print(response.text)
