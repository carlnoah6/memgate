#!/usr/bin/env python3
"""
清理群聊 session 脚本
根据 MEMORY.md 中的指导：
1. 清空 agents/main/sessions/<uuid>.jsonl（transcript）
2. 重置 sessions.json 中对应 session 的 systemSent=false、totalTokens=0
"""

import json
import os
import sys

SESSIONS_DIR = "/home/ubuntu/.openclaw/agents/main/sessions"
SESSIONS_JSON = os.path.join(SESSIONS_DIR, "sessions.json")

# 从 sessions_list 输出中获取的群聊 session 信息
GROUP_SESSIONS = [
    {
        "key": "agent:main:feishu:group:oc_0900e63860f8b6d1b08285262701817f",
        "sessionId": "0bb9e8c1-0227-4f1c-a8ee-16c2b1bbf95c"
    },
    {
        "key": "agent:main:feishu:group:oc_453c88ec52dd029845c46249837e3ba0",
        "sessionId": "7290542d-4e5a-4d00-a3df-a87392a22f1d"
    },
    {
        "key": "agent:main:feishu:group:oc_4fe2e6e2dbfd0e6fc35c9dab672ab820",
        "sessionId": "85eeecaa-77d6-4958-b02f-6b14df4201a2"
    },
    {
        "key": "agent:main:feishu:group:oc_680d9c843e6a0ad501de9299a97f3a7e",
        "sessionId": "860bc801-71b5-4f27-8d32-3d556dcca6eb"
    },
    {
        "key": "agent:main:feishu:group:oc_630995d9b870d2ff6ab3fa34a4e7315a",
        "sessionId": "17084387-b246-4427-a227-a1dcd8f3cdb7"
    },
    {
        "key": "agent:main:feishu:group:oc_7f3ebd31a5cf2fec9170952b29eb2700",
        "sessionId": "0ef748fa-6bc7-4ea8-970d-e5922363e856"
    }
]

def clean_transcript_files():
    """清空 transcript 文件"""
    print("=== 清空 transcript 文件 ===")
    
    for session in GROUP_SESSIONS:
        session_id = session["sessionId"]
        transcript_path = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
        
        if os.path.exists(transcript_path):
            try:
                # 获取文件大小
                original_size = os.path.getsize(transcript_path)
                
                # 清空文件（保留 0 字节）
                open(transcript_path, 'w').close()
                
                print(f"✅ 清空: {session_id}.jsonl (原大小: {original_size:,} bytes)")
            except Exception as e:
                print(f"❌ 清空失败 {session_id}.jsonl: {e}")
        else:
            print(f"⚠️  文件不存在: {session_id}.jsonl")

def reset_sessions_json():
    """重置 sessions.json 中的 session 状态"""
    print("\n=== 重置 sessions.json 状态 ===")
    
    if not os.path.exists(SESSIONS_JSON):
        print(f"❌ sessions.json 不存在: {SESSIONS_JSON}")
        return
    
    try:
        # 备份原文件
        import shutil
        import time
        backup_path = f"{SESSIONS_JSON}.backup.{int(time.time())}"
        shutil.copy2(SESSIONS_JSON, backup_path)
        print(f"✅ 已备份: {backup_path}")
        
        # 读取 sessions.json
        with open(SESSIONS_JSON, 'r') as f:
            sessions_data = json.load(f)
        
        updated = False
        
        # 重置每个群聊 session
        for session in GROUP_SESSIONS:
            session_id = session["sessionId"]
            
            # 在 sessions.json 中查找对应的 session
            for key, session_info in sessions_data.items():
                if isinstance(session_info, dict) and session_info.get("sessionId") == session_id:
                    # 重置状态
                    session_info["systemSent"] = False
                    session_info["totalTokens"] = 0
                    session_info["contextTokens"] = 200000
                    
                    print(f"✅ 重置: {key} (sessionId: {session_id})")
                    updated = True
                    break
        
        if updated:
            # 写回文件
            with open(SESSIONS_JSON, 'w') as f:
                json.dump(sessions_data, f, indent=2)
            print("✅ sessions.json 已更新")
        else:
            print("⚠️  未在 sessions.json 中找到对应的 session 记录")
            
    except Exception as e:
        print(f"❌ 处理 sessions.json 失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("开始清理群聊 session...")
    print(f"找到 {len(GROUP_SESSIONS)} 个群聊 session 需要清理")
    
    clean_transcript_files()
    reset_sessions_json()
    
    print("\n=== 清理完成 ===")
    print("注意：清理后，下次收到群聊消息时会重新初始化 session")
    print("不需要重启 gateway，清理立即生效")

if __name__ == "__main__":
    main()