#!/bin/bash
# 停止知识同步文件监听守护进程
# Usage: ./stop-knowledge-watcher.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
PID_FILE="$WORKSPACE/data/knowledge-watcher.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "ℹ️  Knowledge watcher is not running (no PID file)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "🧹 Watcher not running, cleaning stale PID file"
    rm -f "$PID_FILE"
    exit 0
fi

echo "🛑 Stopping knowledge watcher (PID: $PID)..."
kill "$PID"

# Wait up to 5 seconds for graceful shutdown
for i in {1..10}; do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "✅ Knowledge watcher stopped"
        rm -f "$PID_FILE" 2>/dev/null
        exit 0
    fi
    sleep 0.5
done

# Force kill
echo "⚠️  Force killing watcher..."
kill -9 "$PID" 2>/dev/null
rm -f "$PID_FILE" 2>/dev/null
echo "✅ Knowledge watcher force-stopped"
exit 0
