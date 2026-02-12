#!/bin/bash

# 清理群聊 session 脚本
# 1. 清空 transcript 文件
# 2. 重置 sessions.json 中的 session 状态

SESSIONS_DIR="/home/ubuntu/.openclaw/agents/main/sessions"
SESSIONS_JSON="$SESSIONS_DIR/sessions.json"

echo "=== 开始清理群聊 session ==="

# 备份 sessions.json
if [ -f "$SESSIONS_JSON" ]; then
    cp "$SESSIONS_JSON" "$SESSIONS_JSON.backup.$(date +%s)"
    echo "✅ 已备份 sessions.json"
fi

# 从 sessions_list 获取群聊 session 信息
echo "正在获取群聊 session 列表..."

# 使用 openclaw 命令获取 session 列表
SESSION_INFO=$(openclaw sessions list --json 2>/dev/null || echo "{}")

# 解析 JSON 获取群聊 session
echo "$SESSION_INFO" | python3 -c "
import json, sys, os

try:
    data = json.load(sys.stdin)
    sessions = data.get('sessions', [])
    
    group_sessions = []
    for s in sessions:
        if s.get('kind') == 'group':
            group_sessions.append(s)
    
    print(f'找到 {len(group_sessions)} 个群聊 session:')
    for s in group_sessions:
        session_id = s.get('sessionId', '')
        key = s.get('key', '')
        display_name = s.get('displayName', '')
        total_tokens = s.get('totalTokens', 0)
        print(f'  • {display_name} ({key})')
        print(f'    sessionId: {session_id}, tokens: {total_tokens}')
    
    # 清理 transcript 文件
    print('\\n清理 transcript 文件...')
    for s in group_sessions:
        session_id = s.get('sessionId', '')
        if session_id:
            transcript_path = f'$SESSIONS_DIR/{session_id}.jsonl'
            if os.path.exists(transcript_path):
                # 清空文件（保留 0 字节）
                open(transcript_path, 'w').close()
                print(f'  ✅ 清空: {transcript_path}')
            else:
                print(f'  ⚠️  文件不存在: {transcript_path}')
    
    # 重置 sessions.json
    print('\\n重置 sessions.json 状态...')
    if os.path.exists('$SESSIONS_JSON'):
        with open('$SESSIONS_JSON', 'r') as f:
            sessions_data = json.load(f)
        
        updated = False
        for s in group_sessions:
            session_id = s.get('sessionId', '')
            if session_id in sessions_data:
                # 重置状态
                sessions_data[session_id]['systemSent'] = False
                sessions_data[session_id]['totalTokens'] = 0
                sessions_data[session_id]['contextTokens'] = 200000
                updated = True
                print(f'  ✅ 重置: {session_id}')
        
        if updated:
            with open('$SESSIONS_JSON', 'w') as f:
                json.dump(sessions_data, f, indent=2)
            print('✅ sessions.json 已更新')
        else:
            print('⚠️  未找到对应的 session 记录')
    
except Exception as e:
    print(f'错误: {e}')
    sys.exit(1)
"

echo ""
echo "=== 清理完成 ==="
echo "注意：清理后，下次收到群聊消息时会重新初始化 session"
echo "不需要重启 gateway，清理立即生效"