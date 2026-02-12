#!/bin/bash
# restart-gateway.sh — 统一的 Gateway 重启脚本
# 用法: bash scripts/restart-gateway.sh "重启原因" "source_session"
#
# 自动完成:
# 1. 强制检查（参数、session、子任务）
# 2. 写重启标记 (mark-restart.sh)
# 3. 通过 CLI 创建 cron wake job (--wake now, 15秒后触发)
# 4. 等待 5 秒（让当前流式卡片完成输出）
# 5. 执行 openclaw gateway restart
#
# 这是唯一正确的重启方式。不要手动执行这些步骤。

set -e

REASON="${1:-未指定原因}"
SOURCE_SESSION="${2}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Gateway 重启流程 ==="
echo "原因: $REASON"
echo "来源会话: ${SOURCE_SESSION:-未指定}"
echo ""

# === 强制检查开始 ===
echo "🔍 执行重启前强制检查..."

# 检查1：必须提供原因
if [ -z "$REASON" ]; then
    echo "❌ 错误：必须提供重启原因"
    echo "用法: bash scripts/restart-gateway.sh \"重启原因\" \"source_session\""
    exit 1
fi

# 检查2：必须提供 source_session
if [ -z "$SOURCE_SESSION" ]; then
    echo "❌ 错误：必须提供 source_session"
    echo "用法: bash scripts/restart-gateway.sh \"重启原因\" \"source_session\""
    echo "source_session 格式: feishu:group:oc_xxx 或 main"
    exit 1
fi

# 检查3：验证 source_session 格式
if [[ ! "$SOURCE_SESSION" =~ ^(main|feishu:(group|private):oc_[a-f0-9]+)$ ]]; then
    echo "❌ 错误：source_session 格式不正确"
    echo "正确格式: main 或 feishu:group:oc_xxx 或 feishu:private:oc_xxx"
    exit 1
fi

# 检查4：获取当前 session key 验证（如果可能）
echo "⏳ 获取当前会话状态..."
if command -v openclaw &> /dev/null; then
    CURRENT_SESSION_JSON=$(openclaw session_status --json 2>/dev/null || echo "{}")
    CURRENT_SESSION=$(echo "$CURRENT_SESSION_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('session_id', 'unknown'))
except:
    print('unknown')
")
    
    if [ "$CURRENT_SESSION" != "unknown" ] && [ "$CURRENT_SESSION" != "$SOURCE_SESSION" ]; then
        echo "⚠️  警告：提供的 session_key ($SOURCE_SESSION) 与当前 session ($CURRENT_SESSION) 不匹配"
        echo "是否继续？[y/N]"
        read -r CONFIRM
        if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
            echo "❌ 用户取消重启"
            exit 1
        fi
    fi
fi

# 检查5：检查是否有活跃子任务
echo "⏳ 检查活跃子任务..."
if command -v openclaw &> /dev/null; then
    # 使用 sessions_list 检查活跃子任务
    SESSIONS_JSON=$(openclaw sessions_list --json 2>/dev/null || echo '{"sessions":[]}')
    ACTIVE_SUBAGENTS=$(echo "$SESSIONS_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = 0
    for session in data.get('sessions', []):
        if session.get('kind') == 'subagent' and session.get('activeMinutes', 999) < 5:
            count += 1
            print(f'  - {session.get(\"sessionKey\", \"unknown\")} (活跃 {session.get(\"activeMinutes\", 0)} 分钟)')
    if count > 0:
        print(f'发现 {count} 个活跃子任务')
except:
    pass
")
    
    if [ -n "$ACTIVE_SUBAGENTS" ]; then
        echo "❌ 错误：发现活跃子任务，不能重启："
        echo "$ACTIVE_SUBAGENTS"
        echo ""
        echo "请等待子任务完成，或使用 sessions_send 通知子任务停止。"
        exit 1
    fi
fi

# 检查6：检查 Gateway 是否在运行
echo "⏳ 检查 Gateway 运行状态..."
if ! command -v openclaw &> /dev/null; then
    echo "❌ 错误：openclaw 命令未找到"
    exit 1
fi

GATEWAY_PID=$(pgrep -f "openclaw.*gateway" | head -1)
if [ -z "$GATEWAY_PID" ]; then
    echo "❌ 错误：Gateway 未在运行"
    exit 1
fi
echo "✅ Gateway 正在运行 (PID: $GATEWAY_PID)"

# 检查7：等待用户确认（如果从交互式终端运行）
if [ -t 0 ]; then
    echo ""
    echo "⚠️  即将重启 Gateway，原因: $REASON"
    echo "来源会话: $SOURCE_SESSION"
    echo "当前 PID: $GATEWAY_PID"
    echo ""
    echo "确认重启？[y/N]"
    read -r CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "❌ 用户取消重启"
        exit 1
    fi
fi

echo "✅ 所有强制检查通过"
echo ""

# Step 1: 写重启标记
echo "[1/5] 写重启标记..."
bash "$SCRIPT_DIR/mark-restart.sh" "$REASON" "$SOURCE_SESSION"

# Step 2: 通过 openclaw CLI 创建 cron wake job
echo "[2/5] 创建 wake job (--wake now, 15s)..."
HEARTBEAT_PROMPT="Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."

# 创建一次性 wake job，重启后 15 秒触发心跳
openclaw cron add \
  --name "post-restart-wake" \
  --at "15s" \
  --session main \
  --system-event "$HEARTBEAT_PROMPT" \
  --wake now \
  --delete-after-run \
  --json 2>&1 | grep -v "Config warnings" || true

echo "✅ wake job 创建成功（重启后 15 秒触发心跳）"

# Step 3: 等待当前流式输出完成
echo "[3/5] 等待 5 秒让流式卡片关闭..."
sleep 5

# Step 4: 检查 wake job 是否创建成功
echo "[4/5] 验证 wake job..."
if openclaw cron list --json 2>/dev/null | grep -q "post-restart-wake"; then
    echo "✅ wake job 验证成功"
else
    echo "⚠️  警告：未找到 wake job，但继续执行重启"
fi

# Step 5: 执行重启
echo "[5/5] 执行 openclaw gateway restart..."
openclaw gateway restart 2>&1 || true

echo ""
echo "=== 重启已触发 ==="
echo "重启原因: $REASON"
echo "汇报目标: $SOURCE_SESSION"
echo "当前时间: $(date)"
echo ""
echo "重启后约 15 秒内会自动汇报完成状态。"
