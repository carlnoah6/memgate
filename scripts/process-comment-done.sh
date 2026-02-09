#!/usr/bin/env bash
# process-comment-done.sh — 处理"完成"评论的完整流程
# 用法: process-comment-done.sh <doc_id> "<quote_text>"
#
# 流程: 获取 block → 匹配 quote → 删除 block → 验证删除
# 返回: 0=成功, 1=参数错误, 2=匹配失败, 3=删除失败, 4=验证失败
#
# 示例:
#   ./scripts/process-comment-done.sh BL18d8ZZXo5pIpxVh3al1LXagqc "☐ Wiki 节点删除"

set -euo pipefail

WORKSPACE="/home/ubuntu/.openclaw/workspace"
API="https://open.larksuite.com/open-apis"

# ─── 参数检查 ───
if [[ $# -lt 2 ]]; then
  echo "ERROR: 用法: $0 <doc_id> <quote_text>"
  echo "  doc_id:     Lark 文档 ID"
  echo "  quote_text: 评论引用的原文（用于匹配 block）"
  exit 1
fi

DOC_ID="$1"
QUOTE="$2"

# ─── 获取 token ───
TOKEN=$(python3 -c "import json; print(json.load(open('${WORKSPACE}/data/lark-user-token.json'))['access_token'])")
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: 无法读取 user_access_token"
  exit 1
fi

# ─── Step 1: 获取所有子 block ───
echo "STEP1: 获取文档 ${DOC_ID} 的所有 block..."
BLOCKS_JSON=$(curl -s "${API}/docx/v1/documents/${DOC_ID}/blocks/${DOC_ID}/children?page_size=100" \
  -H "Authorization: Bearer ${TOKEN}")

# 检查 API 是否成功
API_CODE=$(echo "$BLOCKS_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('code',999))" 2>/dev/null || echo "999")
if [[ "$API_CODE" != "0" ]]; then
  echo "ERROR: 获取 block 失败, API code=${API_CODE}"
  echo "$BLOCKS_JSON" | python3 -m json.tool 2>/dev/null || echo "$BLOCKS_JSON"
  exit 3
fi

# ─── Step 2: 匹配 quote 到 block index ───
echo "STEP2: 匹配 quote 到 block..."
MATCH_RESULT=$(echo "$BLOCKS_JSON" | python3 -c "
import json, sys

data = json.load(sys.stdin)
items = data.get('data', {}).get('items', [])
quote = '''${QUOTE}'''

# 提取前20个字符用于模糊匹配（评论 quote 可能被截断）
quote_prefix = quote[:20].strip()

matches = []
for i, item in enumerate(items):
    text = ''
    if 'text' in item:
        for el in item['text'].get('elements', []):
            if 'text_run' in el:
                text += el['text_run'].get('content', '')
    elif 'heading' in item:
        for el in item['heading'].get('elements', []):
            if 'text_run' in el:
                text += el['text_run'].get('content', '')

    # 精确匹配或前缀匹配
    if text.strip() == quote.strip() or (quote_prefix and quote_prefix in text):
        matches.append({'index': i, 'block_id': item['block_id'], 'text': text.strip()})

if not matches:
    print('NO_MATCH')
elif len(matches) == 1:
    m = matches[0]
    print(f'MATCH:{m[\"index\"]}:{m[\"block_id\"]}:{m[\"text\"][:80]}')
else:
    # 多个匹配，优先精确匹配
    exact = [m for m in matches if m['text'] == quote.strip()]
    if len(exact) == 1:
        m = exact[0]
        print(f'MATCH:{m[\"index\"]}:{m[\"block_id\"]}:{m[\"text\"][:80]}')
    else:
        # 取第一个
        m = matches[0]
        print(f'MULTI_MATCH:{len(matches)}:using_first:{m[\"index\"]}:{m[\"block_id\"]}:{m[\"text\"][:80]}')
" 2>/dev/null)

if [[ "$MATCH_RESULT" == "NO_MATCH" ]]; then
  echo "ERROR: 未找到匹配的 block"
  echo "  搜索内容: ${QUOTE}"
  echo "  文档中的所有 block:"
  echo "$BLOCKS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for i, item in enumerate(data.get('data',{}).get('items',[])):
    text = ''
    if 'text' in item:
        for el in item['text'].get('elements',[]):
            if 'text_run' in el: text += el['text_run'].get('content','')
    print(f'  [{i}] {text[:100]}')
" 2>/dev/null
  exit 2
fi

# 解析匹配结果
if [[ "$MATCH_RESULT" == MULTI_MATCH:* ]]; then
  echo "WARNING: 找到多个匹配，使用第一个"
fi

# 提取 index（MATCH:index:block_id:text 或 MULTI_MATCH:count:using_first:index:block_id:text）
if [[ "$MATCH_RESULT" == MATCH:* ]]; then
  BLOCK_INDEX=$(echo "$MATCH_RESULT" | cut -d: -f2)
  BLOCK_ID=$(echo "$MATCH_RESULT" | cut -d: -f3)
  BLOCK_TEXT=$(echo "$MATCH_RESULT" | cut -d: -f4-)
elif [[ "$MATCH_RESULT" == MULTI_MATCH:* ]]; then
  BLOCK_INDEX=$(echo "$MATCH_RESULT" | cut -d: -f4)
  BLOCK_ID=$(echo "$MATCH_RESULT" | cut -d: -f5)
  BLOCK_TEXT=$(echo "$MATCH_RESULT" | cut -d: -f6-)
fi

echo "  找到 block: index=${BLOCK_INDEX}, id=${BLOCK_ID}"
echo "  内容: ${BLOCK_TEXT}"

# ─── Step 3: 删除 block ───
echo "STEP3: 删除 block (index=${BLOCK_INDEX})..."
END_INDEX=$((BLOCK_INDEX + 1))
DELETE_RESULT=$(curl -s -X DELETE \
  "${API}/docx/v1/documents/${DOC_ID}/blocks/${DOC_ID}/children/batch_delete" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"start_index\": ${BLOCK_INDEX}, \"end_index\": ${END_INDEX}}")

DELETE_CODE=$(echo "$DELETE_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('code',999))" 2>/dev/null || echo "999")
if [[ "$DELETE_CODE" != "0" ]]; then
  echo "ERROR: 删除失败, API code=${DELETE_CODE}"
  echo "$DELETE_RESULT" | python3 -m json.tool 2>/dev/null || echo "$DELETE_RESULT"
  exit 3
fi

REV=$(echo "$DELETE_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('document_revision_id','?'))" 2>/dev/null)
echo "  删除成功, revision=${REV}"

# ─── Step 4: 验证删除 ───
echo "STEP4: 验证 block 已被删除..."
sleep 0.5

VERIFY_JSON=$(curl -s "${API}/docx/v1/documents/${DOC_ID}/blocks/${DOC_ID}/children?page_size=100" \
  -H "Authorization: Bearer ${TOKEN}")

VERIFY_RESULT=$(echo "$VERIFY_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
items = data.get('data', {}).get('items', [])
target_id = '${BLOCK_ID}'
found = any(item['block_id'] == target_id for item in items)
if found:
    print('STILL_EXISTS')
else:
    print(f'VERIFIED:total_blocks={len(items)}')
" 2>/dev/null)

if [[ "$VERIFY_RESULT" == "STILL_EXISTS" ]]; then
  echo "ERROR: 验证失败！block ${BLOCK_ID} 仍然存在于文档中"
  exit 4
fi

echo "  验证通过: ${VERIFY_RESULT}"
echo ""
echo "SUCCESS: block 已从文档中删除"
echo "  doc_id: ${DOC_ID}"
echo "  deleted_block: ${BLOCK_ID}"
echo "  deleted_text: ${BLOCK_TEXT}"
