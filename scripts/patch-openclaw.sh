#!/bin/bash
# OpenClaw 源码 patch 脚本
# 每次 OpenClaw 更新后运行此脚本重新应用所有 patch
# 用法: bash scripts/patch-openclaw.sh

set -e

DIST="/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist"
PATCHED=0
FAILED=0

echo "🔧 OpenClaw 源码 Patch 脚本"
echo "=========================="
echo ""

# ============================================================
# Patch 1: Lock timeout 10s → 60s
# 文件: reply-DpTyb3Hh.js (文件名可能随版本变化)
# 原因: 子任务并发时 session file lock timeout 10s 不够用
# ============================================================
echo "--- Patch 1: Lock timeout 10s → 60s ---"
# 找到包含 lock timeout 的文件（文件名带 hash 可能变）
LOCK_FILES=$(grep -rl 'async function acquireSessionWriteLock' "$DIST"/*.js 2>/dev/null || true)
if [ -z "$LOCK_FILES" ]; then
    echo "⚠️  找不到 acquireSessionWriteLock 所在文件，可能文件名已变"
    FAILED=$((FAILED + 1))
else
    for f in $LOCK_FILES; do
        # 检查是否已经 patch 过（timeoutMs 默认值已经是 6e4）
        if grep -q 'timeoutMs ?? 6e4' "$f" 2>/dev/null; then
            echo "✅ $(basename $f) 已经是 60s，跳过"
        elif grep -q 'timeoutMs ?? 1e4' "$f" 2>/dev/null; then
            sed -i 's/timeoutMs ?? 1e4/timeoutMs ?? 6e4/' "$f"
            if grep -q 'timeoutMs ?? 6e4' "$f"; then
                echo "✅ $(basename $f) patch 成功"
                PATCHED=$((PATCHED + 1))
            else
                echo "❌ $(basename $f) patch 失败"
                FAILED=$((FAILED + 1))
            fi
        else
            echo "⚠️  $(basename $f) 找不到 'timeoutMs ?? 1e4'，可能已改变或已 patch"
            # 不算失败，可能默认值变了
        fi
    done
fi
echo ""

# ============================================================
# Patch 2: Fallback rateLimit pattern — 加入 "exhausted your capacity"
# 文件: pi-embedded-helpers-*.js (3个 chunk)
# 原因: API 代理返回 "You have exhausted your capacity" 不匹配已有 pattern，
#       导致不触发 fallback
# ============================================================
echo "--- Patch 2: Fallback pattern 'exhausted your capacity' ---"
HELPER_FILES=$(ls "$DIST"/pi-embedded-helpers-*.js 2>/dev/null | grep -v '.bak' || true)
if [ -z "$HELPER_FILES" ]; then
    echo "⚠️  找不到 pi-embedded-helpers-*.js 文件"
    FAILED=$((FAILED + 1))
else
    for f in $HELPER_FILES; do
        if grep -q 'exhausted your capacity' "$f" 2>/dev/null; then
            echo "✅ $(basename $f) 已包含 pattern，跳过"
        elif grep -q 'resource has been exhausted' "$f" 2>/dev/null; then
            sed -i 's/"resource has been exhausted",/"resource has been exhausted",\n\t\t"exhausted your capacity",/' "$f"
            if grep -q 'exhausted your capacity' "$f"; then
                echo "✅ $(basename $f) patch 成功"
                PATCHED=$((PATCHED + 1))
            else
                echo "❌ $(basename $f) patch 失败"
                FAILED=$((FAILED + 1))
            fi
        else
            echo "⚠️  $(basename $f) 找不到锚点 'resource has been exhausted'，可能结构已变"
            FAILED=$((FAILED + 1))
        fi
    done
fi
echo ""

# ============================================================
# Patch 3: Feishu webhook SDK patch — onEventDispatcher 回调
# 文件: dist/plugin-sdk/index.js
# 原因: Lark 国际版不支持 WebSocket，需要 webhook 模式
# ============================================================
echo "--- Patch 3: Feishu webhook SDK patch ---"
FEISHU_PATCH="/home/ubuntu/.openclaw/plugins/feishu-webhook/patch-feishu-webhook.sh"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$FEISHU_PATCH" ]; then
    echo "⚠️  找不到 $FEISHU_PATCH"
    FAILED=$((FAILED + 1))
elif [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q "Webhook mode patch" "$SDK_FILE" 2>/dev/null; then
    echo "✅ plugin-sdk/index.js 已包含 webhook patch，跳过"
else
    bash "$FEISHU_PATCH"
    if grep -q "Webhook mode patch" "$SDK_FILE" 2>/dev/null; then
        echo "✅ plugin-sdk/index.js patch 成功"
        PATCHED=$((PATCHED + 1))
    else
        echo "❌ plugin-sdk/index.js patch 失败"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# ============================================================
# Patch 4: Feishu 流式卡片多段保留（block → 冻结当前卡片 → 新建下一张）
# 文件: dist/plugin-sdk/index.js
# 原因: 默认行为是一张卡片反复覆盖更新，用户回看时丢失中间内容
#       改为每个 block 冻结为独立卡片，保留在对话历史中
# ============================================================
echo "--- Patch 4: Feishu streaming card multi-block retain ---"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q 'Closing streaming card and creating new one' "$SDK_FILE" 2>/dev/null; then
    echo "✅ plugin-sdk/index.js 已包含多段卡片 patch，跳过"
else
    # Patch 4a: const streamingSession → let streamingSession
    if grep -q 'const streamingSession = (feishuCfg.streaming' "$SDK_FILE" 2>/dev/null; then
        sed -i 's/\tconst streamingSession = (feishuCfg.streaming/\tlet streamingSession = (feishuCfg.streaming/' "$SDK_FILE"
        echo "  ✅ const → let 修改成功"
    elif grep -q 'let streamingSession = (feishuCfg.streaming' "$SDK_FILE" 2>/dev/null; then
        echo "  ✅ 已经是 let，跳过"
    else
        echo "  ⚠️  找不到 streamingSession 声明"
        FAILED=$((FAILED + 1))
    fi

    # Patch 4b: block deliver 逻辑改为关闭+新建
    if grep -q 'Updating streaming card with block text' "$SDK_FILE" 2>/dev/null; then
        # 用 python 做精确替换（sed 处理多行不方便）
        python3 << 'PYEOF'
import re

filepath = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
with open(filepath, "r") as f:
    content = f.read()

old = '''			if (streamingSession?.isActive() && info?.kind === "block" && payload.text) {
					logger$1.debug(`Updating streaming card with block text: ${payload.text.length} chars`);
					await streamingSession.update(payload.text);
					return;
				}'''

new = '''			if (streamingSession?.isActive() && info?.kind === "block" && payload.text) {
					logger$1.debug(`Closing streaming card and creating new one for next block: ${payload.text.length} chars`);
					await streamingSession.close(payload.text);
					streamingStarted = false;
					lastPartialText = "";
					if (options.credentials) {
						streamingSession = new FeishuStreamingSession(client, options.credentials);
						try {
							await streamingSession.start(chatId, "chat_id", options.botName);
							streamingStarted = true;
						} catch (err) {
							logger$1.warn(`Failed to start new streaming card: ${err}`);
						}
					}
					return;
				}'''

if old in content:
    content = content.replace(old, new)
    with open(filepath, "w") as f:
        f.write(content)
    print("OK")
else:
    print("NOT_FOUND")
PYEOF
        RESULT=$?
        if [ $RESULT -eq 0 ]; then
            echo "  ✅ block deliver 逻辑 patch 成功"
            PATCHED=$((PATCHED + 1))
        else
            echo "  ❌ block deliver 逻辑 patch 失败"
            FAILED=$((FAILED + 1))
        fi
    elif grep -q 'Closing streaming card and creating new one' "$SDK_FILE" 2>/dev/null; then
        echo "  ✅ block deliver 已 patch，跳过"
    else
        echo "  ⚠️  找不到 block deliver 锚点"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# ============================================================
# Patch 5: Feishu 排队通知（消息排队 3 秒后发"⏳ 收到"提示）
# 文件: dist/plugin-sdk/index.js
# 原因: 用户发第二条消息时，第一条还在处理中，没有任何反馈
# ============================================================
echo "--- Patch 5: Feishu queue notification ---"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q 'queueNotified' "$SDK_FILE" 2>/dev/null; then
    echo "✅ plugin-sdk/index.js 已包含排队通知 patch，跳过"
else
    python3 << 'PYEOF'
filepath = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
with open(filepath, "r") as f:
    content = f.read()

# Patch 5a: 在 dispatch 前加 queue timer
old_dispatch = '''	const { onModelSelected, ...prefixOptions } = createReplyPrefixOptions({
		cfg,
		agentId: resolveSessionAgentId({ config: cfg }),
		channel: "feishu",
		accountId
	});
	await dispatchReplyWithBufferedBlockDispatcher({
		ctx,'''

new_dispatch = '''	const { onModelSelected, ...prefixOptions } = createReplyPrefixOptions({
		cfg,
		agentId: resolveSessionAgentId({ config: cfg }),
		channel: "feishu",
		accountId
	});
	/* ── Patch: Queue notification ── */
	let queueNotified = false;
	let replyStarted = false;
	const queueTimer = setTimeout(async () => {
		if (!replyStarted && !queueNotified) {
			queueNotified = true;
			try {
				await sendMessageFeishu(client, chatId, { text: "⏳ 收到，前一条消息还在处理中，请稍候…" }, { msgType: "text", receiveIdType: "chat_id" });
				logger$1.debug(`Sent queue notification for chat ${chatId}`);
			} catch (err) {
				logger$1.debug(`Failed to send queue notification: ${err}`);
			}
		}
	}, 3000);
	/* ── End patch ── */
	await dispatchReplyWithBufferedBlockDispatcher({
		ctx,'''

# Patch 5b: onReplyStart 清除 timer
old_reply_start = '\t\t\tonReplyStart: async () => {\\n\t\t\t\tif (streamingSession && !streamingStarted) try {'
new_reply_start = '\t\t\tonReplyStart: async () => {\\n\t\t\t\treplyStarted = true;\\n\t\t\t\tclearTimeout(queueTimer);\\n\t\t\t\tif (streamingSession && !streamingStarted) try {'

# Patch 5c: dispatch 结束后清除 timer
old_close = '\tif (streamingSession?.isActive()) await streamingSession.close();'
new_close = '\tif (streamingSession?.isActive()) await streamingSession.close();\\n\tclearTimeout(queueTimer);'

ok = True
if old_dispatch in content:
    content = content.replace(old_dispatch, new_dispatch)
else:
    print("5a NOT_FOUND")
    ok = False

if ok:
    # For 5b and 5c, these are simpler replacements that might already be applied
    # by the time this runs (since we apply patches sequentially)
    if 'replyStarted = true;' not in content:
        content = content.replace(
            '\t\t\tonReplyStart: async () => {\n\t\t\t\tif (streamingSession && !streamingStarted) try {',
            '\t\t\tonReplyStart: async () => {\n\t\t\t\treplyStarted = true;\n\t\t\t\tclearTimeout(queueTimer);\n\t\t\t\tif (streamingSession && !streamingStarted) try {'
        )
    if 'clearTimeout(queueTimer);' not in content.split('if (streamingSession?.isActive()) await streamingSession.close();')[-1][:50]:
        content = content.replace(
            '\tif (streamingSession?.isActive()) await streamingSession.close();\n}',
            '\tif (streamingSession?.isActive()) await streamingSession.close();\n\tclearTimeout(queueTimer);\n}'
        )
    with open(filepath, "w") as f:
        f.write(content)
    print("OK")
PYEOF
    if grep -q 'queueNotified' "$SDK_FILE" 2>/dev/null; then
        echo "✅ 排队通知 patch 成功"
        PATCHED=$((PATCHED + 1))
    else
        echo "❌ 排队通知 patch 失败"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# ============================================================
# Patch 6: Feishu 流式卡片显示工具执行状态（全局事件监听版）
# 文件: dist/plugin-sdk/index.js
# 原因: 工具调用在聊天界面不可见，用户看到半截话不知道在做什么
#       用全局 onAgentEvent 监听器在流式卡片底部显示工具状态
# 注意: onAgentEvent 是全局事件发射器，不能通过 replyOptions 传递
# ============================================================
echo "--- Patch 6: Feishu streaming card tool status (global listener) ---"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q 'toolStatusCleanup' "$SDK_FILE" 2>/dev/null; then
    echo "✅ plugin-sdk/index.js 已包含工具状态 patch（全局版），跳过"
else
    python3 << 'PYEOF'
filepath = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
with open(filepath, "r") as f:
    content = f.read()

# 在 queue timer 和 dispatch 之间插入全局事件监听
old = '''	/* ── End patch ── */
	await dispatchReplyWithBufferedBlockDispatcher({'''

new = '''	/* ── End patch ── */
	/* ── Patch: Tool status in streaming card ── */
	const toolStatusCleanup = streamingSession ? onAgentEvent((evt) => {
		if (evt?.stream === "tool" && evt?.data?.phase === "start" && streamingSession.isActive()) {
			const name = evt.data.name;
			const args = evt.data.args || {};
			const basename = (p) => { const s = String(p || ""); return s.split("/").pop() || s; };
			const ellipsis = (s, n) => s && s.length > n ? s.slice(0, n) + "…" : s;
			let summary = "";
			if (name === "read") {
				summary = "📖 " + basename(args.path || args.file_path);
			} else if (name === "write") {
				summary = "📝 " + basename(args.path || args.file_path);
			} else if (name === "edit") {
				summary = "✏️ " + basename(args.path || args.file_path);
			} else if (name === "exec") {
				const cmd = String(args.command || "").replace(/\\n[\\s\\S]*/g, "").trim();
				summary = "⚡ " + ellipsis(cmd, 40);
			} else if (name === "web_search") {
				summary = "🔍 " + ellipsis(String(args.query || ""), 30);
			} else if (name === "web_fetch") {
				try { summary = "🌐 " + new URL(String(args.url)).hostname; } catch { summary = "🌐 获取网页"; }
			} else if (name === "memory_search") {
				summary = "🧠 " + ellipsis(String(args.query || ""), 30);
			} else if (name === "sessions_spawn") {
				summary = "🚀 启动子任务";
			} else if (name === "message") {
				summary = "💬 发送消息";
			} else if (name === "image") {
				summary = "🖼️ 分析图片";
			} else if (name === "browser") {
				summary = "🖥️ " + (args.action || "浏览器");
			} else if (name === "cron") {
				summary = "⏰ " + (args.action || "定时任务");
			} else {
				summary = "🔧 " + name;
			}
			const statusLine = `\\n\\n---\\n*${summary}...*`;
			streamingSession.update((lastPartialText || "") + statusLine).catch(() => {});
		}
	}) : null;
	/* ── End patch ── */
	await dispatchReplyWithBufferedBlockDispatcher({'''

# 也需要在 cleanup 处加上 toolStatusCleanup()
old_cleanup = '\tif (streamingSession?.isActive()) await streamingSession.close();\n\tclearTimeout(queueTimer);\n}'
new_cleanup = '\tif (streamingSession?.isActive()) await streamingSession.close();\n\tclearTimeout(queueTimer);\n\tif (toolStatusCleanup) toolStatusCleanup();\n}'

ok = True
if old in content:
    content = content.replace(old, new)
else:
    print("6a NOT_FOUND")
    ok = False

if ok and old_cleanup in content:
    content = content.replace(old_cleanup, new_cleanup)
elif ok:
    print("6b cleanup NOT_FOUND")
    ok = False

if ok:
    # 同时移除旧的 replyOptions 里的 onAgentEvent（如果存在）
    # 不需要了，因为 Patch 4/5/6 按顺序应用时不会有旧版
    with open(filepath, "w") as f:
        f.write(content)
    print("OK")
PYEOF
    if grep -q 'toolStatusCleanup' "$SDK_FILE" 2>/dev/null; then
        echo "✅ 工具状态 patch（全局版）成功"
        PATCHED=$((PATCHED + 1))
    else
        echo "❌ 工具状态 patch 失败"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# ============================================================
# Patch 7: 修复僵尸 "Thinking..." 卡片 — close() 时始终更新文本
# 文件: dist/plugin-sdk/index.js
# 原因: close() 里 if (text) 判断导致空文本时不更新卡片，
#       "⏳ Thinking..." 永远留在卡片上
# ============================================================
echo "--- Patch 7: Fix zombie Thinking card (close always updates text) ---"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q 'text || " "' "$SDK_FILE" 2>/dev/null; then
    echo "✅ plugin-sdk/index.js 已包含 zombie fix，跳过"
else
    # Replace 'if (text) await updateStreamingCardText(...)' with always-update version
    sed -i 's/if (text) await updateStreamingCardText(this\.credentials, this\.state\.cardId, this\.state\.elementId, text, this\.state\.sequence);/await updateStreamingCardText(this.credentials, this.state.cardId, this.state.elementId, text || " ", this.state.sequence);/' "$SDK_FILE"
    if grep -q 'text || " "' "$SDK_FILE" 2>/dev/null; then
        echo "✅ zombie fix patch 成功"
        PATCHED=$((PATCHED + 1))
    else
        echo "❌ zombie fix patch 失败"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# ============================================================
# Patch 8: Block 交付后 lazy-start 流式卡片（不立即创建）
# 文件: dist/plugin-sdk/index.js
# 原因: block 关闭后立即创建新卡片，如果没有后续 block，
#       新卡片成为僵尸 "Thinking..." 卡片
# ============================================================
echo "--- Patch 8: Lazy-start streaming card after block delivery ---"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q "Don't start eagerly" "$SDK_FILE" 2>/dev/null; then
    echo "✅ plugin-sdk/index.js 已包含 lazy-start patch，跳过"
else
    python3 << 'PYEOF'
filepath = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
with open(filepath, "r") as f:
    content = f.read()

ok = True

# 8a: Remove eager start from block delivery
old_block = '''					streamingSession = new FeishuStreamingSession(client, options.credentials);
						try {
							await streamingSession.start(chatId, "chat_id", options.botName);
							streamingStarted = true;
						} catch (err) {
							logger$1.warn(`Failed to start new streaming card: ${err}`);
						}'''

new_block = '''					streamingSession = new FeishuStreamingSession(client, options.credentials);
						// Don't start eagerly — will be started lazily on next partial reply'''

if old_block in content:
    content = content.replace(old_block, new_block)
else:
    # Might already be patched or structure changed
    if "Don't start eagerly" not in content:
        print("8a NOT_FOUND")
        ok = False

# 8b: Add lazy-start to onPartialReply
old_partial = '''			onPartialReply: streamingSession ? async (payload) => {
				if (!streamingSession.isActive() || !payload.text) return;
				if (payload.text === lastPartialText) return;
				lastPartialText = payload.text;
				await streamingSession.update(payload.text);
			} : void 0,
			onReasoningStream: streamingSession ? async (payload) => {
				if (!streamingSession.isActive() || !payload.text) return;
				if (payload.text === lastPartialText) return;
				lastPartialText = payload.text;
				await streamingSession.update(payload.text);
			} : void 0'''

new_partial = '''			onPartialReply: streamingSession ? async (payload) => {
				if (!streamingSession || !payload.text) return;
				if (!streamingSession.isActive() && !streamingStarted) {
					try {
						await streamingSession.start(chatId, "chat_id", options.botName);
						streamingStarted = true;
					} catch (err) {
						logger$1.warn(`Failed to lazy-start streaming card: ${err}`);
						return;
					}
				}
				if (!streamingSession.isActive()) return;
				if (payload.text === lastPartialText) return;
				lastPartialText = payload.text;
				await streamingSession.update(payload.text);
			} : void 0,
			onReasoningStream: streamingSession ? async (payload) => {
				if (!streamingSession || !payload.text) return;
				if (!streamingSession.isActive() && !streamingStarted) {
					try {
						await streamingSession.start(chatId, "chat_id", options.botName);
						streamingStarted = true;
					} catch (err) {
						logger$1.warn(`Failed to lazy-start streaming card: ${err}`);
						return;
					}
				}
				if (!streamingSession.isActive()) return;
				if (payload.text === lastPartialText) return;
				lastPartialText = payload.text;
				await streamingSession.update(payload.text);
			} : void 0'''

if old_partial in content:
    content = content.replace(old_partial, new_partial)
elif "lazy-start" not in content:
    print("8b NOT_FOUND")
    ok = False

if ok:
    with open(filepath, "w") as f:
        f.write(content)
    print("OK")
PYEOF
    if grep -q "Don't start eagerly" "$SDK_FILE" 2>/dev/null; then
        echo "✅ lazy-start patch 成功"
        PATCHED=$((PATCHED + 1))
    else
        echo "❌ lazy-start patch 失败"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# ============================================================
# 汇总
# ============================================================
echo "=========================="
echo "完成: $PATCHED 个 patch 应用, $FAILED 个失败"
if [ $FAILED -gt 0 ]; then
    echo "⚠️  有失败项，请手动检查"
    exit 1
else
    echo "✅ 全部 OK"
fi

# ============================================================
# Patch 7: 删除 "Thinking..." 僵尸卡片
# 文件: dist/plugin-sdk/index.js
# 原因: 流式卡片创建后如果没有任何文字更新就被 close，
#       会留下一张只显示 "⏳ Thinking..." 的僵尸卡片
# 方案: close() 时如果 text 为空，删除消息而不是保留
# ============================================================
echo "--- Patch 7: Delete zombie Thinking cards ---"
SDK_FILE="$DIST/plugin-sdk/index.js"
if [ ! -f "$SDK_FILE" ]; then
    echo "⚠️  找不到 $SDK_FILE"
    FAILED=$((FAILED + 1))
elif grep -q 'Patch 7.*zombie' "$SDK_FILE" 2>/dev/null; then
    echo "✅ 僵尸卡片 patch 已存在，跳过"
else
    python3 << 'PYEOF'
filepath = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
with open(filepath, "r") as f:
    content = f.read()

old = '''\tasync close(finalText, summary) {
\t\tif (!this.state || this.closed) return;
\t\tthis.closed = true;
\t\tawait this.updateQueue;
\t\tconst text = finalText ?? this.state.currentText;
\t\tthis.state.sequence += 1;'''

new = '''\tasync close(finalText, summary) {
\t\tif (!this.state || this.closed) return;
\t\tthis.closed = true;
\t\tawait this.updateQueue;
\t\tconst text = finalText ?? this.state.currentText;
\t\t/* ── Patch 7: Delete zombie "Thinking..." cards ── */
\t\tif ((!text || !text.trim()) && this.state.messageId) {
\t\t\ttry {
\t\t\t\tawait this.client.im.message.delete({ path: { message_id: this.state.messageId } });
\t\t\t\tlogger$2.info(`Deleted empty streaming card (no content): messageId=${this.state.messageId}`);
\t\t\t} catch (err) {
\t\t\t\tlogger$2.debug(`Failed to delete empty streaming card: ${String(err)}`);
\t\t\t}
\t\t\treturn;
\t\t}
\t\t/* ── End Patch 7 ── */
\t\tthis.state.sequence += 1;'''

if old in content:
    content = content.replace(old, new)
    with open(filepath, "w") as f:
        f.write(content)
    print("OK")
else:
    print("NOT_FOUND")
PYEOF
    if grep -q 'Patch 7.*zombie' "$SDK_FILE" 2>/dev/null; then
        echo "✅ 僵尸卡片 patch 成功"
        PATCHED=$((PATCHED + 1))
    else
        echo "❌ 僵尸卡片 patch 失败"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""
