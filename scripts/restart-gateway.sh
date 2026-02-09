#!/bin/bash
# restart-gateway.sh — 统一的 Gateway 重启脚本
# 用法: bash scripts/restart-gateway.sh "重启原因"
#
# 自动完成:
# 1. 写重启标记 (mark-restart.sh)
# 2. 通过 CLI 创建 cron wake job (--wake now, 15秒后触发)
# 3. 等待 5 秒（让当前流式卡片完成输出）
# 4. 执行 openclaw gateway restart
#
# 这是唯一正确的重启方式。不要手动执行这些步骤。

set -e

REASON="${1:-未指定原因}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Gateway 重启流程 ==="
echo "原因: $REASON"
echo ""

# Step 1: 写重启标记
echo "[1/4] 写重启标记..."
bash "$SCRIPT_DIR/mark-restart.sh" "$REASON"

# Step 2: 通过 openclaw CLI 创建 cron wake job
echo "[2/4] 创建 wake job (--wake now, 15s)..."
HEARTBEAT_PROMPT="Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."

openclaw cron add \
  --name "post-restart-wake" \
  --at "15s" \
  --session main \
  --system-event "$HEARTBEAT_PROMPT" \
  --wake now \
  --delete-after-run \
  --json 2>&1 | grep -v "Config warnings" || true

# Step 3: 等待当前流式输出完成
echo "[3/4] 等待 5 秒让流式卡片关闭..."
sleep 5

# Step 4: 执行重启
echo "[4/4] 执行 openclaw gateway restart..."
openclaw gateway restart 2>&1 || true

echo ""
echo "=== 重启已触发 ==="
