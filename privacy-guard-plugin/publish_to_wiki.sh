#!/bin/bash
# Publish Privacy Guard documentation to Lark Wiki

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

echo "Create response: $CREATE_RESPONSE"

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
    
    echo "List response: $LIST_RESPONSE"
    
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
fi

echo "✓ Document token: $OBJ_TOKEN"
echo "✓ Node token: $NODE_TOKEN"

# Read wiki content
WIKI_CONTENT_FILE="WIKI_CONTENT.md"
if [ ! -f "$WIKI_CONTENT_FILE" ]; then
    echo -e "${RED}Error: Wiki content file not found: $WIKI_CONTENT_FILE${NC}"
    exit 1
fi

CONTENT=$(cat "$WIKI_CONTENT_FILE")
echo "✓ Read wiki content (${#CONTENT} characters)"

# Split content into chunks (max 4500 characters per request)
split_content() {
    local content="$1"
    local max_chars=4500
    local chunks=()
    local current_chunk=""
    
    # Split by sections (## headers)
    IFS=$'\n'
    local lines=($content)
    unset IFS
    
    for line in "${lines[@]}"; do
        # Check if adding this line would exceed max chars
        if [ $((${#current_chunk} + ${#line} + 1)) -gt $max_chars ]; then
            if [ -n "$current_chunk" ]; then
                chunks+=("$current_chunk")
                current_chunk=""
            fi
        fi
        
        # Add line to current chunk
        if [ -n "$current_chunk" ]; then
            current_chunk="$current_chunk\n$line"
        else
            current_chunk="$line"
        fi
    done
    
    # Add the last chunk
    if [ -n "$current_chunk" ]; then
        chunks+=("$current_chunk")
    fi
    
    echo "${chunks[@]}"
}

# Split content into chunks
echo "Splitting content into chunks..."
CHUNKS=($(split_content "$CONTENT"))
echo "✓ Split into ${#CHUNKS[@]} chunks"

# Upload chunks to document
for i in "${!CHUNKS[@]}"; do
    CHUNK="${CHUNKS[$i]}"
    CHUNK_NUM=$((i + 1))
    
    echo "Uploading chunk $CHUNK_NUM/${#CHUNKS[@]} (${#CHUNK} chars)..."
    
    # Escape JSON special characters
    ESCAPED_CHUNK=$(echo "$CHUNK" | python3 -c "
import json, sys
content = sys.stdin.read()
print(json.dumps(content, ensure_ascii=False))
")
    
    # Remove surrounding quotes
    ESCAPED_CHUNK="${ESCAPED_CHUNK:1:-1}"
    
    # Create JSON payload
    JSON_PAYLOAD="{\"children\":[{\"block_type\":14,\"code\":{\"style\":{\"language\":1},\"elements\":[{\"text_run\":{\"content\":$ESCAPED_CHUNK}}]}}],\"index\":$i}"
    
    # Upload chunk
    UPLOAD_RESPONSE=$(curl -s -X POST \
      "https://open.larksuite.com/open-apis/docx/v1/documents/$OBJ_TOKEN/blocks/$OBJ_TOKEN/children" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$JSON_PAYLOAD")
    
    if echo "$UPLOAD_RESPONSE" | grep -q "success\|code.*0"; then
        echo "  ✓ Chunk $CHUNK_NUM uploaded successfully"
    else
        echo -e "${YELLOW}  ⚠️  Chunk $CHUNK_NUM upload response: $UPLOAD_RESPONSE${NC}"
    fi
    
    # Small delay between requests
    sleep 1
done

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