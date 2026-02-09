#!/bin/bash
# deliver-daily-report.sh — 日报统一交付脚本
# 读取 markdown 日报文件，自动转换格式并发送到 4 个渠道
#
# 用法: bash scripts/deliver-daily-report.sh <date> [options]
#   date: YYYY-MM-DD 格式
#   --chat-id <id>     Lark 聊天目标（默认: Carl 私聊）
#   --space <id>       Wiki Space ID（默认: Luna 协同知识库）
#   --parent <token>   Wiki 父节点（默认: 📋 日报）
#   --email <addr>     邮件收件人（默认: adam429.lee@gmail.com）
#   --skip-chat        跳过 Lark 聊天
#   --skip-wiki        跳过 Wiki
#   --skip-email       跳过邮件
#
# 日报文件必须已存在: memory/daily-reports/YYYY-MM-DD.md

set -e

DATE="$1"
if [ -z "$DATE" ]; then
    echo "Usage: $0 <YYYY-MM-DD> [options]"
    exit 1
fi
shift

WORKSPACE="/home/ubuntu/.openclaw/workspace"
REPORT_FILE="$WORKSPACE/memory/daily-reports/${DATE}.md"
SCRIPTS="$WORKSPACE/scripts"

# Defaults
CHAT_ID="oc_453c88ec52dd029845c46249837e3ba0"
SPACE_ID="7604126789916479197"
PARENT_TOKEN="EUeRwKmjJiRlDHkRUTelNFVHgRb"
EMAIL="adam429.lee@gmail.com"
SKIP_CHAT=false
SKIP_WIKI=false
SKIP_EMAIL=false

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --chat-id) CHAT_ID="$2"; shift 2;;
        --space) SPACE_ID="$2"; shift 2;;
        --parent) PARENT_TOKEN="$2"; shift 2;;
        --email) EMAIL="$2"; shift 2;;
        --skip-chat) SKIP_CHAT=true; shift;;
        --skip-wiki) SKIP_WIKI=true; shift;;
        --skip-email) SKIP_EMAIL=true; shift;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

# Check report exists
if [ ! -f "$REPORT_FILE" ]; then
    echo "ERROR: Report file not found: $REPORT_FILE"
    exit 1
fi

# Get day of week
DOW=$(python3 -c "
import datetime
d = datetime.date.fromisoformat('$DATE')
names = ['周一','周二','周三','周四','周五','周六','周日']
print(names[d.weekday()])
")

echo "=== 日报交付: $DATE ($DOW) ==="
echo ""

RESULTS=""

# ── 渠道 1: 本地文件 ──
echo "[1/4] 本地文件: $REPORT_FILE ✅ (已存在)"
RESULTS="$RESULTS\n本地文件: ✅"

# ── 渠道 2: Lark 聊天 (post 富文本) ──
if [ "$SKIP_CHAT" = true ]; then
    echo "[2/4] Lark 聊天: 跳过"
    RESULTS="$RESULTS\nLark 聊天: ⏭️ 跳过"
else
    echo "[2/4] Lark 聊天: 发送 post 富文本..."
    if cat "$REPORT_FILE" | "$SCRIPTS/lark-send-message.sh" "$CHAT_ID" --post 2>&1; then
        RESULTS="$RESULTS\nLark 聊天: ✅"
    else
        echo "  ⚠️ Lark 聊天发送失败"
        RESULTS="$RESULTS\nLark 聊天: ❌"
    fi
fi

# ── 渠道 3: Wiki (DocX blocks) ──
if [ "$SKIP_WIKI" = true ]; then
    echo "[3/4] Wiki: 跳过"
    RESULTS="$RESULTS\nWiki: ⏭️ 跳过"
else
    echo "[3/4] Wiki: 创建/更新文档..."
    WIKI_OUTPUT=$(python3 "$SCRIPTS/md-to-lark-wiki.py" \
        --create --space "$SPACE_ID" --parent "$PARENT_TOKEN" \
        --title "${DATE} 日报" \
        --file "$REPORT_FILE" 2>&1)
    if echo "$WIKI_OUTPUT" | grep -q "^OK:"; then
        WIKI_URL=$(echo "$WIKI_OUTPUT" | grep "^URL:" | cut -d' ' -f2)
        echo "  ✅ $WIKI_URL"
        RESULTS="$RESULTS\nWiki: ✅ $WIKI_URL"
    else
        echo "  ⚠️ Wiki 更新失败: $WIKI_OUTPUT"
        RESULTS="$RESULTS\nWiki: ❌"
    fi
fi

# ── 渠道 4: 邮件 ──
if [ "$SKIP_EMAIL" = true ]; then
    echo "[4/4] 邮件: 跳过"
    RESULTS="$RESULTS\n邮件: ⏭️ 跳过"
else
    echo "[4/4] 邮件: 发送纯文本..."
    EMAIL_TEXT=$(python3 "$SCRIPTS/md-to-email-text.py" --file "$REPORT_FILE")
    SUBJECT="🌙 Luna 日报 - ${DATE}（${DOW}）"
    
    # Send via himalaya with raw MIME
    if echo "$EMAIL_TEXT" | (
        cat << MIMEEOF
From: Luna <luna@openclaw.local>
To: $EMAIL
Subject: $SUBJECT
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit

MIMEEOF
        cat
    ) | EDITOR=cat himalaya message send --account gmail 2>&1; then
        RESULTS="$RESULTS\n邮件: ✅"
    else
        echo "  ⚠️ 邮件发送失败"
        RESULTS="$RESULTS\n邮件: ❌"
    fi
fi

echo ""
echo "=== 交付结果 ==="
echo -e "$RESULTS"
