#!/bin/bash
# 重启前调用，写入标记文件
# 用法: bash mark-restart.sh "重启原因"
# 注意：wake event 必须由主 session 用 cron 工具发，bash 无法访问 gateway 的 WebSocket RPC
# 所以这个脚本只负责写标记，wake event 在调用方处理

REASON="${1:-unknown reason}"
echo "$REASON" > /tmp/luna-pending-restart.marker
echo "Restart marker written"
