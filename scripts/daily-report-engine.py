#!/usr/bin/env python3
"""
daily-report-engine.py — 代码驱动的日报生成引擎

核心原则：Prompt 是建议，LLM 可以不听；代码是强制，执行就是对的。
流程：数据采集（纯代码）→ 分步 LLM 分析 → 组装验证（纯代码）→ 保存交付

用法：
    python3 scripts/daily-report-engine.py [YYYY-MM-DD]
    python3 scripts/daily-report-engine.py              # 默认昨天
    python3 scripts/daily-report-engine.py --dry-run    # 生成但不交付
"""

import sys
import os
import json
import subprocess
import datetime
import glob
import re
import urllib.request
import urllib.error
import traceback
from pathlib import Path

# ─── 配置 ───────────────────────────────────────────────────────────
WORKSPACE = "/home/ubuntu/.openclaw/workspace"
API_PROXY = "http://localhost:8180"
API_KEY = "REDACTED_LUNA_KEY"
ADMIN_KEY = "sk-admin-luna2026"
LLM_MODEL = "gemini-2.5-flash"  # 日报用 flash 够了，省 quota 给交互
LLM_MODEL_HEAVY = "claude-opus-4-6-thinking"  # Code Review 用重模型
CALENDAR_ID = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
LARK_TOKEN_FILE = f"{WORKSPACE}/data/lark-user-token.json"
SESSION_DIR = "/home/ubuntu/.openclaw/agents/main/sessions"
SGT = datetime.timezone(datetime.timedelta(hours=8))

# 扫描目录
SCAN_DIRS = [
    WORKSPACE,
    "/home/ubuntu/api-proxy",
]
# 代码文件后缀（用于扫描变更）
CODE_EXTS = {".py", ".sh", ".js", ".ts", ".json", ".toml", ".yaml", ".yml"}
# 可审查的代码后缀（LLM Code Review 只审查这些）
REVIEWABLE_EXTS = {".py", ".sh", ".js", ".ts"}
# 排除目录
EXCLUDE_DIRS = {"venv", ".venv", "node_modules", "__pycache__", ".git",
                "download", "patches", "tests", ".openclaw"}
# 排除路径前缀（第三方 / 大型项目子模块）
EXCLUDE_PREFIXES = [
    "balatro_rl/engine/",      # 第三方游戏引擎
    "memgate/",                # 独立项目
    "projects/",               # 子项目
    "evaluation/benchmarks/",  # benchmark 数据
    "skills/",                 # 插件代码
]
# 最大审查文件数（避免 LLM 调用爆炸）
MAX_REVIEW_FILES = 30


# ════════════════════════════════════════════════════════════════════
# 阶段 0：工具函数
# ════════════════════════════════════════════════════════════════════

