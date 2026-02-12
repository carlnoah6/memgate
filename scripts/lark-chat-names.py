#!/usr/bin/env python3
"""查询 Lark 群聊名称。

用法:
    python3 scripts/lark-chat-names.py                  # 列出所有活跃 session 的群名
    python3 scripts/lark-chat-names.py oc_xxx            # 查单个群名
    python3 scripts/lark-chat-names.py --refresh         # 刷新缓存
    python3 scripts/lark-chat-names.py --resolve "Luna机器人主对话"  # 通过群名反查 chat_id
"""

import json, os, sys, urllib.request, time

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token, BASE_URL

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
CACHE_FILE = os.path.join(WORKSPACE, 'data/chat-names.json')
SESSIONS_FILE = os.path.expanduser('~/.openclaw/agents/main/sessions/sessions.json')
CACHE_TTL = 3600  # 1 hour

def get_chat_name(token, chat_id):
    try:
        req = urllib.request.Request(
            f'{BASE_URL}/im/v1/chats/{chat_id}',
            headers={'Authorization': f'Bearer {token}'})
        r = json.loads(urllib.request.urlopen(req, timeout=5).read())
        return r.get('data', {}).get('name', '(unknown)')
    except Exception as e:
        return f'(error: {e})'

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {'chats': {}, 'updated_at': 0}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    cache['updated_at'] = int(time.time())
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def get_session_chat_ids():
    """从 sessions.json 提取所有群聊 chat_id"""
    if not os.path.exists(SESSIONS_FILE):
        return []
    with open(SESSIONS_FILE) as f:
        sessions = json.load(f)
    chat_ids = []
    for key, val in sessions.items():
        if 'feishu:group:oc_' in key:
            cid = key.split(':')[-1]
            tokens = val.get('totalTokens', 0) or 0
            chat_ids.append((cid, tokens))
    return sorted(chat_ids, key=lambda x: x[1], reverse=True)

def refresh_all():
    token = get_tenant_token()
    cache = load_cache()
    chat_ids = get_session_chat_ids()
    
    for cid, tokens in chat_ids:
        name = get_chat_name(token, cid)
        cache['chats'][cid] = {
            'name': name,
            'tokens': tokens,
            'checked_at': int(time.time())
        }
    save_cache(cache)
    return cache

def resolve_name(name_query):
    """通过群名反查 chat_id"""
    cache = load_cache()
    results = []
    q = name_query.lower()
    for cid, info in cache['chats'].items():
        if q in info.get('name', '').lower():
            results.append((cid, info['name'], info.get('tokens', 0)))
    return results

def main():
    args = sys.argv[1:]
    
    if '--resolve' in args:
        idx = args.index('--resolve')
        if idx + 1 < len(args):
            query = args[idx + 1]
            results = resolve_name(query)
            if results:
                for cid, name, tokens in results:
                    print(json.dumps({'chat_id': cid, 'name': name, 'tokens': tokens}, ensure_ascii=False))
            else:
                # Cache might be stale, refresh and retry
                refresh_all()
                results = resolve_name(query)
                for cid, name, tokens in results:
                    print(json.dumps({'chat_id': cid, 'name': name, 'tokens': tokens}, ensure_ascii=False))
                if not results:
                    print(json.dumps({'error': f'No chat found matching "{query}"'}, ensure_ascii=False))
        return
    
    if '--refresh' in args or not os.path.exists(CACHE_FILE):
        cache = refresh_all()
    else:
        cache = load_cache()
        # Auto-refresh if stale
        if time.time() - cache.get('updated_at', 0) > CACHE_TTL:
            cache = refresh_all()
    
    if args and args[0].startswith('oc_'):
        # Single chat lookup
        chat_id = args[0]
        if chat_id in cache['chats']:
            info = cache['chats'][chat_id]
            print(json.dumps({'chat_id': chat_id, 'name': info['name'], 'tokens': info.get('tokens', 0)}, ensure_ascii=False))
        else:
            token = get_tenant_token()
            name = get_chat_name(token, chat_id)
            print(json.dumps({'chat_id': chat_id, 'name': name}, ensure_ascii=False))
    else:
        # List all
        for cid, info in sorted(cache['chats'].items(), key=lambda x: x[1].get('tokens', 0), reverse=True):
            tokens = info.get('tokens', 0)
            pct = round(tokens / 2000, 1)
            print(f'{tokens:>7} ({pct:>5}%) | {info["name"]} | {cid}')

if __name__ == '__main__':
    main()
