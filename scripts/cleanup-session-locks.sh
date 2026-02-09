#!/bin/bash
# 清理 OpenClaw session 锁文件
# 放到系统 crontab 每 5 分钟运行一次

LOCK_DIR="/home/ubuntu/.openclaw/agents/main/sessions"

# 删除超过 5 分钟的锁文件
find "$LOCK_DIR" -name "*.lock" -mmin +5 -type f -delete 2>/dev/null

# 检查是否有对应进程不存在的锁文件
for lock in "$LOCK_DIR"/*.lock; do
    [ -f "$lock" ] || continue
    # 提取 PID (JSON 格式: {"pid": 12345, ...})
    pid=$(cat "$lock" 2>/dev/null | grep -o '"pid":[0-9]*' | cut -d: -f2)
    if [ -n "$pid" ] && ! ps -p "$pid" > /dev/null 2>&1; then
        # 进程不存在，删除锁
        rm -f "$lock"
    fi
done

echo "Lock cleanup done at $(date)"
