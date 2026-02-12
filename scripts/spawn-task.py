#!/usr/bin/env python3
"""
spawn-task.py — 统一任务 Spawn 入口（代码强制，消除 LLM 幻觉）

所有前置步骤自动完成，LLM 只需调用一条命令。

Usage:
  spawn-task.py create "描述" --project "从零训练模型" [--no-chat] [--source SOURCE_CHAT_ID]
      → 创建任务 + 自动建群（默认）+ 生成完整 prompt → 输出 JSON
      → --no-chat 跳过建群（用于定期检查等不需要群的任务）

  spawn-task.py prompt <task_id>
      → 输出已创建任务的完整 spawn prompt

  spawn-task.py complete <task_id> "结果摘要"
      → 标记完成 + 自动发消息到源 chat + 自动解散任务群

  spawn-task.py fail <task_id> "错误原因"
      → 标记失败 + 通知 + 解散群
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_engine import TaskEngine, BASE, TASK_BOARD, TASK_CHAT_SCRIPT

engine = TaskEngine()

SGT = timezone(timedelta(hours=8))
BACKLOG = BASE / "data" / "backlog.md"
TASK_CHAT = TASK_CHAT_SCRIPT
LARK_SEND = BASE / "scripts" / "lark-send-message.sh"
USER_TOKEN_PATH = "data/lark-user-token.json"

# ── 默认映射 ──────────────────────────────────
DEFAULT_SOURCE_CHAT = "oc_a2a70c6b4a29c2f2eb6c2500ea42a500"  # Luna 群聊


def parse_wiki_mapping():
    """从 backlog.md 解析 Wiki 目标映射表"""
    mapping = {}
    if not BACKLOG.exists():
        return mapping

    content = BACKLOG.read_text()
    # 找到 Wiki 目标映射表
    in_table = False
    for line in content.split("\n"):
        if "Wiki 目标映射" in line:
            in_table = True
            continue
        if in_table and line.startswith("|") and "---" not in line and "项目" not in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                project = parts[0]
                space_id = parts[1]
                parent_token = parts[2]
                mapping[project] = {
                    "space_id": space_id,
                    "parent_token": parent_token,
                    "description": parts[3] if len(parts) > 3 else "",
                }
        elif in_table and not line.startswith("|") and line.strip():
            break  # 表格结束

    return mapping


def parse_chat_mapping():
    """从 backlog.md 解析消息目标映射表"""
    mapping = {}
    if not BACKLOG.exists():
        return mapping

    content = BACKLOG.read_text()
    in_table = False
    for line in content.split("\n"):
        if "消息目标映射" in line:
            in_table = True
            continue
        if in_table and line.startswith("|") and "---" not in line and "目标" not in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                mapping[parts[0]] = parts[1]
        elif in_table and not line.startswith("|") and line.strip():
            break

    return mapping


def create_task_chat(task_id, task_name):
    """创建任务群聊，返回 chat_id 或 None"""
    try:
        result = subprocess.run(
            ["python3", str(TASK_CHAT), "create", task_id, task_name],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip()
        # 提取 chat_id
        for line in output.split("\n"):
            if "oc_" in line:
                match = re.search(r'(oc_[a-f0-9]+)', line)
                if match:
                    return match.group(1)
        return None
    except Exception as e:
        print(f"⚠️ 建群失败: {e}", file=sys.stderr)
        return None


def update_task_board(task_id, updates):
    """直接更新 task-board.json 中某个任务的字段"""
    board = engine.load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t.update(updates)
            break
    engine.save_board(board)


def generate_prompt(task_id, description, project, wiki_info, source_chat, task_chat_id):
    """生成完整的子任务 prompt，所有参数已注入，LLM 无需自行查找"""

    # Wiki 部分
    if wiki_info and wiki_info["space_id"] != "—":
        wiki_section = f"""## Wiki 同步（必须完成）

1. 获取 user_access_token:
   ```bash
   TOKEN=$(python3 -c "import json; print(json.load(open('{BASE}/{USER_TOKEN_PATH}'))['access_token'])")
   ```

2. 在 Wiki 创建文档节点:
   ```bash
   curl -s -X POST "https://open.larksuite.com/open-apis/wiki/v2/spaces/{wiki_info['space_id']}/nodes" \\
     -H "Authorization: Bearer $TOKEN" \\
     -H "Content-Type: application/json" \\
     -d '{{"obj_type":"docx","node_type":"origin","parent_node_token":"{wiki_info['parent_token']}","title":"文档标题"}}'
   ```

3. 将研究内容写入文档（分段写入，每段 <4500 字符）:
   ```bash
   curl -s -X POST "https://open.larksuite.com/open-apis/docx/v1/documents/$OBJ_TOKEN/blocks/$OBJ_TOKEN/children" \\
     -H "Authorization: Bearer $TOKEN" \\
     -H "Content-Type: application/json" \\
     -d '{{"children":[{{"block_type":2,"text":{{"elements":[{{"text_run":{{"content":"内容"}}}}]}}}}],"index":0}}'
   ```