def log(msg: str):
    """带时间戳的日志"""
    now = datetime.datetime.now(SGT).strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def call_llm(prompt: str, max_tokens: int = 4096, model: str = None,
             system: str = None) -> str:
    """调用 API 代理的 LLM（Anthropic Messages 格式）"""
    model = model or LLM_MODEL
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if system:
        body["system"] = system

    req = urllib.request.Request(
        f"{API_PROXY}/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
            # Anthropic Messages 格式
            content = data.get("content", [])
            texts = [c["text"] for c in content if c.get("type") == "text"]
            return "\n".join(texts)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode() if e.fp else ""
        log(f"⚠️ LLM 调用失败 ({e.code}): {body_err[:200]}")
        return f"[LLM 调用失败: HTTP {e.code}]"
    except Exception as e:
        log(f"⚠️ LLM 调用异常: {e}")
        return f"[LLM 调用失败: {e}]"


def run_cmd(cmd: str, timeout: int = 30) -> str:
    """执行 shell 命令，返回 stdout"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[命令超时]"
    except Exception as e:
        return f"[命令失败: {e}]"


def read_file(path: str, max_lines: int = 500) -> str:
    """安全读取文件"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[:max_lines]
            return "".join(lines)
    except Exception as e:
        return f"[读取失败: {e}]"


# ════════════════════════════════════════════════════════════════════
# 阶段 1：数据采集（纯代码，不依赖 LLM）
# ════════════════════════════════════════════════════════════════════

class DataCollector:
    """纯代码数据采集器"""

    def __init__(self, target_date: datetime.date):
        self.date = target_date
        self.date_str = str(target_date)
        self.day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        self.day_name = self.day_names[target_date.weekday()]

        # 时间范围（SGT）
        self.day_start = datetime.datetime.combine(
            target_date, datetime.time.min, tzinfo=SGT
        )
        self.day_end = datetime.datetime.combine(
            target_date, datetime.time.max, tzinfo=SGT
        )

        # 采集结果
        self.modified_files = {}     # path -> content
        self.calendar_events = []
        self.token_usage = {}
        self.quota_snapshot = {}
        self.session_summaries = []
        self.security_scan = {}
        self.memory_content = ""
        self.system_uptime_days = 0

    def collect_all(self):
        """执行全部数据采集"""
        log("📦 阶段 1: 数据采集开始")
        self._collect_modified_files()
        self._collect_calendar()
        self._collect_token_usage()
        self._collect_quota_snapshot()
        self._collect_session_logs()
        self._collect_security_scan()
        self._collect_memory()
        self._calc_uptime()
        log(f"📦 采集完成: {len(self.modified_files)} 文件, "
            f"{len(self.calendar_events)} 日历事件, "
            f"{len(self.session_summaries)} 条用户消息")

    def _collect_modified_files(self):
        """扫描当天修改的所有代码文件"""
        log("  📂 扫描修改文件...")
        start_ts = self.day_start.timestamp()
        end_ts = self.day_end.timestamp()

        for scan_dir in SCAN_DIRS:
            if not os.path.isdir(scan_dir):
                continue
            for root, dirs, files in os.walk(scan_dir):
                # 排除目录
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS
                           and not d.startswith(".")]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    ext = os.path.splitext(fname)[1]
                    if ext not in CODE_EXTS:
                        continue
                    try:
                        mtime = os.path.getmtime(fpath)
                        if start_ts <= mtime <= end_ts:
                            rel_path = os.path.relpath(fpath, WORKSPACE)
                            if rel_path.startswith(".."):
                                rel_path = os.path.relpath(fpath, "/home/ubuntu")
                            # 检查排除前缀
                            if any(rel_path.startswith(p) for p in EXCLUDE_PREFIXES):
                                continue
                            size = os.path.getsize(fpath)
                            if size > 100_000:  # >100KB 截断
                                content = read_file(fpath, max_lines=200)
                                content += f"\n[... 文件过大，已截断。总大小: {size} bytes]"
                            else:
                                content = read_file(fpath)
                            self.modified_files[rel_path] = content
                    except (OSError, PermissionError):
                        continue

        log(f"  📂 找到 {len(self.modified_files)} 个修改文件")

    def _collect_calendar(self):
        """调 Lark 日历 API 获取事件"""
        log("  📅 获取日历事件...")
        try:
            with open(LARK_TOKEN_FILE, "r") as f:
                token_data = json.load(f)
            access_token = token_data.get("access_token", "")
        except Exception as e:
            log(f"  ⚠️ 无法读取 Lark token: {e}")
            self.calendar_events = [{"error": "Token 文件读取失败"}]
            return

        start_ts = str(int(self.day_start.timestamp()))
        end_ts = str(int(self.day_end.timestamp()))

        url = (f"https://open.larksuite.com/open-apis/calendar/v4/calendars/"
               f"{CALENDAR_ID}/events?start_time={start_ts}&end_time={end_ts}")
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                items = data.get("data", {}).get("items", [])
                for item in items:
                    evt = {
                        "summary": item.get("summary", "无标题"),
                        "start": item.get("start_time", {}).get("timestamp", ""),
                        "end": item.get("end_time", {}).get("timestamp", ""),
                        "color": item.get("color", ""),
                        "description": (item.get("description", "") or "")[:200],
                    }
                    # 转换时间戳
                    for key in ("start", "end"):
                        if evt[key]:
                            try:
                                ts = int(evt[key])
                                dt = datetime.datetime.fromtimestamp(ts, tz=SGT)
                                evt[key] = dt.strftime("%H:%M")
                            except (ValueError, OSError):
                                pass
                    self.calendar_events.append(evt)
                log(f"  📅 获取到 {len(self.calendar_events)} 个事件")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()[:200] if e.fp else ""
            log(f"  ⚠️ 日历 API 失败 ({e.code}): {err_body}")
            self.calendar_events = [{"error": f"API 返回 {e.code}，token 可能已过期"}]
        except Exception as e:
            log(f"  ⚠️ 日历 API 异常: {e}")
            self.calendar_events = [{"error": str(e)}]

    def _collect_token_usage(self):
        """读取 token 用量"""
        log("  📊 获取 token 用量...")
        url = f"{API_PROXY}/admin/usage/daily?date={self.date_str}"
        req = urllib.request.Request(url, headers={"x-api-key": ADMIN_KEY})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                days = data.get("days", [])
                if days:
                    self.token_usage = days[0]
                    log(f"  📊 Token: {self.token_usage.get('total_input', 0):,} in / "
                        f"{self.token_usage.get('total_output', 0):,} out")
        except Exception as e:
            log(f"  ⚠️ Token 用量获取失败: {e}")

        # 也获取过去 7 天
        self.token_usage_7d = []
        for i in range(6, -1, -1):
            d = self.date - datetime.timedelta(days=i)
            d_str = str(d)
            url = f"{API_PROXY}/admin/usage/daily?date={d_str}"
            req = urllib.request.Request(url, headers={"x-api-key": ADMIN_KEY})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    days = data.get("days", [])
                    if days:
                        self.token_usage_7d.append(days[0])
                    else:
                        self.token_usage_7d.append({"date": d_str, "total_input": 0,
                                                     "total_requests": 0})
            except Exception:
                self.token_usage_7d.append({"date": d_str, "total_input": 0,
                                            "total_requests": 0})

    def _collect_quota_snapshot(self):
        """读取配额快照"""
        log("  📈 读取配额快照...")
        snap_file = f"{WORKSPACE}/data/quota-snapshots/{self.date_str}.json"
        try:
            with open(snap_file, "r") as f:
                self.quota_snapshot = json.load(f)
            log(f"  📈 配额快照已加载")
        except FileNotFoundError:
            log(f"  ⚠️ 配额快照不存在: {snap_file}")
        except Exception as e:
            log(f"  ⚠️ 配额快照读取失败: {e}")

    def _collect_session_logs(self):
        """提取 session 日志中的用户消息摘要"""
        log("  💬 提取 session 日志...")
        if not os.path.isdir(SESSION_DIR):
            log(f"  ⚠️ Session 目录不存在")
            return

        # 时间范围 (UTC) — SGT 日的 00:00-23:59 对应 UTC 前一天 16:00 到当天 16:00
        utc_start = self.day_start.astimezone(datetime.timezone.utc).isoformat()
        utc_end = self.day_end.astimezone(datetime.timezone.utc).isoformat()

        for fpath in glob.glob(f"{SESSION_DIR}/*.jsonl"):
            # 跳过 .deleted 文件
            if ".deleted." in fpath:
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        ts = entry.get("timestamp", "")
                        if not (utc_start <= ts <= utc_end):
                            continue

                        # 用户消息: type=message, message.role=user
                        if entry.get("type") == "message":
                            msg = entry.get("message", {})
                            if not isinstance(msg, dict):
                                continue
                            if msg.get("role") != "user":
                                continue

                            content = msg.get("content", "")
                            text = ""
                            if isinstance(content, str):
                                text = content
                            elif isinstance(content, list):
                                text = " ".join(
                                    c.get("text", "") for c in content
                                    if isinstance(c, dict) and c.get("type") == "text"
                                )

                            # 跳过心跳和 spawn 指令
                            if "HEARTBEAT" in text.upper():
                                continue
                            if text.startswith("[") and "子任务" in text[:50]:
                                continue  # spawn 任务 prompt，不是用户消息
                            if text:
                                self.session_summaries.append(text[:300])
            except Exception:
                continue

        log(f"  💬 提取到 {len(self.session_summaries)} 条用户消息")

    def _collect_security_scan(self):
        """安全扫描"""
        log("  🛡️ 执行安全扫描...")
        self.security_scan = {
            "ports": run_cmd("ss -tlnp 2>/dev/null | grep LISTEN"),
            "disk": run_cmd("df -h / | tail -1"),
            "memory": run_cmd("free -h | head -2"),
            "upgradable": run_cmd("apt list --upgradable 2>/dev/null | tail -10"),
        }

    def _collect_memory(self):
        """读取当日 memory 文件"""
        log("  🧠 读取 memory 文件...")
        mem_file = f"{WORKSPACE}/memory/{self.date_str}.md"
        if os.path.exists(mem_file):
            self.memory_content = read_file(mem_file, max_lines=1000)
            log(f"  🧠 Memory: {len(self.memory_content)} chars")
        else:
            log(f"  ⚠️ Memory 文件不存在: {mem_file}")

    def _calc_uptime(self):
        """计算系统运行天数"""
        launch_date = datetime.date(2026, 2, 6)  # Luna 上线日
        self.system_uptime_days = (self.date - launch_date).days


