#!/bin/bash
# Gateway Watchdog - Independent Process Monitor
# 独立运行，不依赖 Gateway，每 60 秒检查一次 Gateway 进程

set -e

# Configuration
WORKSPACE_DIR="/home/ubuntu/.openclaw/workspace"
LOG_FILE="$WORKSPACE_DIR/data/gateway-watchdog.log"
PID_FILE="$WORKSPACE_DIR/data/gateway-watchdog.pid"
GATEWAY_PID_FILE="$WORKSPACE_DIR/data/gateway.pid"
CHECK_INTERVAL=60  # seconds

cd "$WORKSPACE_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if Gateway process is running
check_gateway() {
    # First check PID file
    if [ -f "$GATEWAY_PID_FILE" ]; then
        local pid=$(cat "$GATEWAY_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            # Process exists, verify it's openclaw-gateway
            if ps -p "$pid" -o comm= | grep -q "openclaw"; then
                return 0  # Running
            fi
        fi
    fi
    
    # Fallback: check by pgrep
    if pgrep -f "openclaw-gateway" > /dev/null 2>&1; then
        # Update PID file with actual PID
        pgrep -f "openclaw-gateway" | head -1 > "$GATEWAY_PID_FILE"
        return 0  # Running
    fi
    
    return 1  # Not running
}

# Start Gateway
start_gateway() {
    log "⚠️ Gateway process not found, attempting to restart..."
    
    # Clean up old PID file
    rm -f "$GATEWAY_PID_FILE"
    
    # Start Gateway using openclaw CLI
    if openclaw gateway start >> "$LOG_FILE" 2>&1; then
        sleep 2
        # Verify it started
        if check_gateway; then
            local new_pid=$(cat "$GATEWAY_PID_FILE" 2>/dev/null || pgrep -f "openclaw-gateway" | head -1)
            log "✅ Gateway restarted successfully (PID: $new_pid)"
            return 0
        else
            log "❌ Gateway failed to start (process not found after start command)"
            return 1
        fi
    else
        log "❌ Failed to execute 'openclaw gateway start'"
        return 1
    fi
}

# Main watchdog loop
watchdog_loop() {
    log "🔍 Gateway Watchdog started (checking every ${CHECK_INTERVAL}s)"
    
    local consecutive_failures=0
    local max_failures=3
    
    while true; do
        if ! check_gateway; then
            consecutive_failures=$((consecutive_failures + 1))
            log "⚠️ Gateway check failed ($consecutive_failures/$max_failures)"
            
            if [ $consecutive_failures -ge $max_failures ]; then
                log "🚨 Gateway confirmed down after $max_failures consecutive failures"
                if start_gateway; then
                    consecutive_failures=0
                else
                    log "❌ Failed to restart Gateway, will retry in ${CHECK_INTERVAL}s"
                fi
            fi
        else
            if [ $consecutive_failures -gt 0 ]; then
                log "✅ Gateway is running (recovered)"
                consecutive_failures=0
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Stop function
stop_watchdog() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid" 2>/dev/null || true
            log "🛑 Gateway Watchdog stopped (PID: $pid)"
        fi
        rm -f "$PID_FILE"
    fi
}

# Status function
status_watchdog() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Gateway Watchdog: running (PID: $pid)"
        else
            echo "Gateway Watchdog: stopped (stale PID file)"
        fi
    else
        echo "Gateway Watchdog: stopped"
    fi
    
    # Also show Gateway status
    if check_gateway; then
        local gateway_pid=$(cat "$GATEWAY_PID_FILE" 2>/dev/null || pgrep -f "openclaw-gateway" | head -1)
        echo "Gateway: running (PID: $gateway_pid)"
    else
        echo "Gateway: not running"
    fi
}

# Main entry point
case "${1:-}" in
    start)
        # Check if already running
        if [ -f "$PID_FILE" ]; then
            old_pid=$(cat "$PID_FILE")
            if ps -p "$old_pid" > /dev/null 2>&1; then
                echo "Gateway Watchdog is already running (PID: $old_pid)"
                exit 0
            fi
        fi
        
        # Start in background
        nohup bash "$0" run >> "$LOG_FILE" 2>&1 &
        new_pid=$!
        echo $new_pid > "$PID_FILE"
        echo "Gateway Watchdog started (PID: $new_pid)"
        log "🚀 Gateway Watchdog started (PID: $new_pid)"
        ;;
    
    run)
        # Internal: run the actual watchdog loop
        watchdog_loop
        ;;
    
    stop)
        stop_watchdog
        ;;
    
    status)
        status_watchdog
        ;;
    
    check)
        # One-time check (for use by other scripts)
        if check_gateway; then
            exit 0
        else
            exit 1
        fi
        ;;
    
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status|restart|check}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the watchdog daemon"
        echo "  stop    - Stop the watchdog daemon"
        echo "  status  - Show status of watchdog and Gateway"
        echo "  restart - Restart the watchdog daemon"
        echo "  check   - One-time check of Gateway process (exit 0 if running)"
        exit 1
        ;;
esac
