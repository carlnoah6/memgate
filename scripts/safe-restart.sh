#!/bin/bash
# Luna 统一重启入口
# 用法:
#   bash safe-restart.sh "原因"                    → gateway restart（完整重启）
#   bash safe-restart.sh "原因" --patch '{"..."}' → config.patch（热重载）
#
# 自动完成：写标记 + 重启/patch + 发 wake event

REASON="${1:-manual restart}"
WORKSPACE="/home/ubuntu/.openclaw/workspace"

# 1. 写重启标记
bash "$WORKSPACE/scripts/mark-restart.sh" "$REASON"

# 2. 判断重启方式
if [ "$2" = "--patch" ]; then
    # config.patch 模式：不需要 wake event（GatewayRestart 消息会自动触发）
    echo "Mode: config.patch (hot reload)"
    # patch 由调用者（LLM）通过 gateway tool 执行
    # 这里只负责标记
else
    # gateway restart 模式：需要后台 wake event
    echo "Mode: gateway restart (full restart)"
    nohup bash -c "sleep 8; openclaw system event --text 'Gateway restarted: $REASON' --mode now --timeout 10000 2>/dev/null" &>/tmp/restart-wake.log &
    openclaw gateway restart
fi

echo "Done. Restart marker written."