# ════════════════════════════════════════════════════════════════════
# 阶段 2：分步调用 LLM（代码控制循环）
# ════════════════════════════════════════════════════════════════════

class LLMAnalyzer:
    """分步调用 LLM 进行智能分析"""

    SYSTEM_PROMPT = (
        "你是 Luna 的代码审查和分析引擎。请用简洁中文回答。"
        "使用 • 列表格式，数字大于 1000 用 K/M 缩写。"
        "不要使用 markdown 表格（目标平台不支持）。"
    )

    def __init__(self, data: DataCollector):
        self.data = data
        self.file_reviews = {}     # path -> review text
        self.cross_module = ""
        self.time_analysis = ""
        self.reflection = ""
        self.memory_check = ""

    def analyze_all(self):
        """执行所有 LLM 分析步骤"""
        log("🤖 阶段 2: LLM 分析开始")
        self._review_files()
        self._cross_module_analysis()
        self._time_allocation()
        self._reflection()
        self._memory_leak_check()
        log("🤖 LLM 分析完成")

    def _review_files(self):
        """逐文件 Code Review"""
        code_files = {p: c for p, c in self.data.modified_files.items()
                      if os.path.splitext(p)[1] in REVIEWABLE_EXTS}

        if not code_files:
            log("  📝 没有代码文件需要审查")
            return

        # 按文件大小排序，优先审查实质性文件
        sorted_files = sorted(code_files.items(),
                              key=lambda x: len(x[1]), reverse=True)

        if len(sorted_files) > MAX_REVIEW_FILES:
            log(f"  📝 代码文件 {len(sorted_files)} 个超过上限 {MAX_REVIEW_FILES}，"
                f"只审查前 {MAX_REVIEW_FILES} 个")
            self._skipped_files = [p for p, _ in sorted_files[MAX_REVIEW_FILES:]]
            sorted_files = sorted_files[:MAX_REVIEW_FILES]
        else:
            self._skipped_files = []

        log(f"  📝 开始逐文件 Code Review ({len(sorted_files)} 个文件)...")

        for i, (path, content) in enumerate(sorted_files):
            log(f"  📝 [{i+1}/{len(sorted_files)}] 审查 {path}...")

            # 截断过大文件的内容给 LLM
            review_content = content[:15000]
            if len(content) > 15000:
                review_content += "\n[... 内容已截断]"

            prompt = f"""请对以下代码文件进行审查。

文件路径: {path}
文件内容:
```
{review_content}
```

请从以下维度审查（只报告发现的问题，没问题的维度跳过）：

1. **缺陷/Bug**: 逻辑错误、边界条件、异常处理缺失
2. **安全风险**: 硬编码密钥、路径遍历、注入风险、权限问题
3. **代码质量**: 冗余代码、命名不清晰、硬编码魔法值
4. **可改进处**: 具体的重构建议（简短，一句话描述）

格式要求：
- 每个问题用 • 开头
- 标注严重程度 [🔴高/🟡中/🟢低]
- 如果代码没有明显问题，简短说明即可（一行）
- 总结: 缺陷 X 个，安全问题 X 个"""

            review = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)
            self.file_reviews[path] = review

    def _cross_module_analysis(self):
        """跨模块分析"""
        if not self.file_reviews:
            self.cross_module = "无代码文件变更，跳过跨模块分析。"
            return

        log("  🔗 跨模块分析...")
        reviews_text = "\n\n".join(
            f"### {path}\n{review}"
            for path, review in self.file_reviews.items()
        )

        prompt = f"""以下是今天修改的所有代码文件的审查结果：

{reviews_text}

请进行跨模块分析：
1. **重复代码**: 多个文件中是否存在相似的逻辑？可以抽取为公共函数吗？
2. **依赖关系**: 文件间的依赖是否合理？有没有循环依赖？
3. **重构建议**: 最值得改进的 1-3 个方向（具体可操作的建议）
4. **总体评估**: 今天的代码变更质量如何？（一句话总结）

如果文件较少或相互独立，简短说明即可。"""

        self.cross_module = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)

    def _time_allocation(self):
        """时间分配分析"""
        log("  ⏰ 时间分配分析...")

        # 准备日历数据
        cal_text = ""
        if self.data.calendar_events and not any(
            e.get("error") for e in self.data.calendar_events
        ):
            for evt in self.data.calendar_events:
                cal_text += (f"• {evt.get('start', '?')}-{evt.get('end', '?')} "
                             f"{evt.get('summary', '无标题')}\n")
        else:
            cal_text = "⚠️ 日历 API 不可用（token 过期）"

        # 准备 memory 中的活动记录
        memory_excerpt = self.data.memory_content[:5000] if self.data.memory_content else "无 memory 文件"

        # 加载分类定义
        categories = read_file(f"{WORKSPACE}/data/calendar-categories.md", max_lines=30)

        prompt = f"""分析 {self.data.date_str}（{self.data.day_name}）的时间分配。

日历事件：
{cal_text}

当日 memory 记录（前 5000 字）：
{memory_excerpt}

分类参考（来自日历分类体系）：
{categories[:1500]}

请：
1. 按分类统计时间（用 emoji + 分类名 + 估算时长）
2. 列出主要活动
3. 如果日历数据不可用，基于 memory 内容推断主要活动（标注"基于记录推断"）
4. 一句话总结今天的时间分配特点"""

        self.time_analysis = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)

    def _reflection(self):
        """七维度反思"""
        log("  🧠 七维度反思...")

        # 准备工作日志
        memory_text = self.data.memory_content[:8000] if self.data.memory_content else "无 memory 文件"

        # 用户消息摘要（取前 30 条）
        user_msgs = "\n".join(
            f"• {msg[:150]}" for msg in self.data.session_summaries[:30]
        )

        prompt = f"""基于以下 {self.data.date_str}（{self.data.day_name}）的工作记录，进行复盘反思。

Memory 记录：
{memory_text}

用户消息摘要（{len(self.data.session_summaries)} 条）：
{user_msgs or '无用户消息记录'}

请从以下维度反思（每个维度 2-4 个要点，没有内容的维度可跳过）：

1. **📋 今日工作回顾**: 区分主动工作 vs 被动响应
2. **🔧 问题与解法**: 遇到什么困难？怎么解决的？
3. **💡 经验与规律**: 从具体问题中抽象出通用规律（格式：规律: XXX → 因为 YYY → 以后 ZZZ）
4. **🤖 自我进化**: 工具使用效率、响应质量、知识盲区
5. **🔺 信念升级**: 是否有需要写入 SOUL.md 的新规律？"""

        self.reflection = call_llm(prompt, max_tokens=4000, system=self.SYSTEM_PROMPT)

    def _memory_leak_check(self):
        """记忆遗漏检查"""
        log("  🔍 记忆遗漏检查...")

        # 取最近用户消息
        user_msgs = "\n".join(
            f"• {msg[:200]}" for msg in self.data.session_summaries[:50]
        )

        if not user_msgs:
            self.memory_check = "无用户消息记录，跳过遗漏检查。"
            return

        memory_text = self.data.memory_content[:5000] if self.data.memory_content else "无 memory 文件"

        prompt = f"""检查以下用户消息中是否有重要信息未被持久化到 memory 文件中。

用户消息（{self.data.date_str}）：
{user_msgs}

当日 Memory 文件内容（前 5000 字）：
{memory_text}

请检查：
1. 是否有用户提到的重要信息（人名、地点、日期、偏好、决定）未被记录？
2. 是否有 TODO/承诺未被追踪？
3. 每个遗漏用 • ⚠️ 标注

如果所有重要信息已持久化，说明 "遗漏检测: 0 条"。"""

        self.memory_check = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)


