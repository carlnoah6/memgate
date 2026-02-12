#!/usr/bin/env python3
"""
auto-wiki-sync.py — 自动同步本地文档到 Lark Wiki

用法:
    auto-wiki-sync.py sync                          # 同步所有有变更且 auto_sync=true 的文件
    auto-wiki-sync.py check                         # 检查哪些文件有变更（不执行同步）
    auto-wiki-sync.py register <file> --project <project> --title <title> [--node-token ...] [--obj-token ...] [--no-sync]
    auto-wiki-sync.py list                          # 列出所有注册的文件映射
"""

import json, hashlib, sys, os, time, argparse, subprocess
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
WORKSPACE = "/home/ubuntu/.openclaw/workspace"
SYNC_FILE = os.path.join(WORKSPACE, "data/wiki-sync.json")
TOKEN_FILE = os.path.join(WORKSPACE, "data/lark-user-token.json")
MD_TO_WIKI = os.path.join(WORKSPACE, "scripts/md-to-lark-wiki.py")


def load_sync():
    with open(SYNC_FILE) as f:
        return json.load(f)


def save_sync(data):
    with open(SYNC_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_token():
    """Try to refresh token if needed. Returns True if token is (likely) valid."""
    refresh_script = os.path.join(WORKSPACE, "scripts/lark-token-refresh.py")
    if os.path.exists(refresh_script):
        result = subprocess.run(
            [sys.executable, refresh_script, "--check"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"⚠️  Token refresh failed: {result.stdout.strip()} {result.stderr.strip()}", file=sys.stderr)
            return False
    return True


def file_hash(filepath):
    """Compute MD5 hash of a file."""
    abs_path = os.path.join(WORKSPACE, filepath) if not os.path.isabs(filepath) else filepath
    if not os.path.exists(abs_path):
        return None
    with open(abs_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def get_changed_files(sync_data):
    """Return list of (file_key, entry) where file has changed and auto_sync=true."""
    changed = []
    for fkey, entry in sync_data.get("files", {}).items():
        if not entry.get("auto_sync", False):
            continue
        current_hash = file_hash(fkey)
        if current_hash is None:
            continue
        if current_hash != entry.get("last_hash", ""):
            changed.append((fkey, entry, current_hash))
    return changed


def sync_file(fkey, entry, current_hash):
    """Sync a single file to Lark Wiki. Returns (success, message)."""
    abs_path = os.path.join(WORKSPACE, fkey)
    obj_token = entry.get("obj_token")
    node_token = entry.get("node_token")

    # If no obj_token, need to create the Wiki page
    if not obj_token:
        space_id = entry.get("space_id")
        parent_token = entry.get("parent_token")
        title = entry.get("title", os.path.basename(fkey))
        if not space_id or not parent_token:
            return False, f"No space_id/parent_token for {fkey}, cannot create"

        cmd = [
            sys.executable, MD_TO_WIKI,
            "--create",
            "--space", space_id,
            "--parent", parent_token,
            "--title", title,
            "--file", abs_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr

        # Parse created/found node info from output
        for line in output.split("\n"):
            if "node=" in line and "obj=" in line:
                import re
                m = re.search(r'node=(\S+)\s+obj=(\S+)', line)
                if m:
                    node_token = m.group(1)
                    obj_token = m.group(2)
            if "URL:" in line:
                url = line.split("URL:")[1].strip()
                entry["url"] = url

        if not obj_token:
            return False, f"Failed to create wiki page: {output[:200]}"

        entry["node_token"] = node_token
        entry["obj_token"] = obj_token

        if result.returncode == 0:
            entry["last_hash"] = current_hash
            entry["last_synced"] = datetime.now(SGT).isoformat()
            return True, f"Created + synced → {node_token}"
        else:
            return False, f"Create failed: {output[:200]}"

    else:
        # Update existing document
        cmd = [
            sys.executable, MD_TO_WIKI,
            obj_token,
            "--file", abs_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr

        if result.returncode == 0:
            entry["last_hash"] = current_hash
            entry["last_synced"] = datetime.now(SGT).isoformat()
            return True, f"Updated → {obj_token}"
        else:
            return False, f"Update failed: {output[:200]}"


def cmd_check(args):
    """Check which files have changes without syncing."""
    sync_data = load_sync()
    changed = get_changed_files(sync_data)

    if not changed:
        print("✅ No files have changes (all up to date)")
        return

    print(f"📋 {len(changed)} file(s) have changes:")
    for fkey, entry, current_hash in changed:
        title = entry.get("title", fkey)
        has_wiki = "✅" if entry.get("obj_token") else "🆕"
        print(f"  {has_wiki} {fkey}")
        print(f"     Title: {title}")
        print(f"     Hash: {entry.get('last_hash', '(none)')[:8]}… → {current_hash[:8]}…")


def cmd_sync(args):
    """Sync all changed files with auto_sync=true."""
    ensure_token()
    sync_data = load_sync()
    changed = get_changed_files(sync_data)

    if not changed:
        print("✅ No files need syncing")
        return

    print(f"🔄 Syncing {len(changed)} file(s)...")
    success_count = 0
    fail_count = 0

    for fkey, entry, current_hash in changed:
        title = entry.get("title", fkey)
        print(f"\n  → {title} ({fkey})")
        ok, msg = sync_file(fkey, entry, current_hash)
        if ok:
            print(f"    ✅ {msg}")
            success_count += 1
        else:
            print(f"    ❌ {msg}")
            fail_count += 1

        # Save after each file to preserve partial progress
        save_sync(sync_data)
        time.sleep(1)  # Rate limiting

    print(f"\n📊 Done: {success_count} synced, {fail_count} failed")
    if fail_count > 0:
        sys.exit(1)


def cmd_register(args):
    """Register a file for wiki sync."""
    sync_data = load_sync()
    projects = sync_data.get("projects", {})

    # Resolve project to space_id and parent_token
    if args.project:
        if args.project not in projects:
            print(f"❌ Unknown project: {args.project}")
            print(f"   Available: {', '.join(projects.keys())}")
            sys.exit(1)
        proj = projects[args.project]
        space_id = proj["space_id"]
        parent_token = proj["parent_token"]
    else:
        space_id = None
        parent_token = None

    # Normalize file path (relative to workspace)
    fpath = args.file
    if os.path.isabs(fpath):
        fpath = os.path.relpath(fpath, WORKSPACE)

    entry = {
        "title": args.title,
        "space_id": space_id,
        "parent_token": parent_token,
        "node_token": args.node_token,
        "obj_token": args.obj_token,
        "url": None,
        "last_hash": "",
        "last_synced": None,
        "sync_direction": "push",
        "auto_sync": not args.no_sync,
    }

    # If node_token is provided, construct URL
    if args.node_token:
        entry["url"] = f"https://fg9w9yu3odc.sg.larksuite.com/wiki/{args.node_token}"

    sync_data.setdefault("files", {})[fpath] = entry
    save_sync(sync_data)
    print(f"✅ Registered: {fpath}")
    print(f"   Title: {args.title}")
    print(f"   Project: {args.project or '(none)'}")
    print(f"   Auto-sync: {not args.no_sync}")


def cmd_list(args):
    """List all registered file mappings."""
    sync_data = load_sync()
    files = sync_data.get("files", {})
    projects = sync_data.get("projects", {})

    print(f"📚 {len(files)} registered file(s):\n")

    # Group by sync status
    synced = []
    unsynced = []
    disabled = []

    for fkey, entry in sorted(files.items()):
        if not entry.get("auto_sync", False):
            disabled.append((fkey, entry))
        elif entry.get("obj_token"):
            synced.append((fkey, entry))
        else:
            unsynced.append((fkey, entry))

    if synced:
        print(f"  ✅ Active ({len(synced)}):")
        for fkey, entry in synced:
            last = entry.get("last_synced", "never")
            if last and last != "never":
                last = last[:19]  # Trim timezone
            print(f"     {fkey}")
            print(f"       → {entry.get('title', '?')}  (synced: {last})")

    if unsynced:
        print(f"\n  🆕 Pending creation ({len(unsynced)}):")
        for fkey, entry in unsynced:
            print(f"     {fkey}")
            print(f"       → {entry.get('title', '?')}")

    if disabled:
        print(f"\n  ⏸️  Disabled ({len(disabled)}):")
        for fkey, entry in disabled:
            print(f"     {fkey}")
            print(f"       → {entry.get('title', '?')}")

    if projects:
        print(f"\n  📁 Projects ({len(projects)}):")
        for pname, pinfo in projects.items():
            print(f"     {pname}: space={pinfo['space_id'][:8]}… parent={pinfo['parent_token'][:8]}…")


def main():
    parser = argparse.ArgumentParser(description="Auto Wiki Sync — 自动同步本地文档到 Lark Wiki")
    sub = parser.add_subparsers(dest="command")

    sync_parser = sub.add_parser("sync", help="Sync all changed files with auto_sync=true")
    # sync_parser does not take positional arguments

    sub.add_parser("check", help="Check which files have changes")
    sub.add_parser("list", help="List all registered file mappings")

    reg = sub.add_parser("register", help="Register a file for wiki sync")
    reg.add_argument("file", help="File path")
    reg.add_argument("--project", "-p", help="Project name (resolves space_id/parent_token)")
    reg.add_argument("--title", "-t", required=True, help="Wiki document title")
    reg.add_argument("--node-token", help="Existing Wiki node token")
    reg.add_argument("--obj-token", help="Existing Wiki obj token")
    reg.add_argument("--no-sync", action="store_true", help="Register but disable auto-sync")

    args = parser.parse_args()

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "register":
        cmd_register(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