### Lark Block Types 速查（代码强制，禁止凭记忆）
- Text=2, Heading1=3, Heading2=4, Heading3=5
- Bullet=12, Ordered=13, Code=14
- Divider=22
- ⚠️ 15=Quote, 16=Equation (不是列表！)
"""
    else:
        wiki_section = "## Wiki\n不需要上传 Wiki，仅存本地。"

    # 任务群聊部分
    if task_chat_id:
        chat_section = f"""## 进度汇报
- 任务群 chat_id: `{task_chat_id}`
- 在关键节点发进度更新（不要每步都发）:
  ```bash
  {LARK_SEND} "{task_chat_id}" "🔄 进度: ..."
  ```"""
    else:
        chat_section = "## 进度汇报\n无专用群聊，完成后直接发结果到源 chat。"

    # 完成/失败指令 — 使用 spawn-task.py 保证解散群聊
    SPAWN_TASK = f"python3 {BASE}/scripts/spawn-task.py"

    prompt = f"""# 子任务: {description}

项目: {project or '独立任务'}

{wiki_section}

{chat_section}

## Git 工作流（强制规则，适用于所有代码修改）
如果本任务涉及修改 git 仓库中的任何文件，**必须遵守以下流程**：
1. `git checkout -b <分支名>` — 创建 feature 分支（命名: `feat/xxx`, `fix/xxx`, `docs/xxx`）
2. 在分支上完成所有修改和 commit
3. `git push -u origin <分支名>` — 推送分支（**绝不推送 main/master**）
4. `gh pr create --title "..." --body "..."` — 创建 Pull Request
5. 在完成消息中附上 PR 链接

**⚠️ 直接 push 到 main/master 是被 Branch Protection 禁止的，push 会被拒绝。**

## 代码质量（强制规则，适用于所有代码修改）
- **输入校验**: 所有来自外部的输入（用户参数、文件内容、API 响应）在使用前必须验证格式和范围
- **错误处理**: 解析外部数据（JSON、日期、文件）必须用 try/except，不能假设格式正确
- **路径安全**: 拼接文件路径时必须验证输入不含 `..` 等遍历字符
- **裸 except 禁用**: 使用 `except Exception:` 而非 `except:`

## 消息发送（强制规则）
- **禁止用 `message` 工具**（子任务没有 Feishu 配置，会报错）
- 必须用脚本: `{LARK_SEND} "<chat_id>" "<消息内容>"`

## Wiki 注册（创建 Wiki 文档后必须执行）
如果本任务创建了新的 Wiki 文档，**必须注册到同步系统**：
```bash
python3 {BASE}/scripts/auto-wiki-sync.py register \u003c本地文件路径\u003e --project "\u003c项目名\u003e" --title "\u003cWiki文档标题\u003e" --node-token \u003cnode_token\u003e --obj-token \u003cobj_token\u003e --no-sync
```
这样文档会被自动同步系统管理，后续变更会自动推送到 Wiki。

## 完成后（必须执行，用 spawn-task.py 保证群聊自动解散）
成功时:
```bash
{SPAWN_TASK} complete {task_id} "结果摘要（一句话）"
```

失败时:
```bash
{SPAWN_TASK} fail {task_id} "失败原因"
```

⚠️ 必须用 `spawn-task.py complete/fail`，不要直接用 `task-manager.py`！
   spawn-task.py 会自动: 更新任务面板 + 发消息到源 chat + 解散任务群聊