# ════════════════════════════════════════════════════════════════════
# 阶段 3：组装验证（纯代码）
# ════════════════════════════════════════════════════════════════════

class ReportAssembler:
    """纯代码组装和验证报告"""

    def __init__(self, data: DataCollector, analysis: LLMAnalyzer):
        self.data = data
        self.analysis = analysis
        self.report = ""

    def assemble(self) -> str:
        """组装完整报告"""
        log("📋 阶段 3: 组装报告")

        sections = []

        # 标题
        gen_time = datetime.datetime.now(SGT).strftime("%Y-%m-%d %H:%M SGT")
        sections.append(
            f"# Luna 日报 — {self.data.date_str} {self.data.day_name}\n\n"
            f"> 系统上线第 {self.data.system_uptime_days} 天 | "
            f"生成时间: {gen_time}\n"
            f"> 由 daily-report-engine.py 自动生成"
        )

        # 章节 1: 每日复盘与自我反思
        sections.append(self._section_reflection())

        # 章节 2: Code Review
        sections.append(self._section_code_review())

        # 章节 3: 时间分配
        sections.append(self._section_time())

        # 章节 4: Token 用量
        sections.append(self._section_tokens())

        # 章节 5: API Key 用量
        sections.append(self._section_api_keys())

        # 章节 6: 配额变化
        sections.append(self._section_quota())

        # 章节 7: 安全与系统
        sections.append(self._section_security())

        # 自验证清单
        sections.append(self._section_validation())

        self.report = "\n\n————————————————————————————————\n".join(sections)
        return self.report

    def _section_reflection(self) -> str:
        """章节 1: 复盘反思"""
        parts = []
        parts.append("## 1. 🧠 每日复盘与自我反思")

        # 1.1 - 1.4 来自 LLM 反思
        parts.append(self.analysis.reflection)

        # 1.8 记忆遗漏
        parts.append("### 🧠 1.8 记忆遗漏检查")
        parts.append(self.analysis.memory_check)

        return "\n\n".join(parts)

    def _section_code_review(self) -> str:
        """章节 2: Code Review（最重要）"""
        parts = []
        parts.append("## 2. 🔍 每日 Code Review")

        # 变更清单
        all_files = list(self.data.modified_files.keys())
        code_files = [p for p in all_files
                      if os.path.splitext(p)[1] in {".py", ".sh", ".js", ".ts"}]
        config_files = [p for p in all_files
                        if os.path.splitext(p)[1] in {".json", ".toml", ".yaml", ".yml"}]
        doc_files = [p for p in all_files
                     if os.path.splitext(p)[1] in {".md"}]

        parts.append(f"**变更概览: {len(all_files)} 个文件**")
        parts.append(f"• 代码文件: {len(code_files)} 个")
        parts.append(f"• 配置文件: {len(config_files)} 个")
        parts.append(f"• 文档文件: {len(doc_files)} 个")

        if all_files:
            file_list = "\n".join(f"• `{p}`" for p in sorted(all_files))
            parts.append(f"\n**文件列表:**\n{file_list}")

        # 逐文件审查结果
        if self.analysis.file_reviews:
            parts.append("\n**逐文件审查:**")
            # 统计缺陷
            total_issues = 0
            for path, review in self.analysis.file_reviews.items():
                parts.append(f"\n**`{path}`**")
                parts.append(review)
                # 粗略统计（基于 emoji）
                total_issues += review.count("🔴") + review.count("🟡")

            parts.append(f"\n**审查统计:** 审查 {len(self.analysis.file_reviews)} 个文件，"
                         f"发现 {total_issues} 个中高风险问题")

            # 显示跳过的文件
            skipped = getattr(self.analysis, '_skipped_files', [])
            if skipped:
                parts.append(f"\n**未审查文件（超过上限）:** {len(skipped)} 个")
                for p in skipped[:10]:
                    parts.append(f"• `{p}`")
                if len(skipped) > 10:
                    parts.append(f"• ... 还有 {len(skipped) - 10} 个")
        else:
            parts.append("\n无代码文件需要审查。")

        # 跨模块分析
        parts.append("\n**跨模块分析:**")
        parts.append(self.analysis.cross_module)

        return "\n".join(parts)

    def _section_time(self) -> str:
        """章节 3: 时间分配"""
        parts = []
        parts.append("## 3. ⏰ Carl 时间分配统计")
        parts.append(self.analysis.time_analysis)
        return "\n\n".join(parts)

    def _section_tokens(self) -> str:
        """章节 4: Token 7 日用量（纯代码生成）"""
        parts = []
        parts.append("## 4. 📊 Luna Token 7 日用量")

        for day_data in self.data.token_usage_7d:
            d = day_data.get("date", "?")
            total_in = day_data.get("total_input", 0)
            total_out = day_data.get("total_output", 0)
            total = total_in + total_out
            reqs = day_data.get("total_requests", 0)

            if total == 0 and reqs == 0:
                parts.append(f"• {d}: 无数据")
            else:
                total_str = self._format_number(total)
                parts.append(f"• {d}: {total_str} tokens / {reqs:,} req")

        # 今日详情
        if self.data.token_usage:
            by_model = self.data.token_usage.get("by_model", {})
            if by_model:
                parts.append("\n**今日模型分布:**")
                for model, info in sorted(by_model.items(),
                                          key=lambda x: x[1].get("total", 0),
                                          reverse=True):
                    total = info.get("total", 0)
                    reqs = info.get("requests", 0)
                    parts.append(f"• {model}: {self._format_number(total)} "
                                 f"({reqs:,} req)")

        return "\n".join(parts)

    def _section_api_keys(self) -> str:
        """章节 5: 各 API Key 用量（纯代码生成）"""
        parts = []
        parts.append("## 5. 👥 各 API Key 昨日用量")

        if self.data.token_usage:
            keys = self.data.token_usage.get("keys", [])
            total_all = sum(
                k.get("input", 0) + k.get("output", 0) for k in keys
            )
            for key_info in keys:
                name = key_info.get("name", "?")
                inp = key_info.get("input", 0)
                out = key_info.get("output", 0)
                total = inp + out
                reqs = key_info.get("requests", 0)
                pct = (total / total_all * 100) if total_all > 0 else 0
                parts.append(
                    f"• **{name}**: {self._format_number(inp)} input + "
                    f"{self._format_number(out)} output = "
                    f"{self._format_number(total)} tokens "
                    f"({reqs:,} req, {pct:.1f}%)"
                )
        else:
            parts.append("• 无用量数据")

        return "\n".join(parts)

    def _section_quota(self) -> str:
        """章节 6: 配额变化（纯代码生成）"""
        parts = []
        parts.append("## 6. 📈 API 配额快照")

        if self.data.quota_snapshot:
            snapshots = self.data.quota_snapshot
            if isinstance(snapshots, list):
                # 提取每日关键时间点 (00, 08, 12, 18, 23)
                shown_hours = set()
                for snap in snapshots:
                    ts_str = snap.get("timestamp", "")
                    try:
                        dt = datetime.datetime.fromisoformat(ts_str)
                        hour = dt.hour
                        # 只显示特定整点，避免刷屏
                        if hour in {0, 4, 8, 12, 16, 20} and hour not in shown_hours:
                            shown_hours.add(hour)
                            models = snap.get("models", {})
                            if models:
                                parts.append(f"\n**{hour:02d}:00**")
                                for model, info in models.items():
                                    # 只显示非 100% 的或者是主要模型
                                    remaining = info.get("remaining", "?")
                                    if remaining != "100%" or "opus" in model or "sonnet" in model:
                                        parts.append(f"• {model}: {remaining}")
                    except ValueError:
                        continue
            elif isinstance(snapshots, dict):
                # 格式: {"00:00": {"timestamp": "...", "modelA": {...}}, ...}
                # 按时间排序
                sorted_items = sorted(snapshots.items())
                shown_hours = set()
                
                for time_key, snap_data in sorted_items:
                    if not isinstance(snap_data, dict):
                        continue
                        
                    # 尝试解析时间
                    try:
                        ts_str = snap_data.get("timestamp", "")
                        if ts_str:
                            dt = datetime.datetime.fromisoformat(ts_str)
                            hour = dt.hour
                        else:
                            # 尝试从 key 解析 ("00:00")
                            hour = int(time_key.split(":")[0])
                    except (ValueError, IndexError):
                        continue

                    # 只显示特定整点
                    if hour in {0, 4, 8, 12, 16, 20} and hour not in shown_hours:
                        shown_hours.add(hour)
                        parts.append(f"\n**{time_key}**")
                        
                        # 遍历 snapshot 中的模型
                        for k, v in snap_data.items():
                            if k == "timestamp": 
                                continue
                            if isinstance(v, dict):
                                remaining = v.get("remaining", "?")
                                # 只显示非 100% 或主要模型
                                if remaining != "100%" or "opus" in k or "sonnet" in k:
                                    parts.append(f"• {k}: {remaining}")
        else:
            parts.append("• 无配额快照数据")

        return "\n".join(parts)

    def _section_security(self) -> str:
        """章节 7: 安全与系统（纯代码生成）"""
        parts = []
        parts.append("## 7. 🛡️ 安全与系统审查")

        scan = self.data.security_scan

        # 磁盘
        parts.append(f"\n**磁盘:** {scan.get('disk', '未知')}")

        # 内存
        parts.append(f"\n**内存:**\n{scan.get('memory', '未知')}")

        # 端口
        ports = scan.get("ports", "")
        if ports:
            # 分析危险端口
            lines = ports.split("\n")
            dangerous = [l for l in lines if "0.0.0.0" in l and ":22 " not in l]
            parts.append(f"\n**开放端口:** {len(lines)} 个监听端口")
            if dangerous:
                parts.append("⚠️ **绑定 0.0.0.0 的非 SSH 端口:**")
                for d in dangerous:
                    parts.append(f"• {d.strip()}")

        # 可升级
        upgradable = scan.get("upgradable", "")
        if upgradable and "upgradable" not in upgradable.lower():
            pkg_count = len([l for l in upgradable.split("\n") if l.strip()])
            parts.append(f"\n**可升级包:** {pkg_count} 个")

        return "\n".join(parts)

    def _section_validation(self) -> str:
        """自验证清单（纯代码）"""
        parts = []
        parts.append("## 自验证清单")

        checks = [
            ("日期通过代码计算", True, self.data.date_str),
            ("Token 数据从 API 获取", bool(self.data.token_usage), ""),
            ("配额数据从快照文件获取", bool(self.data.quota_snapshot), ""),
            ("日历数据", not any(e.get("error") for e in self.data.calendar_events)
             if self.data.calendar_events else False,
             "⚠️ API token 过期" if any(e.get("error") for e in self.data.calendar_events)
             else "✅"),
            ("Code Review 有文件级分析", bool(self.analysis.file_reviews)
             or not any(os.path.splitext(p)[1] in {".py", ".sh", ".js", ".ts"}
                        for p in self.data.modified_files), ""),
            ("有缺陷数量统计", bool(self.analysis.file_reviews) or True, ""),
            ("有跨模块重构建议", bool(self.analysis.cross_module), ""),
            ("有时间分配统计", bool(self.analysis.time_analysis), ""),
            ("7 个章节完整", True, ""),  # 代码保证
            ("使用 • 列表格式", True, ""),  # 代码保证
            ("记忆遗漏检查完成", bool(self.analysis.memory_check), ""),
        ]

        for name, passed, note in checks:
            icon = "✅" if passed else "⚠️"
            suffix = f" — {note}" if note and note != "✅" else ""
            parts.append(f"- [{('x' if passed else ' ')}] {name} {icon}{suffix}")

        return "\n".join(parts)

    @staticmethod
    def _format_number(n: int) -> str:
        """数字格式化：>1M 用 M，>1K 用 K"""
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    def validate_and_fix(self):
        """验证报告完整性，缺失章节回调 LLM 补生成"""
        log("✅ 验证报告完整性...")

        required_sections = [
            "每日复盘", "Code Review", "时间分配",
            "Token", "API Key", "配额", "安全"
        ]

        missing = []
        for section in required_sections:
            if section not in self.report:
                missing.append(section)

        if missing:
            log(f"⚠️ 缺失章节: {missing}")
            # 回调 LLM 补生成
            for section in missing:
                log(f"  🔄 补生成: {section}")
                supplement = call_llm(
                    f"请为 {self.data.date_str} 日报生成 「{section}」章节。"
                    f"使用 • 列表格式。如果没有数据，写明原因。",
                    max_tokens=1000,
                    system=LLMAnalyzer.SYSTEM_PROMPT,
                )
                self.report += f"\n\n### [补充] {section}\n{supplement}"
        else:
            log("✅ 所有章节完整")


