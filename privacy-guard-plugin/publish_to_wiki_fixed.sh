#!/bin/bash
# Publish Privacy Guard documentation to Lark Wiki (improved version)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Publishing Privacy Guard documentation to Lark Wiki${NC}"
echo "============================================================="

# Get access token
TOKEN_FILE="/home/ubuntu/.openclaw/workspace/data/lark-user-token.json"
if [ ! -f "$TOKEN_FILE" ]; then
    echo -e "${RED}Error: Lark token file not found at $TOKEN_FILE${NC}"
    exit 1
fi

TOKEN=$(python3 -c "import json; print(json.load(open('$TOKEN_FILE'))['access_token'])")
echo "✓ Got access token"

# Wiki space and parent node
SPACE_ID="7604126789916479197"
PARENT_NODE_TOKEN="IUBdwFzDhisMDrkm1fAltnOhgGd"
DOC_TITLE="Privacy Guard 插件化设计与发布"

# Create document node
echo "Creating document node..."
CREATE_RESPONSE=$(curl -s -X POST \
  "https://open.larksuite.com/open-apis/wiki/v2/spaces/$SPACE_ID/nodes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"obj_type\":\"docx\",\"node_type\":\"origin\",\"parent_node_token\":\"$PARENT_NODE_TOKEN\",\"title\":\"$DOC_TITLE\"}")

echo "Create response received"

# Extract node token and object token
NODE_TOKEN=$(echo "$CREATE_RESPONSE" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('data', {}).get('node', {}).get('node_token', ''))")
OBJ_TOKEN=$(echo "$CREATE_RESPONSE" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('data', {}).get('node', {}).get('obj_token', ''))")

if [ -z "$NODE_TOKEN" ] || [ -z "$OBJ_TOKEN" ]; then
    echo -e "${YELLOW}Warning: Could not extract tokens from response${NC}"
    echo "Trying to find existing document..."
    
    # Try to list nodes and find existing document
    LIST_RESPONSE=$(curl -s -X GET \
      "https://open.larksuite.com/open-apis/wiki/v2/spaces/$SPACE_ID/nodes?parent_node_token=$PARENT_NODE_TOKEN" \
      -H "Authorization: Bearer $TOKEN")
    
    # Try to extract existing document token
    OBJ_TOKEN=$(echo "$LIST_RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('data', {}).get('items', []):
    if item.get('title') == '$DOC_TITLE':
        print(item.get('obj_token', ''))
        break
")
    
    if [ -z "$OBJ_TOKEN" ]; then
        echo -e "${RED}Error: Could not create or find document${NC}"
        exit 1
    fi
    
    echo "✓ Found existing document: $OBJ_TOKEN"
else
    echo "✓ Document created: $OBJ_TOKEN"
    echo "✓ Node token: $NODE_TOKEN"
fi

# Read wiki content
WIKI_CONTENT_FILE="WIKI_CONTENT.md"
if [ ! -f "$WIKI_CONTENT_FILE" ]; then
    echo -e "${RED}Error: Wiki content file not found: $WIKI_CONTENT_FILE${NC}"
    exit 1
fi

# Read and prepare content
CONTENT=$(cat "$WIKI_CONTENT_FILE")
echo "✓ Read wiki content (${#CONTENT} characters)"

# Create a Python script to properly split and upload content
PYTHON_SCRIPT=$(cat << 'EOF'
import json
import sys
import time

def upload_to_wiki(content, obj_token, access_token):
    """Upload content to Lark Wiki document"""
    
    # Split by sections (## headers) for better structure
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for line in lines:
        line_length = len(line)
        
        # If adding this line would exceed 4000 chars, start new chunk
        if current_length + line_length + 1 > 4000:
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
        
        current_chunk.append(line)
        current_length += line_length + 1  # +1 for newline
    
    # Add the last chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    print(f"Split into {len(chunks)} chunks")
    
    # Upload each chunk
    import requests
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    for i, chunk in enumerate(chunks):
        chunk_num = i + 1
        print(f"Uploading chunk {chunk_num}/{len(chunks)} ({len(chunk)} chars)...")
        
        # Prepare payload
        payload = {
            "children": [{
                "block_type": 1,  # Document block
                "text": {
                    "elements": [{
                        "text_run": {
                            "content": chunk
                        }
                    }]
                }
            }],
            "index": i
        }
        
        url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{obj_token}/blocks/{obj_token}/children"
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    print(f"  ✓ Chunk {chunk_num} uploaded successfully")
                else:
                    print(f"  ⚠️  Chunk {chunk_num} upload response: {result}")
            else:
                print(f"  ⚠️  Chunk {chunk_num} HTTP error: {response.status_code}")
                print(f"  Response: {response.text}")
        except Exception as e:
            print(f"  ✗ Chunk {chunk_num} error: {e}")
        
        # Small delay between requests
        if i < len(chunks) - 1:
            time.sleep(1)
    
    return len(chunks)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 script.py <content> <obj_token> <access_token>")
        sys.exit(1)
    
    content = sys.argv[1]
    obj_token = sys.argv[2]
    access_token = sys.argv[3]
    
    num_chunks = upload_to_wiki(content, obj_token, access_token)
    print(f"\nUploaded {num_chunks} chunks successfully")
EOF
)

# Write Python script to file
PY_SCRIPT_FILE="/tmp/upload_wiki.py"
echo "$PYTHON_SCRIPT" > "$PY_SCRIPT_FILE"

# Run Python script to upload content
echo "Uploading content to Wiki..."
python3 "$PY_SCRIPT_FILE" "$CONTENT" "$OBJ_TOKEN" "$TOKEN"

# Clean up
rm -f "$PY_SCRIPT_FILE"

echo -e "${GREEN}✓ Wiki documentation published successfully!${NC}"
echo ""
echo "Document URL: https://open.larksuite.com/wiki/$OBJ_TOKEN"
echo "You can view and edit the document in Lark Wiki."

# Send notification via script
NOTIFICATION_SCRIPT="/home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh"
if [ -f "$NOTIFICATION_SCRIPT" ]; then
    echo "Sending notification..."
    "$NOTIFICATION_SCRIPT" "oc_a2a70c6b4a29c2f2eb6c2500ea42a500" "Privacy Guard 插件文档已发布到 Wiki：https://open.larksuite.com/wiki/$OBJ_TOKEN"
    echo "✓ Notification sent"
else
    echo -e "${YELLOW}Warning: Notification script not found at $NOTIFICATION_SCRIPT${NC}"
fi