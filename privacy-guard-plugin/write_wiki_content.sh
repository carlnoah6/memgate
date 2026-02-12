#!/bin/bash

TOKEN="***TOKEN_REMOVED***"
NODE_TOKEN="KkFfwh3tWixqTJkEyCslpdr7gkf"
API_URL="https://open.larksuite.com/open-apis/wiki/v2/spaces/7604126789916479197/nodes/$NODE_TOKEN/blocks"

echo "开始写入 Wiki 内容..."

# 读取 blocks
BLOCKS=$(cat /home/ubuntu/.openclaw/workspace/privacy-guard-plugin/wiki_blocks.json)

# 写入内容
curl -s -X POST "$API_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$BLOCKS"

echo "Wiki 内容写入完成！"
