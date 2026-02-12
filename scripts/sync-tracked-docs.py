#!/usr/bin/env python3
"""
扫描两个 Wiki 知识库的所有文档，自动更新 tracked-docs.json。
用途：
  1. 定期运行（心跳评论检查前调用），确保新文档自动纳入监控
  2. 子任务创建文档后调用，立即注册监控
  3. 手动运行查看当前状态

用法：
  python3 sync-tracked-docs.py          # 扫描并更新
  python3 sync-tracked-docs.py --dry    # 只打印不更新
  python3 sync-tracked-docs.py --add <obj_token> <title> <file_type> <node_token>  # 手动添加单个文档
"""

import json
import os
import sys
import urllib.request

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_user_token, BASE_URL

TRACKED_DOCS_PATH = "/home/ubuntu/.openclaw/workspace/data/tracked-docs.json"
API_BASE = "https://open.larksuite.com"

# 两个知识库
SPACES = [
    {"id": "7604126789916479197", "name": "Luna 协同知识库"},
    {"id": "7604150806383693538", "name": "Carl 私人知识库"},
]

def get_token():
    return get_user_token()

def get_all_nodes(space_id, token, parent=None):
    """递归获取知识库下所有节点"""
    url = f"{API_BASE}/open-apis/wiki/v2/spaces/{space_id}/nodes"
    if parent:
        url += f"?parent_node_token={parent}"
    
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ API 错误: {e}")
        return []
    
    if data.get("code") != 0:
        print(f"  ⚠️ API 返回错误: code={data.get('code')}, msg={data.get('msg')}")
        return []
    
    results = []
    for node in data["data"].get("items", []):
        obj_type = node.get("obj_type", "unknown")
        # 只监控 docx 和 sheet（其他类型如 mindnote 不支持评论 API）
        if obj_type in ("docx", "sheet"):
            results.append({
                "id": node["obj_token"],
                "title": node["title"],
                "file_type": obj_type,
                "node_token": node["node_token"],
                "space_id": space_id,
            })
        # 递归子节点
        children = get_all_nodes(space_id, token, node["node_token"])
        results.extend(children)
    
    return results

def load_tracked():
    if os.path.exists(TRACKED_DOCS_PATH):
        with open(TRACKED_DOCS_PATH) as f:
            return json.load(f)
    return []

def save_tracked(docs):
    with open(TRACKED_DOCS_PATH, "w") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)

def add_single(obj_token, title, file_type, node_token):
    """手动添加单个文档到监控列表"""
    tracked = load_tracked()
    existing_ids = {d["id"] for d in tracked}
    
    if obj_token in existing_ids:
        print(f"已存在: {title} ({obj_token})")
        return
    
    tracked.append({
        "id": obj_token,
        "title": title,
        "file_type": file_type,
        "node_token": node_token,
    })
    save_tracked(tracked)
    print(f"✅ 已添加: {title} ({obj_token})")

def main():
    # 手动添加模式
    if len(sys.argv) >= 6 and sys.argv[1] == "--add":
        add_single(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        return
    
    dry_run = "--dry" in sys.argv
    
    token = get_token()
    tracked = load_tracked()
    existing_ids = {d["id"] for d in tracked}
    
    print(f"当前监控: {len(tracked)} 个文档")
    
    # 扫描所有知识库
    all_docs = []
    for space in SPACES:
        print(f"\n扫描 {space['name']} ({space['id']})...")
        docs = get_all_nodes(space["id"], token)
        print(f"  发现 {len(docs)} 个文档")
        all_docs.extend(docs)
    
    # 找出新文档
    new_docs = [d for d in all_docs if d["id"] not in existing_ids]
    
    if not new_docs:
        print(f"\n✅ 无新文档，当前 {len(tracked)} 个全部在监控中")
        return
    
    print(f"\n发现 {len(new_docs)} 个新文档:")
    for d in new_docs:
        print(f"  + {d['title']} ({d['file_type']}) [{d['id']}]")
    
    if dry_run:
        print("\n(dry run, 未更新文件)")
        return
    
    # 合并并保存
    # 更新已有文档的 space_id（老数据可能没有这个字段）
    for d in tracked:
        if "space_id" not in d:
            # 从扫描结果中查找
            for ad in all_docs:
                if ad["id"] == d["id"]:
                    d["space_id"] = ad["space_id"]
                    break
    
    tracked.extend([{
        "id": d["id"],
        "title": d["title"],
        "file_type": d["file_type"],
        "node_token": d["node_token"],
    } for d in new_docs])
    
    save_tracked(tracked)
    print(f"\n✅ 已更新 tracked-docs.json: {len(tracked)} 个文档（新增 {len(new_docs)} 个）")

if __name__ == "__main__":
    main()