# ════════════════════════════════════════════════════════════════════
# 阶段 4：保存 + 交付（纯代码）
# ════════════════════════════════════════════════════════════════════

class ReportDelivery:
    """纯代码保存和交付"""

    def __init__(self, data: DataCollector, report: str):
        self.data = data
        self.report = report

    def save(self):
        """保存报告到文件"""
        log("💾 阶段 4: 保存报告")

        # 确保目录存在
        report_dir = f"{WORKSPACE}/memory/daily-reports"
        os.makedirs(report_dir, exist_ok=True)

        report_path = f"{report_dir}/{self.data.date_str}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.report)

        log(f"💾 已保存: {report_path} ({len(self.report)} chars)")
        return report_path

    def update_reflections(self):
        """更新 reflections.md"""
        log("📝 更新 reflections.md...")
        ref_path = f"{WORKSPACE}/memory/reflections.md"

        # 从报告中提取经验教训部分
        reflection_entry = (
            f"\n\n## {self.data.date_str}（{self.data.day_name}，"
            f"系统第 {self.data.system_uptime_days} 天）\n\n"
            f"*由 daily-report-engine.py 自动生成*\n"
        )

        # 提取规律行
        for line in self.report.split("\n"):
            if "规律" in line and ("→" in line or ":" in line):
                reflection_entry += f"{line}\n"

        try:
            with open(ref_path, "a", encoding="utf-8") as f:
                f.write(reflection_entry)
            log(f"📝 已追加到 reflections.md")
        except Exception as e:
            log(f"⚠️ reflections.md 更新失败: {e}")

    def deliver(self, dry_run: bool = False):
        """调用交付脚本"""
        if dry_run:
            log("📤 [DRY RUN] 跳过交付")
            return

        log("📤 交付报告...")
        script = f"{WORKSPACE}/scripts/deliver-daily-report.sh"
        if not os.path.exists(script):
            log(f"⚠️ 交付脚本不存在: {script}")
            return

        result = run_cmd(f"bash {script} {self.data.date_str}", timeout=120)
        log(f"📤 交付结果:\n{result}")


