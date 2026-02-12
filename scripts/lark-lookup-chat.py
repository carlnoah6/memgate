#!/usr/bin/env python3
"""根据群名查 chat_id，或列出所有群。

用法:
  python3 lark-lookup-chat.py                    # 列出所有群
  python3 lark-lookup-chat.py "Luna任务板"        # 模糊搜索群名
  python3 lark-lookup-chat.py --refresh           # 刷新缓存
"""
import json, os, sys, time, urllib.request

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token, BASE_URL

CACHE_FILE = "/home/ubuntu/.openclaw/workspace/data/lark-chats-cache.json"
CACHE_TTL = 3600  # 1 hour

def fetch_all_chats():
    token = get_tenant_token()
    chats = []
    page_token = ""
    while True:
        url = f"{BASE_URL}/im/v1/chats?page_size=50"
        if page_token:
            url += f"&page_token={page_token}"
        resp = urllib.request.urlopen(urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"}, method="GET"), timeout=10).read()
        data = json.loads(resp)
        items = data.get("data", {}).get("items", [])
        for c in items:
            chats.append({"chat_id": c["chat_id"], "name": c.get("name", "(无名)"),
                          "user_count": c.get("user_count", "?")})
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"].get("page_token", "")
    # Save cache
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"ts": time.time(), "chats": chats}, f, ensure_ascii=False, indent=2)
    return chats

def load_chats(force_refresh=False):
    if not force_refresh and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache.get("ts", 0) < CACHE_TTL:
            return cache["chats"]
    return fetch_all_chats()

def main():
    force = "--refresh" in sys.argv
    query = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            query = arg.lower()

    chats = load_chats(force_refresh=force)

    if query:
        matches = [c for c in chats if query in c["name"].lower()]
        if not matches:
            print(f"未找到包含 '{query}' 的群")
            sys.exit(1)
        for c in matches:
            print(f"{c['chat_id']}  |  {c['name']}")
    else:
        for c in chats:
            print(f"{c['chat_id']}  |  {c['name']}")

if __name__ == "__main__":
    main()
