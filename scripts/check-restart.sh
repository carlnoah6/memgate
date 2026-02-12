#!/bin/bash
# 检查 gateway 是否刚重启
# 两种检测方式：1) 标记文件（手动标记） 2) PID 变化（崩溃/完整重启）

PID_FILE="/home/ubuntu/.openclaw/workspace/data/gateway.pid"
MARKER="/tmp/luna-pending-restart.marker"
CURRENT_PID=$(pgrep -f "openclaw.*gateway" | head -1)

if [ -z "$CURRENT_PID" ]; then
    echo "Gateway not running"
    exit 1
fi

# 优先检查标记文件（覆盖 config.patch 等 SIGUSR1 热重载场景）
if [ -f "$MARKER" ]; then
    # 解析 JSON 格式的标记文件
    MARKER_CONTENT=$(cat "$MARKER")
    REASON="未知原因"
    SOURCE_SESSION="unknown"
    
    # 尝试解析 JSON
    if echo "$MARKER_CONTENT" | python3 -c "import json, sys; json.load(sys.stdin)" 2>/dev/null; then
        REASON=$(echo "$MARKER_CONTENT" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('reason', '未知原因'))")
        SOURCE_SESSION=$(echo "$MARKER_CONTENT" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('source_session', 'unknown'))")
        echo "RESTART_INFO: {\"reason\": \"$REASON\", \"source_session\": \"$SOURCE_SESSION\"}"
    else
        # 旧格式（纯文本）
        REASON="$MARKER_CONTENT"
        echo "重启原因: $REASON"
    fi
    
    rm -f "$MARKER"
    echo "$CURRENT_PID" > "$PID_FILE"
    # 重启后自动启动知识同步 watcher
    bash "$(dirname "$0")/start-knowledge-watcher.sh" 2>/dev/null &
    echo "just_restarted"
    exit 0
fi

# 其次检查 PID 变化（覆盖崩溃/手动重启等场景）
if [ -f "$PID_FILE" ]; then
    LAST_PID=$(cat "$PID_FILE")
    if [ "$CURRENT_PID" != "$LAST_PID" ]; then
        echo "$CURRENT_PID" > "$PID_FILE"
        echo "RESTART_INFO: {\"reason\": \"PID 变化（从 $LAST_PID 变为 $CURRENT_PID）\", \"source_session\": \"unknown\"}"
        # 重启后自动启动知识同步 watcher
        bash "$(dirname "$0")/start-knowledge-watcher.sh" 2>/dev/null &
        echo "just_restarted"
        exit 0
    fi
fi

# 更新 PID 记录
echo "$CURRENT_PID" > "$PID_FILE"
echo "running_normally"
