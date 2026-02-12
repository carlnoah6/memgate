#!/bin/bash
# 重启前调用，写入标记文件
# 用法: bash mark-restart.sh "重启原因" "source_session"
# 注意：wake event 必须由主 session 用 cron 工具发，bash 无法访问 gateway 的 WebSocket RPC
# 所以这个脚本只负责写标记，wake event 在调用方处理

REASON="${1:-unknown reason}"
SOURCE_SESSION="${2:-unknown}"

# 使用 Python 生成 JSON，避免 shell 字符串拼接问题
python3 -c "
import json
import sys
data = {
    'reason': sys.argv[1],
    'source_session': sys.argv[2],
    'timestamp': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")'
}
with open('/tmp/luna-pending-restart.marker', 'w') as f:
    json.dump(data, f)
print('Restart marker written (JSON format)')
" "$REASON" "$SOURCE_SESSION"