"""
    return prompt


def cmd_create(args):
    """create "描述" --project "项目" [--chat] [--source CHAT_ID]"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("description")
    parser.add_argument("--project", "-p", default=None)
    parser.add_argument("--no-chat", action="store_true", help="不创建任务群聊（默认会创建）")
    parser.add_argument("--source", "-s", default=None, help="结果发送目标 chat_id")
    parser.add_argument("--timeout", "-t", type=int, default=1800, help="超时秒数")
    parsed = parser.parse_args(args)

    description = parsed.description
    project = parsed.project
    source_chat = parsed.source or DEFAULT_SOURCE_CHAT

    # Step 1: 创建任务
    task = engine.add(description, source_chat)
    task_id = task["id"]
    print(f"✅ 任务 {task_id} 已创建")

    # Step 2: 查找 Wiki 映射
    wiki_mapping = parse_wiki_mapping()
    wiki_info = None
    if project:
        wiki_info = wiki_mapping.get(project)
        if not wiki_info:
            # 模糊匹配
            for key, val in wiki_mapping.items():
                if project.lower() in key.lower() or key.lower() in project.lower():
                    wiki_info = val
                    project = key  # 用精确名称
                    break

        if wiki_info:
            print(f"✅ Wiki 映射: {project} → space={wiki_info['space_id']}, parent={wiki_info['parent_token']}")
        elif project != "内部参考文档":
            print(f"⚠️ 项目 '{project}' 不在 Wiki 映射表中！请先添加到 data/backlog.md", file=sys.stderr)

    # Step 3: 创建任务群聊（默认行为，--no-chat 跳过）
    task_chat_id = None
    if not parsed.no_chat:
        task_chat_id = create_task_chat(task_id, description)
        if task_chat_id:
            print(f"✅ 任务群聊: {task_chat_id}")
            update_task_board(task_id, {"task_chat_id": task_chat_id})
        else:
            print("⚠️ 建群失败，继续不带群聊", file=sys.stderr)
    else:
        print("ℹ️ 跳过建群（--no-chat）")

    # Step 4: 生成 prompt
    prompt = generate_prompt(task_id, description, project, wiki_info, source_chat, task_chat_id)

    # Step 5: 输出结果 JSON（LLM 直接用）
    result = {
        "task_id": task_id,
        "task": prompt,
        "label": task_id,
        "runTimeoutSeconds": parsed.timeout,
        "source_chat": source_chat,
        "task_chat_id": task_chat_id,
        "project": project,
        "wiki_space": wiki_info["space_id"] if wiki_info else None,
        "wiki_parent": wiki_info["parent_token"] if wiki_info else None,
    }

    # 写到临时文件供 LLM 读取
    prompt_file = BASE / "data" / "spawn-prompts" / f"{task_id}.json"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"✅ Prompt 已保存: data/spawn-prompts/{task_id}.json")
    print(f"\n📋 LLM 使用方式:")
    print(f'   sessions_spawn(task=<prompt内容>, label="{task_id}", runTimeoutSeconds={parsed.timeout})')
    print(f'   然后: python3 scripts/task-manager.py start {task_id} <session_key>')

    # 输出 JSON 到 stdout（最后）
    print(f"\n--- SPAWN_JSON ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_prompt(args):
    """输出已创建任务的完整 prompt"""
    if not args:
        print("Usage: spawn-task.py prompt <task_id>", file=sys.stderr)
        sys.exit(1)

    task_id = args[0]
    prompt_file = BASE / "data" / "spawn-prompts" / f"{task_id}.json"

    if not prompt_file.exists():
        print(f"❌ 找不到 {task_id} 的 prompt 文件", file=sys.stderr)
        sys.exit(1)

    data = json.loads(prompt_file.read_text())
    print(data["task"])


def cmd_complete(args):
    """complete <task_id> "结果" — 标记完成 + 发消息 + 解散群"""
    if len(args) < 2:
        print('Usage: spawn-task.py complete <task_id> "结果摘要"', file=sys.stderr)
        sys.exit(1)

    task_id = args[0]
    result_summary = args[1]

    # 1. Read task info BEFORE completing (complete will dissolve chat)
    board = engine.load_board()
    task = None
    for t in board["tasks"]:
        if t["id"] == task_id:
            task = t
            break

    source_chat = (task.get("source_chat") if task else None) or DEFAULT_SOURCE_CHAT
    task_chat_id = task.get("task_chat_id") if task else None

    # 2. 标记完成 (this calls engine.complete which handles dissolve + notification)
    try:
        engine.complete(task_id, result_summary)
        print(f"✅ {task_id} 标记完成")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 2.5. 触发一次 wiki 同步（最佳努力，不影响任务完成）
    try:
        auto_sync = BASE / "scripts" / "auto-wiki-sync.py"
        subprocess.run(
            ["python3", str(auto_sync), "sync"],
            capture_output=True, text=True, timeout=60
        )
    except Exception:
        pass  # Wiki sync failure should not block task completion

    # 3. Additional notification to source chat (engine.complete already sends one,
    #    but spawn-task historically also sends; engine.complete handles this now)
    if source_chat:
        print(f"📨 结果已发送到 {source_chat}")

    if task_chat_id:
        print(f"📌 任务群 {task_chat_id} 保留（用户手动关闭）")


def cmd_fail(args):
    """fail <task_id> "原因" — 标记失败 + 通知 + 解散群"""
    if len(args) < 2:
        print('Usage: spawn-task.py fail <task_id> "错误原因"', file=sys.stderr)
        sys.exit(1)

    task_id = args[0]
    error_msg = args[1]

    # 1. Read task info BEFORE failing
    board = engine.load_board()
    task = None
    for t in board["tasks"]:
        if t["id"] == task_id:
            task = t
            break

    source_chat = (task.get("source_chat") if task else None) or DEFAULT_SOURCE_CHAT
    task_chat_id = task.get("task_chat_id") if task else None

    # 2. 标记失败 (engine.fail handles dissolve + notification)
    try:
        engine.fail(task_id, error_msg)
        print(f"❌ {task_id} 标记失败")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if source_chat:
        print(f"📨 失败通知已发送到 {source_chat}")

    if task_chat_id:
        print(f"📌 任务群保留（用户手动关闭）")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "create": cmd_create,
        "prompt": cmd_prompt,
        "complete": cmd_complete,
        "fail": cmd_fail,
    }

    if cmd not in commands:
        print(f"未知命令: {cmd}")
        print(f"可用命令: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[cmd](args)


if __name__ == "__main__":
    main()
