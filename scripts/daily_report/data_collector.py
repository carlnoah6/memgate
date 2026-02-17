import os
import json
import datetime
import glob
import urllib.request
import urllib.error
from .config import (
    log, read_file, run_cmd,
    SGT, WORKSPACE, SCAN_DIRS, EXCLUDE_DIRS, CODE_EXTS, EXCLUDE_PREFIXES,
    LARK_TOKEN_FILE, CALENDAR_ID, API_PROXY, ADMIN_KEY, SESSION_DIR
)

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
        self._collect_cross_session_incidents()
        self._collect_kimi_balance()
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
            from .config import get_lark_auth_url
            auth_url = get_lark_auth_url()
            self.calendar_events = [{"error": f"API 返回 {e.code}，token 可能已过期", "auth_url": auth_url}]
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

    def _collect_kimi_balance(self):
        """采集 Kimi 余额和今日用量"""
        log("  💰 采集 Kimi 账户数据...")
        
        self.kimi_balance = {}
        
        # 1. 尝试从 Moonshot API 实时获取余额
        api_key = self._get_moonshot_api_key()
        if api_key:
            try:
                req = urllib.request.Request(
                    "https://api.moonshot.cn/v1/users/me/balance",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
                if result.get("status") and result.get("data"):
                    d = result["data"]
                    self.kimi_balance = {
                        "balance_cny": d.get("available_balance"),
                        "cash_balance": d.get("cash_balance"),
                        "voucher_balance": d.get("voucher_balance"),
                        "source": "api",
                        "platform": "Moonshot (Kimi)",
                    }
                    log(f"  💰 Kimi 余额 (API): {self.kimi_balance['balance_cny']:.2f} 元")
                else:
                    log(f"  ⚠️ Moonshot API 返回异常: {result}")
            except Exception as e:
                log(f"  ⚠️ Moonshot API 调用失败: {e}")
        
        # 2. Fallback: 读取本地余额文件
        if not self.kimi_balance.get("balance_cny"):
            balance_file = f"{WORKSPACE}/data/kimi-balance.json"
            try:
                with open(balance_file, "r") as f:
                    file_data = json.load(f)
                self.kimi_balance = {**file_data, "source": "file"}
                log(f"  💰 Kimi 余额 (文件 fallback): {self.kimi_balance.get('balance_cny', '?')} 元")
            except FileNotFoundError:
                log(f"  ⚠️ Kimi 余额文件不存在: {balance_file}")
                self.kimi_balance = {"balance_cny": None, "error": "API 和文件均不可用"}
            except Exception as e:
                log(f"  ⚠️ Kimi 余额读取失败: {e}")
                self.kimi_balance = {"balance_cny": None, "error": str(e)}
        
        # 2. 从 token_usage 中提取 Kimi 今日用量
        self.kimi_usage = {"tokens": 0, "cost_cny": 0}
        if self.token_usage:
            by_model = self.token_usage.get("by_model", {})
            kimi_data = by_model.get("kimi-k2.5", {})
            total_tokens = kimi_data.get("total", 0)
            self.kimi_usage["tokens"] = total_tokens
            
            # 计算费用 (按 12元/百万 tokens 估算)
            rate = self.kimi_balance.get("rate_per_1m_tokens_cny", 12.0)
            self.kimi_usage["cost_cny"] = round(total_tokens / 1_000_000 * rate, 2)
            log(f"  💰 Kimi 今日用量: {total_tokens:,} tokens / 约 {self.kimi_usage['cost_cny']:.2f} 元")

    def _get_moonshot_api_key(self) -> str | None:
        """从 moonshot-config.json 读取 API key"""
        config_file = f"{WORKSPACE}/data/moonshot-config.json"
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            return config.get("moonshot_api_key")
        except Exception as e:
            log(f"  ⚠️ 读取 moonshot-config.json 失败: {e}")
            return None

    def _collect_cross_session_incidents(self):
        """采集串台事件统计数据"""
        log("  🔒 采集串台事件统计...")
        
        # 从 session 日志中分析串台相关事件
        self.cross_session_stats = {
            'total_incidents': 0,
            'prevented': 0,
            'leaked': 0,
            'by_file': {},
            'by_type': {}
        }
        
        if not os.path.isdir(SESSION_DIR):
            log("  ⚠️ Session 目录不存在，跳过串台统计")
            return
        
        # 关键词匹配串台相关事件
        cross_session_keywords = ['串台', 'cross_session', '泄露', 'leak', 'context bleed']
        
        # 时间范围 (UTC)
        utc_start = self.day_start.astimezone(datetime.timezone.utc).isoformat()
        utc_end = self.day_end.astimezone(datetime.timezone.utc).isoformat()
        
        for fpath in glob.glob(f"{SESSION_DIR}/*.jsonl"):
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
                        
                        # 检查是否是串台相关事件
                        text = ""
                        if entry.get("type") == "message":
                            msg = entry.get("message", {})
                            content = msg.get("content", "") if isinstance(msg, dict) else ""
                            if isinstance(content, str):
                                text = content
                            elif isinstance(content, list):
                                text = " ".join(
                                    c.get("text", "") for c in content
                                    if isinstance(c, dict) and c.get("type") == "text"
                                )
                        
                        # 检查是否包含串台关键词
                        text_lower = text.lower()
                        for keyword in cross_session_keywords:
                            if keyword.lower() in text_lower:
                                self.cross_session_stats['total_incidents'] += 1
                                break
            except Exception:
                continue
        
        log(f"  🔒 串台事件: {self.cross_session_stats['total_incidents']} 起")
