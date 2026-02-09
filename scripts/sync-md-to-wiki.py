#!/usr/bin/env python3
"""
MD ↔ Wiki 双向同步脚本

规则：MD 是 Luna 写的，Wiki 是 Carl 看的。每个重要 MD 文件对应一个 Wiki 文档。

用法：
  python3 sync-md-to-wiki.py                    # 同步所有有变更的文件
  python3 sync-md-to-wiki.py --register FILE     # 注册新文件（自动创建 Wiki 文档）
  python3 sync-md-to-wiki.py --list              # 列出所有映射
  python3 sync-md-to-wiki.py --force FILE        # 强制同步指定文件
  python3 sync-md-to-wiki.py --force-all         # 强制同步所有文件

映射表：data/wiki-sync.json
"""

import json
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

WORKSPACE = Path(__file__).parent.parent
SYNC_MAP_PATH = WORKSPACE / "data" / "wiki-sync.json"
WIKI_SCRIPT = WORKSPACE / "scripts" / "md-to-lark-wiki.py"

SGT = timezone(timedelta(hours=8))


def load_sync_map() -> dict:
    if SYNC_MAP_PATH.exists():
        with open(SYNC_MAP_PATH) as f:
            return json.load(f)
    return {"files": {}, "defaults": {}}


def save_sync_map(data: dict):
    SYNC_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_MAP_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def file_hash(path: str) -> str:
    """计算文件内容的 hash"""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except FileNotFoundError:
        return ""


def sync_file(md_path: str, entry: dict, force: bool = False) -> bool:
    """同步单个文件到 Wiki，返回是否有变更"""
    full_path = WORKSPACE / md_path
    if not full_path.exists():
        print(f"  ⚠️ 文件不存在: {md_path}")
        return False

    current_hash = file_hash(str(full_path))
    last_hash = entry.get("last_hash", "")

    if current_hash == last_hash and not force:
        return False  # 没有变更

    # 执行同步
    space_id = entry["space_id"]
    parent_token = entry["parent_token"]
    title = entry["title"]
    
    import subprocess
    cmd = [
        "python3", str(WIKI_SCRIPT),
        "--create",
        "--space", space_id,
        "--parent", parent_token,
        "--title", title,
        "--file", str(full_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    
    if "OK:" in output:
        # Extract node_token from URL if present
        for line in output.split("\n"):
            if "URL:" in line:
                url = line.split("URL:")[-1].strip()
                node_token = url.split("/wiki/")[-1] if "/wiki/" in url else ""
                if node_token:
                    entry["node_token"] = node_token
                    entry["url"] = url
            if "Found existing" in line:
                parts = line.split("node=")[-1].split(" obj=")
                if len(parts) == 2:
                    entry["node_token"] = parts[0]
                    entry["obj_token"] = parts[1]
            if "Created wiki" in line:
                parts = line.split("node=")[-1].split(" obj=")
                if len(parts) == 2:
                    entry["node_token"] = parts[0]
                    entry["obj_token"] = parts[1]

        entry["last_hash"] = current_hash
        entry["last_synced"] = datetime.now(SGT).isoformat()
        action = "更新" if last_hash else "创建"
        print(f"  ✅ {action}: {title}")
        if entry.get("url"):
            print(f"     {entry['url']}")
        return True
    else:
        print(f"  ❌ 同步失败: {title}")
        print(f"     {output[:200]}")
        return False


def register_file(md_path: str, title: str, space_id: str, parent_token: str):
    """注册新文件到映射表"""
    sync_map = load_sync_map()
    
    sync_map["files"][md_path] = {
        "title": title,
        "space_id": space_id,
        "parent_token": parent_token,
        "last_hash": "",
        "last_synced": None,
        "node_token": None,
        "obj_token": None,
        "url": None
    }
    
    save_sync_map(sync_map)
    print(f"✅ 已注册: {md_path} → {title}")
    
    # Immediately sync
    entry = sync_map["files"][md_path]
    if sync_file(md_path, entry, force=True):
        save_sync_map(sync_map)


def sync_all(force: bool = False):
    """同步所有有变更的文件"""
    sync_map = load_sync_map()
    files = sync_map.get("files", {})
    
    if not files:
        print("没有注册的文件。用 --register 添加。")
        return
    
    changed = 0
    skipped = 0
    errors = 0
    
    for md_path, entry in files.items():
        result = sync_file(md_path, entry, force=force)
        if result:
            changed += 1
        elif result is False and file_hash(str(WORKSPACE / md_path)) == entry.get("last_hash", ""):
            skipped += 1
        else:
            errors += 1
    
    save_sync_map(sync_map)
    
    total = len(files)
    print(f"\n同步完成: {changed} 更新, {skipped} 无变更, {errors} 错误 / 共 {total} 个文件")


def list_files():
    """列出所有映射"""
    sync_map = load_sync_map()
    files = sync_map.get("files", {})
    
    if not files:
        print("没有注册的文件。")
        return
    
    print(f"{'MD 文件':<45} {'Wiki 标题':<35} {'状态'}")
    print("-" * 100)
    for md_path, entry in files.items():
        full_path = WORKSPACE / md_path
        exists = full_path.exists()
        current_hash = file_hash(str(full_path)) if exists else ""
        last_hash = entry.get("last_hash", "")
        
        if not exists:
            status = "⚠️ 文件不存在"
        elif current_hash != last_hash:
            status = "🔄 待同步"
        else:
            status = "✅ 已同步"
        
        title = entry.get("title", "?")
        print(f"{md_path:<45} {title:<35} {status}")


def main():
    args = sys.argv[1:]
    
    if not args or args == ["--sync"]:
        print("=== MD → Wiki 同步 ===\n")
        sync_all()
    
    elif args[0] == "--list":
        list_files()
    
    elif args[0] == "--force-all":
        print("=== MD → Wiki 强制同步 ===\n")
        sync_all(force=True)
    
    elif args[0] == "--force" and len(args) > 1:
        md_path = args[1]
        sync_map = load_sync_map()
        if md_path in sync_map.get("files", {}):
            sync_file(md_path, sync_map["files"][md_path], force=True)
            save_sync_map(sync_map)
        else:
            print(f"文件未注册: {md_path}")
    
    elif args[0] == "--register" and len(args) >= 5:
        # --register FILE TITLE SPACE_ID PARENT_TOKEN
        register_file(args[1], args[2], args[3], args[4])
    
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