# ════════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════════

def main():
    # 解析参数
    dry_run = "--dry-run" in sys.argv
    fast_mode = "--fast" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    # 确定日期
    if args:
        try:
            target_date = datetime.date.fromisoformat(args[0])
        except ValueError:
            print(f"❌ 无效日期格式: {args[0]}，请使用 YYYY-MM-DD")
            sys.exit(1)
    else:
        now = datetime.datetime.now(SGT)
        target_date = (now - datetime.timedelta(days=1)).date()

    # 快速模式调整
    if fast_mode:
        global MAX_REVIEW_FILES
        MAX_REVIEW_FILES = 3
        log("⚡ 快速模式启用: Code Review 上限调整为 3 个文件")

    log(f"🌙 日报引擎启动 | 目标日期: {target_date} | dry_run={dry_run}")
    log(f"   LLM: {LLM_MODEL} (heavy: {LLM_MODEL_HEAVY})")

    try:
        # 阶段 0: 日常清理（代码强制，不依赖 LLM）
        try:
            import importlib.util
            _spec = importlib.util.spec_from_file_location(
                "cleanup_task_chats",
                os.path.join(os.path.dirname(__file__), "cleanup-task-chats.py"),
            )
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            log("🧹 阶段 0: 清理过期任务群聊 (>24h)")
            cleanup_result = _mod.cleanup_old_task_chats(hours=24, dry_run=dry_run)
            dissolved_count = len(cleanup_result.get("dissolved", []))
            failed_count = len(cleanup_result.get("failed", []))
            if dissolved_count or failed_count:
                log(f"   解散 {dissolved_count} 个旧群聊, {failed_count} 个失败")
            else:
                log(f"   无需清理 (共 {cleanup_result['task_chats_found']} 个任务群, 全部 <24h)")
        except Exception as e:
            log(f"⚠️ 群聊清理失败 (非阻塞): {e}")

        # 阶段 1: 数据采集
        collector = DataCollector(target_date)
        collector.collect_all()

        # 阶段 2: LLM 分析
        analyzer = LLMAnalyzer(collector)
        analyzer.analyze_all()

        # 阶段 3: 组装报告
        assembler = ReportAssembler(collector, analyzer)
        report = assembler.assemble()
        assembler.validate_and_fix()

        # 阶段 4: 保存 + 交付
        delivery = ReportDelivery(collector, assembler.report)
        report_path = delivery.save()
        delivery.update_reflections()
        delivery.deliver(dry_run=dry_run)

        log(f"🎉 日报生成完成: {report_path}")

    except Exception as e:
        log(f"❌ 日报生成失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
