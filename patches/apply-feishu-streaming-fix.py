#!/usr/bin/env python3
"""
Luna Patch: 修复 Feishu 流式卡片跨 turn 内容重复 bug
适用于: OpenClaw plugin-sdk/index.js (Patch 9 区域)

用法:
  python3 apply-feishu-streaming-fix.py          # 检查并应用
  python3 apply-feishu-streaming-fix.py --check  # 仅检查
  python3 apply-feishu-streaming-fix.py --force  # 强制应用（跳过版本检查）
"""

import sys
import os
import re
import shutil
from datetime import datetime

TARGET = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

# ===== PATCH DEFINITIONS =====
# Each patch is (old_pattern, new_text, description)

PATCHES = [
    # 1. Variable declarations: add lastRawPayloadText
    (
        'let lastPartialText = "";\n\t/* ── Patch 9: Accumulate text across turns when blockStreaming is off ── */\n\tlet completedTurnsText = "";\n\tconst shouldAccumulate = !(feishuCfg.blockStreaming ?? true);',
        'let lastPartialText = ""; /* Full display text (for dedup + tool status) */\n\tlet lastRawPayloadText = ""; /* Raw payload.text from last onPartialReply (for turn detection) */\n\tlet completedTurnsText = ""; /* Accumulated text from completed turns */\n\tconst shouldAccumulate = !(feishuCfg.blockStreaming ?? true);',
        "Variable declarations"
    ),
    # 2. Tool status baseText
    (
        '/* Patch 9: use accumulated text for tool status display */\n\t\t\tconst baseText = shouldAccumulate && completedTurnsText\n\t\t\t\t? completedTurnsText + (lastPartialText ? "\\n\\n" + lastPartialText : "")\n\t\t\t\t: (lastPartialText || "");',
        '/* Luna fix v4: use lastPartialText which already has accumulated display */\n\t\t\tconst baseText = lastPartialText || "";',
        "Tool status baseText"
    ),
    # 3. Block delivery reset
    (
        'lastPartialText = "";\n\t\t\t\t\tcompletedTurnsText = ""; /* Patch 9: reset on block delivery */\n\t\t\t\t\tdeferStreamingStart = true;',
        'lastPartialText = "";\n\t\t\t\t\tlastRawPayloadText = "";\n\t\t\t\t\tcompletedTurnsText = "";\n\t\t\t\t\tdeferStreamingStart = true;',
        "Block delivery reset"
    ),
    # 4. Final delivery reset
    (
        'streamingStarted = false;\n\t\t\t\t\tcompletedTurnsText = ""; /* Patch 9: reset on final delivery */\n\t\t\t\t\treturn;',
        'streamingStarted = false;\n\t\t\t\t\tlastRawPayloadText = "";\n\t\t\t\t\tcompletedTurnsText = "";\n\t\t\t\t\treturn;',
        "Final delivery reset"
    ),
    # 5. onReplyStart: remove Patch 9 accumulation
    (
        '/* Patch 9: save completed turn text before new turn starts */\n\t\t\t\tif (shouldAccumulate && lastPartialText) {\n\t\t\t\t\tcompletedTurnsText += (completedTurnsText ? "\\n\\n" : "") + lastPartialText;\n\t\t\t\t\tlastPartialText = "";\n\t\t\t\t}\n\t\t\t\tif (deferStreamingStart) return;',
        '/* Luna fix v4: removed Patch 9 accumulation from onReplyStart (per-session, not per-turn) */\n\t\t\t\tif (deferStreamingStart) return;',
        "onReplyStart cleanup"
    ),
    # 6a. Exec tool status: sanitize API keys/tokens from display
    (
        '''const cmd = String(args.command || "").trim();
				const lines = cmd.split("\\n").map(l => l.trim());
				const comments = lines.filter(l => l.startsWith("#") && l.length > 2).map(l => l.replace(/^#+\\s*/, ""));
				if (comments.length > 0) {
					summary = "⚡ " + ellipsis(comments[0], 80);
				} else {
					const first = lines.find(l => l && !l.startsWith("#")) || "";
					const bin = first.split(/\\s+/)[0].split("/").pop() || "";
					const cmdMap = {
						grep: "搜索文件", sed: "查看/编辑文件", cat: "读取文件", tail: "查看文件末尾", head: "查看文件开头",
						python3: "运行 Python", python: "运行 Python", node: "运行 Node.js",
						curl: "调用 API", wget: "下载文件",
						openclaw: "OpenClaw 命令", himalaya: "处理邮件",
						ls: "列出文件", find: "查找文件", stat: "文件信息",
						cd: "切换目录", mkdir: "创建目录", rm: "删除文件", mv: "移动文件", cp: "复制文件",
						echo: "输出文本", ps: "查看进程", pgrep: "查找进程", kill: "终止进程",
						git: "Git 操作", npm: "npm 操作", apt: "安装软件"
					};
					const label = cmdMap[bin] || bin;
					summary = "⚡ " + label + "：" + ellipsis(first, 80);
				}''',
        '''const cmd = String(args.command || "").trim();
				const lines = cmd.split("\\n").map(l => l.trim());
				const comments = lines.filter(l => l.startsWith("#") && l.length > 2).map(l => l.replace(/^#+\\s*/, ""));
				/* Luna fix: sanitize sensitive data from exec status */
				const sanitize = (s) => s.replace(/(?:API_KEY|TOKEN|SECRET|PASSWORD|APIKEY|api_key|token|secret|password|access_token|app_secret)\\s*=\\s*["']?[^\\s"';&|]+["']?/gi, "[***]")
					.replace(/(?:Bearer|Basic)\\s+[A-Za-z0-9_\\-\\.=+\\/]{10,}/gi, "[***]")
					.replace(/["'][A-Za-z0-9_\\-]{20,}["']/g, "[***]");
				if (comments.length > 0) {
					summary = "⚡ " + ellipsis(sanitize(comments[0]), 80);
				} else {
					const first = lines.find(l => l && !l.startsWith("#") && !/^\\s*(?:API_KEY|TOKEN|SECRET|PASSWORD|APIKEY)\\s*=/i.test(l)) || lines.find(l => l && !l.startsWith("#")) || "";
					const bin = first.split(/\\s+/)[0].split("/").pop() || "";
					const cmdMap = {
						grep: "搜索文件", sed: "查看/编辑文件", cat: "读取文件", tail: "查看文件末尾", head: "查看文件开头",
						python3: "运行 Python", python: "运行 Python", node: "运行 Node.js",
						curl: "调用 API", wget: "下载文件",
						openclaw: "OpenClaw 命令", himalaya: "处理邮件",
						ls: "列出文件", find: "查找文件", stat: "文件信息",
						cd: "切换目录", mkdir: "创建目录", rm: "删除文件", mv: "移动文件", cp: "复制文件",
						echo: "输出文本", ps: "查看进程", pgrep: "查找进程", kill: "终止进程",
						git: "Git 操作", npm: "npm 操作", apt: "安装软件",
						pip: "安装依赖", bash: "运行脚本", sleep: "等待中", date: "查看时间",
						file: "检查文件类型", wc: "统计文件"
					};
					const label = cmdMap[bin] || bin;
					summary = "⚡ " + label + (first ? "：" + ellipsis(sanitize(first), 80) : "");
				}''',
        "Exec tool status: sanitize API keys"
    ),
    # 6b. Add more tool status handlers (process, etc.)
    (
        '''} else if (name === "sessions_list") {
				summary = "📋 查看子任务";
			} else if (name === "sessions_history") {
				summary = "📜 查看历史";
			} else {''',
        '''} else if (name === "process") {
				const pAction = args.action || "";
				const pMap = { poll: "检查任务状态", log: "查看日志", kill: "终止进程", list: "列出进程", write: "输入数据" };
				summary = "⏳ " + (pMap[pAction] || "管理进程") + (args.sessionId ? "（" + ellipsis(args.sessionId, 20) + "）" : "");
			} else if (name === "sessions_list") {
				summary = "📋 查看子任务";
			} else if (name === "sessions_history") {
				summary = "📜 查看历史";
			} else if (name === "sessions_send") {
				summary = "📨 发送到子任务";
			} else if (name === "session_status") {
				summary = "📊 查看状态";
			} else if (name === "tts") {
				summary = "🔊 语音合成";
			} else if (name === "gateway") {
				summary = "⚙️ " + (args.action || "网关操作");
			} else if (name === "nodes") {
				summary = "📱 " + (args.action || "设备操作");
			} else if (name === "canvas") {
				summary = "🎨 " + (args.action || "画布操作");
			} else if (name === "memory_get") {
				summary = "🧠 " + basename(args.path || "读取记忆");
			} else {''',
        "Additional tool status handlers"
    ),
    # 7. onPartialReply: replace Patch 9 prepend with turn detection (renumbered from 6)
    (
        '/* Patch 9: prepend accumulated text from previous turns */\n\t\t\t\tconst displayText = shouldAccumulate && completedTurnsText\n\t\t\t\t\t? completedTurnsText + "\\n\\n" + payload.text\n\t\t\t\t\t: payload.text;\n\t\t\t\tif (displayText === lastPartialText) return;\n\t\t\t\tlastPartialText = displayText;\n\t\t\t\tawait streamingSession.update(displayText);',
        '/* Luna fix v4: Detect turn switch in onPartialReply.\n\t\t\t\t   Within a turn, payload.text grows monotonically (deltaBuffer += chunk).\n\t\t\t\t   Between turns, deltaBuffer resets, so payload.text starts fresh and short.\n\t\t\t\t   Detection: if payload.text doesn\'t start with lastRawPayloadText, new turn. */\n\t\t\t\tif (shouldAccumulate && lastRawPayloadText && !payload.text.startsWith(lastRawPayloadText)) {\n\t\t\t\t\t/* New turn: save previous raw text as completed */\n\t\t\t\t\tcompletedTurnsText += (completedTurnsText ? "\\n\\n" : "") + lastRawPayloadText;\n\t\t\t\t}\n\t\t\t\tlastRawPayloadText = payload.text;\n\t\t\t\tconst displayText = shouldAccumulate && completedTurnsText\n\t\t\t\t\t? completedTurnsText + "\\n\\n" + payload.text\n\t\t\t\t\t: payload.text;\n\t\t\t\tif (displayText === lastPartialText) return;\n\t\t\t\tlastPartialText = displayText;\n\t\t\t\tawait streamingSession.update(displayText);',
        "onPartialReply turn detection"
    ),
]

