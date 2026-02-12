#!/bin/bash
# 启动知识同步文件监听守护进程
# Usage: ./start-knowledge-watcher.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
PID_FILE="$WORKSPACE/data/knowledge-watcher.pid"
LOG_FILE="$WORKSPACE/data/knowledge-watcher.log"
SYNC_SCRIPT="$SCRIPT_DIR/knowledge-sync.py"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "⚠️  Knowledge watcher already running (PID: $PID)"
        exit 0
    else
        echo "🧹 Cleaning stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Check inotifywait
if ! command -v inotifywait &>/dev/null; then
    echo "❌ inotifywait not found. Installing inotify-tools..."
    sudo apt install -y inotify-tools
    if ! command -v inotifywait &>/dev/null; then
        echo "❌ Failed to install inotify-tools"
        exit 1
    fi
fi

# Initialize state if needed
if [ ! -f "$WORKSPACE/data/knowledge-sync-state.json" ]; then
    echo "📋 Initializing knowledge sync state..."
    python3 "$SYNC_SCRIPT" init
fi

# Start watcher in background
echo "🚀 Starting knowledge sync watcher..."
nohup python3 "$SYNC_SCRIPT" watch >> "$LOG_FILE" 2>&1 &

# Wait a moment to check it started OK
sleep 1

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ Knowledge watcher started (PID: $PID)"
        echo "📝 Log file: $LOG_FILE"
        exit 0
    fi
fi

echo "❌ Knowledge watcher failed to start. Check log: $LOG_FILE"
exit 1
