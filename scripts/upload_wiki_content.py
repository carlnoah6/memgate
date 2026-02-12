import requests
import json
import sys

# Configuration
DOC_TOKEN = "Z9D4d7PXMobUFRxgWwMluURGgzh"
ACCESS_TOKEN = "***TOKEN_REMOVED***"
API_URL = f"https://open.larksuite.com/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{DOC_TOKEN}/children"

# Read code content
with open("data/pipeline.py", "r") as f:
    code_content = f.read()

# Construct Blocks
# Block Types: 2=Text, 3=H1, 4=H2, 13=Ordered List, 14=Code
children = [
    {
        "block_type": 4, # Heading 2
        "heading2": {
            "elements": [{"text_run": {"content": "Design Overview", "text_style": {}}}]
        }
    },
    {
        "block_type": 2, # Text
        "text": {
            "elements": [{"text_run": {"content": "The Data Processing Pipeline MVP implements a 4-stage cleaning process designed for LLM training data preparation:", "text_style": {}}}]
        }
    },
    {
        "block_type": 13, # Ordered List
        "ordered": {
            "elements": [{"text_run": {"content": "Language Identification (Heuristic/FastText)", "text_style": {}}}]
        }
    },
    {
        "block_type": 13,
        "ordered": {
            "elements": [{"text_run": {"content": "Quality Filtering (Length & Symbol Ratio)", "text_style": {}}}]
        }
    },
    {
        "block_type": 13,
        "ordered": {
            "elements": [{"text_run": {"content": "Deduplication (Exact MD5)", "text_style": {}}}]
        }
    },
    {
        "block_type": 13,
        "ordered": {
            "elements": [{"text_run": {"content": "PII Scrubbing (Regex for Email/Phone/IP)", "text_style": {}}}]
        }
    },
    {
        "block_type": 4, # Heading 2
        "heading2": {
            "elements": [{"text_run": {"content": "Implementation (MVP)", "text_style": {}}}]
        }
    },
    {
        "block_type": 14, # Code Block
        "code": {
            "language": 16, # Python
            "elements": [{"text_run": {"content": code_content, "text_style": {}}}]
        }
    },
    {
        "block_type": 4, # Heading 2
        "heading2": {
            "elements": [{"text_run": {"content": "Next Steps", "text_style": {}}}]
        }
    },
    {
        "block_type": 13, # Ordered List
        "ordered": {
            "elements": [{"text_run": {"content": "Replace heuristic LangID with FastText model.", "text_style": {}}}]
        }
    },
    {
        "block_type": 13,
        "ordered": {
            "elements": [{"text_run": {"content": "Integrate Datatrove for distributed processing.", "text_style": {}}}]
        }
    }
]

payload = {
    "children": children,
    "index": -1
}

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json; charset=utf-8"
}

try:
    response = requests.post(API_URL, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