def check_patch(content):
    """Check if patch is already applied."""
    if "Luna fix v4" in content:
        return "applied"
    if "Patch 9: Accumulate text across turns" in content:
        return "needed"
    return "unknown"

def apply_patches(content):
    """Apply all patches."""
    applied = 0
    skipped = 0
    for old, new, desc in PATCHES:
        if old in content:
            content = content.replace(old, new, 1)
            applied += 1
            print(f"  ✅ {desc}")
        elif new in content:
            skipped += 1
            print(f"  ⏭️  {desc} (already applied)")
        else:
            print(f"  ⚠️  {desc} — pattern not found, may need manual review")
    return content, applied, skipped

def main():
    check_only = "--check" in sys.argv
    force = "--force" in sys.argv

    if not os.path.exists(TARGET):
        print(f"❌ File not found: {TARGET}")
        sys.exit(1)

    with open(TARGET, "r") as f:
        content = f.read()

    status = check_patch(content)

    if status == "applied":
        print("✅ Patch already applied.")
        sys.exit(0)
    elif status == "needed":
        print("🔧 Patch needed — original Patch 9 detected.")
    elif status == "unknown":
        if not force:
            print("⚠️  Cannot determine patch status. Use --force to apply anyway.")
            sys.exit(1)
        print("⚠️  Unknown state, applying with --force...")

    if check_only:
        print("Run without --check to apply.")
        sys.exit(1)

    # Backup
    backup = f"{TARGET}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(TARGET, backup)
    print(f"📋 Backup: {backup}")

    # Apply
    print("Applying patches:")
    new_content, applied, skipped = apply_patches(content)

    if applied > 0:
        with open(TARGET, "w") as f:
            f.write(new_content)
        print(f"\n✅ Done! {applied} patches applied, {skipped} already present.")
        print("🔄 Run: openclaw gateway restart")
    else:
        print(f"\n⏭️  Nothing to apply ({skipped} already present).")

if __name__ == "__main__":
    main()
