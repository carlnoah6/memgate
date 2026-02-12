# Code Review #06: 系统运维与看门狗

**审查范围**: 11 个文件 — 看门狗、重启流程、心跳调度、Session 工具、Patch 系统
**审查日期**: 2026-02-12
**总体评级**: ⚠️ 中等风险 — 核心逻辑正确但有结构债务和竞态隐患

---

## 📊 总览

| 文件 | 行数 | 评级 | 核心问题 |
|------|------|------|----------|
| independent-watchdog.py | 310 | ✅ 良好 | 多信号判断设计优秀，少量边界问题 |
| watchdog-log.py | 55 | ⚠️ 需改进 | 时区假设错误，SIGUSR1 可能不够 |
| patch-openclaw.sh | 596 | 🔴 需重构 | 与 patches/*.py 重复，Patch 7 编号冲突，过大 |
| restart-gateway.sh | 40 | ✅ 良好 | 流程清晰，缺少 source_session 传递 |
| check-restart.sh | 42 | ⚠️ 需改进 | 后台 `&` 启动 watcher 可能丢输出 |
| mark-restart.sh | 9 | ✅ 良好 | 极简设计，符合单一职责 |
| heartbeat-scheduler.py | 82 | ✅ 良好 | 逻辑清晰，状态更新时机有小问题 |
| session-overview.py | 225 | ✅ 良好 | 高效使用 tail，分类逻辑可维护 |
| inspect_session.py | 107 | ✅ 良好 | 路径遍历防护到位 |
| cleanup-session-locks.sh | 18 | ⚠️ 需改进 | TOCTOU 竞态，PID 解析脆弱 |
| check-ci-events.py | 30 | ⚠️ 需改进 | 删除后无法恢复，缺少幂等性保护 |

---

## 1. independent-watchdog.py — 独立看门狗

### ✅ 做得好的地方
- **多信号综合判断**是核心亮点：心跳 + Session 文件 + 日志三路交叉验证，避免了之前"心跳死=系统死"的误杀问题（2/11 教训已固化）
- **原子文件操作**：`atomic_write_json()` 用 `tempfile.mkstemp()` + `os.replace()` 防崩溃写坏，`acquire_lock()` 用 `O_CREAT | O_EXCL` 保证原子性
- **限频防抖**：冷却期 + 每小时最大重启次数 + 告警限频，防止重启风暴
- **降级重启**：`openclaw gateway restart` 超时后 fallback 到 `pkill` + `start`
- Lark 通知带重试

### ⚠️ 问题与建议

**P1 — 硬编码的 APP_SECRET（安全问题）**
```python
APP_SECRET = "***LARK_SECRET_REMOVED***"  # Line 36
```
明文硬编码在脚本中。虽然这是内部工具，但如果代码库被公开或备份泄露，Lark App Secret 就暴露了。
- **建议**: 从环境变量或 `data/lark-credentials.json` 读取

**P2 — `check_cooldown` 时区对比可能出错**
```python
last = datetime.fromisoformat(state["last_restart"])
now = datetime.now(SGT)
if last.tzinfo is None:
    last = last.replace(tzinfo=SGT)  # 假设无时区=SGT
```
`replace(tzinfo=SGT)` 不做时间转换（`2026-02-12T10:00:00` 被当作 `10:00 SGT` 而非 UTC）。如果状态文件中的时间是 UTC 写入但没带 `Z`，会偏差 8 小时。
- **建议**: 统一使用 `datetime.now(timezone.utc)` 存储，或始终在 `isoformat()` 时带时区

**P3 — `get_last_heartbeat_time` 只检查 periodic 和 research**
```python
for key in ["periodic", "research"]:
    ts = checks.get(key, 0)
```
如果日后添加新的心跳任务类型（如 `dailyReport`），这里不会自动包含。
- **建议**: 遍历 `checks.values()` 取最大值，或者单独维护一个 `last_heartbeat_ts` 顶层字段

**P4 — 锁文件过期阈值 (300s) 与 crontab 间隔 (3min=180s) 不匹配**
```python
if LOCKFILE.exists():
    age = time.time() - LOCKFILE.stat().st_mtime
    if age < 300:  # 5分钟
```
Crontab 每 3 分钟触发一次，但锁过期 5 分钟。如果上一次执行崩溃且没清锁，要等 5 分钟才能恢复，期间会错过 1 次调度。
- **建议**: 锁过期阈值降到 240s（2 个周期），或者用 PID 验证（检查锁文件中的 PID 是否还存活）更可靠

**P5 — `pgrep` 双重查找的可靠性**
```python
result = subprocess.run(["pgrep", "-x", "openclaw-gate"], ...)
if result.returncode != 0:
    result = subprocess.run(["pgrep", "-f", "openclaw.*gateway"], ...)
```
`-f` 会匹配到自身进程的命令行（如果看门狗的参数包含 "openclaw.*gateway" 字样）。当前没这个问题，但未来维护风险。
- **建议**: 加 `--ignore-ancestors` 或 `-P 1`（排除 shell 子进程）

### 总评: ✅ 8/10
多信号判断设计优秀，是 2/11 误杀教训的正确固化。安全性（硬编码 secret）和时区处理需要补强。

---

## 2. watchdog-log.py — 日志分析看门狗

### ⚠️ 问题与建议

**P1 — 时区假设错误（时间比较 bug）**
```python
last_log_time = datetime.strptime(ts_match.group(1), "%Y-%m-%dT%H:%M:%S").timestamp()
current_time = time.time()
silence_duration = current_time - last_log_time
```
`datetime.strptime()` 返回的是 **naive datetime**（无时区），`.timestamp()` 会将其解释为**本地时间**。但日志中的时间戳是 UTC（带 `Z` 后缀，被正则截断了）。

在 SGT (UTC+8) 服务器上：
- 日志写 `2026-02-12T10:00:00Z`（UTC 10:00）
- 被解析为本地时间 10:00 SGT = UTC 02:00
- `silence_duration` 会多出 **8 小时**
- 结果：**永远判定为超时**

但实际上当前系统"碰巧能工作"的原因是：`TIMEOUT_SECONDS = 60`，只要日志确实在 1 分钟内有更新，即使偏差 8 小时，非超时路径上 `check_log_for_hang` 仍返回 `False`（因为 `silence_duration > TIMEOUT_SECONDS` 才进入扫描）。但方向是反的——这会导致**过度触发**而非漏报。

- **建议**: 
```python
last_log_time = datetime.strptime(ts_match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
```

**P2 — SIGUSR1 不一定能恢复挂起**
当前策略是 `pkill -USR1 -f openclaw-gateway`（热重载），但如果挂起原因是 agent loop 卡在 API 调用上（如 Claude API 无响应），SIGUSR1 只重载配置，不会中断正在进行的 HTTP 请求。
- `independent-watchdog.py` 用全进程重启作为兜底，两者形成互补
- **建议**: 在注释中标注"SIGUSR1 是快速恢复手段，完整重启由 independent-watchdog 兜底"

**P3 — 无状态/无通知**
没有任何日志输出到持久文件（只 `print`，但没有 crontab 重定向）。触发 SIGUSR1 后没有通知 Carl 或记录到状态文件。
- **建议**: 添加持久化日志和计数器

### 总评: ⚠️ 5/10
时区 bug 是实际存在的（虽然因为超短超时和 independent-watchdog 兜底暂时没爆）。建议修复时区或直接用 mtime 比较（`os.path.getmtime(log_file)` vs `time.time()`，完全绕过时间戳解析）。

---

## 3. patch-openclaw.sh — Patch 集合脚本（596行）

### 🔴 需要重构

**P0 — 与 `patches/*.py` 完全重复**
HEARTBEAT.md 列出了 8 个独立的 Python patch 脚本（`patches/apply-feishu-streaming-fix.py` 等），crontab 也每 5 分钟运行 `patch-openclaw.sh`。两套系统做同一件事：
- `patch-openclaw.sh`: 8 个 Patch（Bash + embedded Python heredoc）
- `patches/*.py`: 13 个独立 Python 脚本

哪个是 source of truth？如果两者竞争修改同一个文件，可能互相覆盖。

**建议**: 选择一套作为权威来源，废弃另一套。推荐：
- **保留 `patches/*.py`**（更精确的 pattern matching、独立可测试、有幂等性检查）
- **把 `patch-openclaw.sh` 改为编排器**：调用 `patches/*.py` 而非自己实现

**P1 — Patch 7 编号冲突**
文件中有两个 "Patch 7"：
- Line ~340: `Patch 7: 修复僵尸 "Thinking..." 卡片 — close() 时始终更新文本`（用 `sed` 把 `if (text)` 改为 `text || " "`）
- Line ~530: `Patch 7: 删除 "Thinking..." 僵尸卡片 — close() 时如果 text 为空，删除消息`（用 Python heredoc 加删除逻辑）

这两个 Patch 7 **目标矛盾**：
- 第一个让 close 时永远更新文本（空变空格）
- 第二个让 close 时空文本直接删除卡片

如果按顺序执行，第一个先把空文本变成 `" "`，第二个的 `!text || !text.trim()` 检查中 `" ".trim()` = `""` → 仍会删除。所以实际效果是第二个 Patch 7 胜出，但第一个的 `sed` 修改残留在代码中。

**建议**: 删除第一个 Patch 7（`text || " "` 版本），只保留第二个（删除僵尸卡片版本）

**P2 — 汇总输出在中间而非末尾**
```bash
# Line ~376 (中间)
echo "完成: $PATCHED 个 patch 应用, $FAILED 个失败"

# Line ~530+ (更多 patch 继续执行)
```
"Patch 8" 和重复的 "Patch 7" 都在汇总之后执行，计数器继续递增但汇总已经输出了。

**P3 — 每 5 分钟运行一次的代价**
Crontab 每 5 分钟运行此脚本，它每次都：
1. `grep -rl` 全局扫描 dist/*.js（IO 密集）
2. 读取并检查多个大文件
3. 嵌入的 Python heredoc 每次都 `read()` 整个 `plugin-sdk/index.js`（11KB+）

虽然幂等检查会快速跳过已 patch 的情况，但 grep 扫描仍有开销。
- **建议**: 在开头加一个快速指纹检查（如 `md5sum dist/plugin-sdk/index.js`），如果没变就跳过全部

**P4 — Bash heredoc 中的 Python 难以调试**
Patch 4-8 的核心逻辑用 `python3 << 'PYEOF' ... PYEOF` 内嵌，缺点：
- 语法错误只在运行时发现
- 无法单独测试
- 缩进和引号容易出错（之前 watchdog 的 f-string bug 就是类似问题）

### 总评: 🔴 3/10
功能正确但结构混乱。596 行应拆分为独立脚本 + 编排器，消除与 `patches/*.py` 的重复。

---

## 4. restart-gateway.sh — 重启流程

### ✅ 良好

四步流程清晰（标记 → wake job → 等待 → 重启），且有 `set -e` 保护。

**P1 — 缺少 source_session 传递**
`mark-restart.sh` 只接受 reason，但 HEARTBEAT.md 说 `restart-gateway.sh` 应传 `$CURRENT_SESSION`：
```bash
bash scripts/restart-gateway.sh "重启原因" "$CURRENT_SESSION"
```
脚本中 `$2` 完全没被使用——source_session 丢失了，重启后无法路由汇报到正确的 session。
- **建议**: 把 `$2` 传给 `mark-restart.sh`，写入 marker 文件的 JSON 中

**P2 — `|| true` 吞错误**
```bash
openclaw cron add ... --json 2>&1 | grep -v "Config warnings" || true
openclaw gateway restart 2>&1 || true
```
如果 `cron add` 失败（如 WebSocket 断开），wake job 不会创建，重启后不会汇报。`|| true` 让脚本继续执行但问题被静默。
- **建议**: 检查退出码并记录警告

### 总评: ✅ 7/10

---

## 5. check-restart.sh — 重启检测

### ⚠️ 需改进

**P1 — Marker 文件与 HEARTBEAT.md 描述不一致**
HEARTBEAT.md 说 `check-restart.sh` 输出 `RESTART_INFO` JSON，但实际脚本输出的是纯文本：
```bash
echo "重启原因: $(cat $MARKER)"
echo "just_restarted"
```
心跳 handler 中需要解析 `source_session`，但 marker 内容只是纯文本字符串（reason），没有 JSON 结构。
- **建议**: 让 `mark-restart.sh` 写 JSON，`check-restart.sh` 输出结构化 JSON

**P2 — 后台启动 watcher 丢失错误**
```bash
bash "$(dirname "$0")/start-knowledge-watcher.sh" 2>/dev/null &
```
`2>/dev/null &` 会吞掉所有错误。如果 watcher 启动失败，无人知晓。
- **建议**: 重定向到日志文件而非 /dev/null

**P3 — PID 检测的 TOCTOU**
```bash
CURRENT_PID=$(pgrep -f "openclaw.*gateway" | head -1)
```
这和 independent-watchdog 用的 pgrep 有同样的问题——可能匹配到非目标进程。两者应统一检测方式。

### 总评: ⚠️ 6/10

---

## 6. mark-restart.sh — 重启标记

### ✅ 良好（极简）

9 行代码，职责单一。唯一注意：marker 在 `/tmp/`，系统重启后丢失（这是预期行为——机器重启不等于 gateway 重启）。

### 总评: ✅ 9/10

---

## 7. heartbeat-scheduler.py — 心跳调度器

### ✅ 良好

**P1 — 状态提前更新导致"执行但失败"时跳过重试**
```python
# 如果有到期任务，更新状态
if due_tasks:
    for task in due_tasks:
        if task in TASKS:
            state.setdefault("lastChecks", {})[task] = now_ms
```
状态在**输出到期任务后立即更新**，但实际 spawn 是否成功取决于调用方（心跳 handler LLM）。如果 LLM 理解错误或 spawn 失败，下次心跳不会重试。
- **建议**: 由调用方（或独立确认脚本）在 spawn 成功后更新状态。或者加一个 "pending" 状态

**P2 — 每日任务只用日期判断，无法处理"当天失败需重试"**
```python
if hour >= 4 and daily_state.get("dailyReport") != today_str:
    due_tasks.append("dailyReport")
```
如果 04:00 的日报 spawn 失败，daily 状态已经被更新为 today_str，当天不会重试。
- **建议**: 引入 `pending` / `completed` 状态区分

**P3 — 非原子文件写入**
```python
with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)
```
没有用 `independent-watchdog.py` 中的 `atomic_write_json()`。虽然心跳调度器不太可能崩溃在写入中间，但为了一致性和健壮性应统一。

### 总评: ✅ 7.5/10

---

## 8. session-overview.py — Session 概览

### ✅ 良好

**优点**:
- 高效使用 `tail -50` 避免读取大文件
- `categorize_activity()` 提供简洁的中文标签
- 自动跳过 `🤖` 前缀的任务群和 subagent session

**P1 — `fmt_relative_time` 在 1-2 小时范围有歧义**
```python
if diff_sec < 3600:
    mins = int(diff_sec / 60)
    return f"{mins} 分钟"
if diff_sec < 86400:
    hours = diff_sec / 3600
    if hours < 2:
        mins = int(diff_sec / 60)
        return f"{mins} 分钟"  # 90分钟 → "90 分钟"
    return f"{hours:.1f} 小时"  # 120分钟 → "2.0 小时"
```
这个分支结构中，第一个 `< 3600` 已经处理了所有 < 60 分钟的情况，第二个 `hours < 2` 处理的是 60-120 分钟。但 60-120 分钟同时会被第一个 `< 3600` 截获（只适用于 < 60 分钟）。实际上没 bug，但代码意图不清晰。

**P2 — 无错误处理的 `subprocess.run`**
```python
result = subprocess.run(
    ["tail", "-50", session_file],
    capture_output=True, text=True, timeout=5
)
```
如果 session 文件被锁或权限错误，`tail` 可能输出到 stderr 但 returncode 非零。当前正确检查了 returncode，但没记录错误原因。

### 总评: ✅ 8/10

---

## 9. inspect_session.py — Session 检查器

### ✅ 良好

**优点**:
- `_SAFE_SESSION_ID` 正则防止路径遍历（✅ 安全）
- `_resolve_session_id` 通过 sessions.json 间接查找，支持 session key 和直接 UUID
- `tail_jsonl` 用 `deque(maxlen=N)` 实现高效尾读

**P1 — `open(sessions_file)` 没有 `with`**
```python
data = json.load(open(sessions_file))  # 文件句柄泄漏
```
- **建议**: `with open(sessions_file) as f: data = json.load(f)`

**P2 — 时间戳解析分支不够健壮**
```python
if isinstance(ts_raw, str):
    if ts_raw.endswith("Z"): ts_raw = ts_raw[:-1]
    timestamp = datetime.fromisoformat(ts_raw).timestamp()
else:
    timestamp = ts_raw / 1000.0  # 假设毫秒
```
如果 `ts_raw` 是秒级 epoch（而非毫秒），结果会偏差 1000 倍。可以加一个合理范围检查。

### 总评: ✅ 7.5/10

---

## 10. cleanup-session-locks.sh — 锁清理

### ⚠️ 需改进

**P1 — PID 解析脆弱**
```bash
pid=$(cat "$lock" 2>/dev/null | grep -o '"pid":[0-9]*' | cut -d: -f2)
```
不处理空格：`"pid": 12345`（冒号后有空格）会匹配失败。JSON 中字段顺序、空格都可能变化。
- **建议**: 用 `python3 -c "import json,sys;print(json.load(sys.stdin).get('pid',''))"` 或 `jq .pid`

**P2 — TOCTOU 竞态**
```bash
if [ -n "$pid" ] && ! ps -p "$pid" > /dev/null 2>&1; then
    rm -f "$lock"
fi
```
在 `ps -p` 检查和 `rm -f` 之间，PID 可能被复用（新进程获得了相同 PID）。虽然概率极低（PID 空间大），但在高频重启场景下可能发生。
- 实际风险低，但可以通过比较锁文件中的 PID 和实际 gateway PID 来强化

**P3 — `find -mmin +5 -delete` 和后面的循环存在重叠**
`find` 已经删除了超过 5 分钟的锁文件，后面的循环又检查所有锁。如果 `find` 已删干净，循环是空的。如果 `find` 没删完（< 5 分钟的锁），循环才有意义。逻辑对但冗余。

### 总评: ⚠️ 6/10

---

## 11. check-ci-events.py — CI 事件处理

### ⚠️ 需改进

**P1 — 读取后立即删除，无恢复能力**
```python
data = json.loads(f.read_text())
events.append(data)
f.unlink()  # 删了就没了
```
如果调用方在处理事件时崩溃，事件永久丢失。
- **建议**: 移到 `processed/` 目录而非删除，或者让调用方确认后再删

**P2 — 损坏文件也删除**
```python
except Exception:
    f.unlink()  # Remove corrupt files
```
任何异常（包括权限错误、磁盘满）都会删除文件。
- **建议**: 区分 JSON 解析错误（可删）和 IO 错误（应保留并报错）

### 总评: ⚠️ 6/10

---

## 🔍 跨文件分析

### 竞态条件汇总

| 场景 | 涉及文件 | 风险 | 严重度 |
|------|----------|------|--------|
| 两个看门狗同时重启 | independent-watchdog + watchdog-log | 后者用 SIGUSR1，前者用 restart。如果 SIGUSR1 刚发，independent 又 restart，可能双杀 | 低 — 时间窗口小 |
| heartbeat-scheduler 和心跳 handler 并发写状态 | heartbeat-scheduler.py | 调度器写状态后 handler spawn 失败，状态已更新 | 中 — 任务跳过一个周期 |
| patch-openclaw.sh 和 patches/*.py 竞争修改 | patch-openclaw.sh + patches/*.py | 两套系统同时修改 plugin-sdk/index.js | 中 — 幂等性检查可能互相干扰 |
| cleanup-session-locks 和活跃写入并发 | cleanup-session-locks.sh | 极短时间窗内删了正在使用的锁 | 低 — find 只删 >5min 的 |

### 架构建议

**1. 统一 Patch 系统（最高优先级）**

当前有两套 patch 系统并行运行：
- `patch-openclaw.sh`（crontab 每 5 分钟）— 8 个 patch
- `patches/*.py`（心跳 HEARTBEAT.md 手动列出）— 13 个独立 patch

**建议方案**：
```bash
# 新的 patch-openclaw.sh (编排器版)
#!/bin/bash
for patch in /home/ubuntu/.openclaw/workspace/patches/*.py; do
    python3 "$patch" || echo "WARN: $(basename $patch) failed"
done
```
废弃旧的 596 行版本，让 `patches/*.py` 成为唯一的 source of truth。

**2. 统一进程检测**

`independent-watchdog.py`、`check-restart.sh`、`watchdog-log.py` 三个脚本都用不同方式检测 gateway 进程：
- `pgrep -x openclaw-gate` + fallback `pgrep -f openclaw.*gateway`
- `pgrep -f "openclaw.*gateway" | head -1`
- `pkill -USR1 -f openclaw-gateway`

**建议**: 抽取为共享函数或小脚本 `scripts/gateway-pid.sh`

**3. 重启标记 JSON 化**

`mark-restart.sh` 写纯文本 → `check-restart.sh` 读纯文本。HEARTBEAT.md 期望 JSON（含 `source_session`）。应该对齐：
```bash
# mark-restart.sh
echo "{\"reason\":\"$REASON\",\"source_session\":\"$SESSION\",\"ts\":\"$(date -Iseconds)\"}" > /tmp/luna-pending-restart.marker
```

---

## 📋 建议优先级

| 优先级 | 建议 | 影响 |
|--------|------|------|
| 🔴 P0 | 统一 patch 系统（消除 patch-openclaw.sh 和 patches/*.py 重复） | 消除双系统竞争风险 |
| 🔴 P0 | 修复 patch-openclaw.sh 的 Patch 7 编号冲突 | 防止逻辑矛盾 |
| 🟡 P1 | 修复 watchdog-log.py 时区 bug | 防止过度触发 SIGUSR1 |
| 🟡 P1 | restart-gateway.sh 传递 source_session | 重启后汇报到正确的 chat |
| 🟡 P1 | check-restart.sh 输出结构化 JSON | 与 HEARTBEAT.md 描述对齐 |
| 🟡 P1 | heartbeat-scheduler.py 状态更新时机改为确认后 | 防止失败任务被跳过 |
| 🟢 P2 | independent-watchdog.py 移除硬编码 secret | 安全加固 |
| 🟢 P2 | cleanup-session-locks.sh 用 jq 解析 PID | 健壮性 |
| 🟢 P2 | check-ci-events.py 移到 processed/ 而非删除 | 可恢复性 |
| 🟢 P3 | 统一进程检测方式 | 可维护性 |
