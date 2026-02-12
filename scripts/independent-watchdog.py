#!/usr/bin/env python3
"""
independent-watchdog.py — 独立于 OpenClaw 心跳的系统级看门狗

设计原则：冗余防卡死，但不误杀
  Layer 1: OpenClaw 心跳（every 5m）— 正常情况下的调度器
  Layer 2: 本脚本（system crontab every 3m）— 心跳失效时的后备
  Layer 3: 进程存活检测 — 进程崩溃时由 systemd 自动重启

本脚本由 crontab 直接驱动，不依赖 OpenClaw 的任何内部机制。
即使 OpenClaw agent loop 完全卡死，crontab 仍会触发本脚本。

重启决策（多信号综合判断，避免误杀活跃对话）：
  1. 进程存活？ — 不活 → 启动
  2. 心跳在执行？ — heartbeat-state.json 最后时间 > N 分钟 → 可能卡死
  3. Session 有写入？ — 最后 session 文件修改时间
  4. Gateway 日志有写入？ — 日志文件修改时间

  只有当 心跳 + Session + 日志 全部超时，才判定系统真的死了。
  如果心跳死了但 Session/日志还活着 → 只发告警，不重启。

⚠️ 2026-02-11 教训：看门狗在 Carl 活跃聊天时强制重启，因为只看心跳不看其他信号。
   心跳没跑 ≠ 系统坏了。心跳机制可以独立故障。

Usage: 由 crontab 调用
  */3 * * * * /usr/bin/python3 /home/ubuntu/.openclaw/workspace/scripts/independent-watchdog.py >> /home/ubuntu/.openclaw/workspace/logs/watchdog.log 2>&1
"""

import json
import os
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────
SGT = timezone(timedelta(hours=8))
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
LOGS_DIR = WORKSPACE / "logs"
WATCHDOG_STATE = WORKSPACE / "data" / "watchdog-state.json"
HEARTBEAT_STATE = WORKSPACE / "data" / "heartbeat-state.json"
SESSION_DIR = Path("/home/ubuntu/.openclaw/agents/main/sessions")
RESTART_MARKER = WORKSPACE / "data" / "restart-marker.json"
LOCKFILE = Path("/tmp/independent-watchdog.lock")
OPENCLAW = "/home/ubuntu/.npm-global/bin/openclaw"
GATEWAY_LOG_DIR = Path("/tmp/openclaw")

# 阈值（动态读取心跳配置后覆盖）
HEARTBEAT_THRESHOLD_MINUTES = 10   # 默认：心跳超过 10 分钟未执行 → 可能卡死
SESSION_THRESHOLD_MINUTES = 15     # Session 无更新超过 15 分钟 → 辅助确认
LOG_THRESHOLD_MINUTES = 10         # 日志无更新超过 10 分钟 → 辅助确认
COOLDOWN_MINUTES = 5               # 重启后冷却 5 分钟
MAX_RESTARTS_PER_HOUR = 3          # 每小时最多重启 3 次
ALERT_INTERVAL_MINUTES = 30        # 告警最多每 30 分钟发一次
GRACE_PERIOD_MINUTES = 15          # 首次启动/状态文件缺失时的宽限期

# 心跳间隔倍数（阈值 = 间隔 × 倍数）
HEARTBEAT_THRESHOLD_MULTIPLIER = 2.5  # 阈值是心跳间隔的 2.5 倍（给一些缓冲）


def parse_heartbeat_interval():
    """从 HEARTBEAT.md 或 AGENTS.md 解析心跳间隔（分钟）
    
    支持的格式：
    - 心跳已启用（every: 5m）
    - 心跳: every 30m
    - Heartbeat: every 5min
    - every: 30m
    - every: 5 minutes
    
    返回：间隔分钟数（默认 5）
    """
    import re
    
    files_to_check = [
        WORKSPACE / "HEARTBEAT.md",
        WORKSPACE / "AGENTS.md",
    ]
    
    patterns = [
        r'every[:\s]+(\d+)\s*(m|min|minute|minutes)?',  # every: 5m, every 30m, every: 5 minutes
        r'心跳.*?(\d+)\s*(分钟|m|min)',  # 中文：心跳（每 5 分钟）
        r'heartbeat.*?(\d+)\s*(m|min|minute|minutes)?',  # Heartbeat every 5m
    ]
    
    for file_path in files_to_check:
        if not file_path.exists():
            continue
        try:
            content = file_path.read_text()
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    minutes = int(match.group(1))
                    if 1 <= minutes <= 1440:  # 合理范围：1分钟到24小时
                        logmsg(f"📖 从 {file_path.name} 读取心跳间隔: {minutes} 分钟")
                        return minutes
        except Exception as e:
            logmsg(f"⚠️ 读取 {file_path.name} 失败: {e}")
            continue
    
    logmsg("📖 使用默认心跳间隔: 5 分钟")
    return 5  # 默认值


def get_heartbeat_threshold():
    """获取心跳阈值（基于配置的间隔）"""
    interval = parse_heartbeat_interval()
    threshold = int(interval * HEARTBEAT_THRESHOLD_MULTIPLIER)
    # 确保最小阈值（避免间隔太小导致误报）
    return max(threshold, 8)  # 至少 8 分钟

# Lark 通知 — use lark_common centralized credentials
try:
    import importlib.util
    _lc_spec = importlib.util.spec_from_file_location("lark_common", str(WORKSPACE / "scripts" / "lark_common.py"))
    _lc = importlib.util.module_from_spec(_lc_spec)
    _lc_spec.loader.exec_module(_lc)
    APP_ID = _lc.APP_ID
    APP_SECRET = _lc.APP_SECRET
except Exception:
    # Fallback: hardcoded credentials (watchdog must never fail to start)
    APP_ID = "cli_a90c3a6163785ed2"
    APP_SECRET = "***LARK_SECRET_REMOVED***"
CARL_CHAT = "oc_453c88ec52dd029845c46249837e3ba0"


def logmsg(msg):
    """输出带时间戳的日志行（避免与变量名 log_minutes 混淆）"""
    now = datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def acquire_lock():
    """原子创建锁文件，防止多实例并行（O_CREAT | O_EXCL 保证原子性）"""
    try:
        if LOCKFILE.exists():
            age = time.time() - LOCKFILE.stat().st_mtime
            if age < 300:
                logmsg("另一个实例运行中，退出")
                return False
            logmsg(f"清理过期锁（{age:.0f}s）")
            try:
                LOCKFILE.unlink()
            except FileNotFoundError:
                pass  # 另一个进程已经清理了

        # 原子创建锁文件：O_CREAT | O_EXCL 保证只有一个进程能成功
        fd = os.open(str(LOCKFILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        logmsg("锁竞争失败，退出")
        return False
    except Exception as e:
        logmsg(f"获取锁异常: {e}")
        return False


def release_lock():
    try:
        LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass


def atomic_write_json(path, data):
    """原子写入 JSON 文件：写临时文件 → rename，防止写到一半崩溃导致损坏"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 在同一目录创建临时文件，保证 rename 是原子的（同一文件系统）
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, str(path))  # 原子替换
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def load_state():
    if WATCHDOG_STATE.exists():
        try:
            return json.loads(WATCHDOG_STATE.read_text())
        except (json.JSONDecodeError, ValueError) as e:
            logmsg(f"⚠️ 状态文件损坏（{e}），重置")
        except Exception as e:
            logmsg(f"⚠️ 读取状态文件异常（{e}），重置")
    return {"restarts": [], "last_restart": None, "total_restarts": 0,
            "last_alert": None, "alert_count": 0}


def save_state(state):
    atomic_write_json(WATCHDOG_STATE, state)


def is_gateway_running():
    """检查 gateway 进程是否存活，返回 (是否存活, PID 列表)"""
    try:
        # 先尝试精确匹配进程名（pgrep -x 匹配 15 字符截断后的名字）
        result = subprocess.run(
            ["pgrep", "-x", "openclaw-gate"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            # Fallback: 模式匹配完整命令行
            result = subprocess.run(
                ["pgrep", "-f", "openclaw.*gateway"],
                capture_output=True, text=True, timeout=5
            )
        pids = [p for p in result.stdout.strip().split("\n") if p and p.isdigit()]
        return len(pids) > 0, pids
    except subprocess.TimeoutExpired:
        logmsg("⚠️ pgrep 超时")
        return False, []
    except Exception:
        return False, []


def get_last_heartbeat_time():
    """检查心跳调度器的最后执行时间，返回 UTC datetime 或 None"""
    if not HEARTBEAT_STATE.exists():
        return None
    try:
        data = json.loads(HEARTBEAT_STATE.read_text())
        checks = data.get("lastChecks", {})
        latest_ms = 0
        for key in ["periodic", "research"]:
            ts = checks.get(key, 0)
            if isinstance(ts, (int, float)) and ts > latest_ms:
                latest_ms = ts
        if latest_ms > 0:
            return datetime.fromtimestamp(latest_ms / 1000, tz=timezone.utc)
    except (json.JSONDecodeError, ValueError, TypeError, OSError):
        pass
    return None


def get_last_session_time():
    """获取最近 session 文件的修改时间，返回 UTC datetime 或 None"""
    try:
        if not SESSION_DIR.exists():
            return None
        sessions = sorted(
            SESSION_DIR.glob("*.jsonl"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        if sessions:
            mtime = sessions[0].stat().st_mtime
            return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except Exception:
        pass
    return None


def get_last_log_time():
    """获取 Gateway 日志文件的最后修改时间。
    
    直接扫描 /tmp/openclaw/ 目录找最新的日志文件，
    而不是拼日期构造文件名（OpenClaw 用 UTC 日期命名，本地是 SGT，会错位）。
    """
    try:
        if not GATEWAY_LOG_DIR.exists():
            return None
        log_files = sorted(
            GATEWAY_LOG_DIR.glob("openclaw-*.log"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        if log_files:
            mtime = log_files[0].stat().st_mtime
            return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except Exception:
        pass
    return None


def check_cooldown(state):
    """检查是否在冷却期内（刚重启过，或频率过高）"""
    if state.get("last_restart"):
        try:
            last = datetime.fromisoformat(state["last_restart"])
            now = datetime.now(SGT)
            # 确保都有时区信息再比较
            if last.tzinfo is None:
                last = last.replace(tzinfo=SGT)
            elapsed = (now - last).total_seconds() / 60
            if elapsed < COOLDOWN_MINUTES:
                logmsg(f"冷却期（{elapsed:.1f}分钟前重启），跳过")
                return True
        except (ValueError, TypeError):
            pass

    now_ts = time.time()
    recent = [t for t in state.get("restarts", []) if isinstance(t, (int, float)) and now_ts - t < 3600]
    if len(recent) >= MAX_RESTARTS_PER_HOUR:
        logmsg(f"1小时内已重启 {len(recent)} 次，跳过")
        return True

    return False


def should_alert(state):
    """检查是否应该发告警（限频：每 30 分钟最多一次）"""
    last_alert = state.get("last_alert")
    if not last_alert:
        return True
    try:
        last = datetime.fromisoformat(last_alert)
        now = datetime.now(SGT)
        if last.tzinfo is None:
            last = last.replace(tzinfo=SGT)
        elapsed = (now - last).total_seconds() / 60
        return elapsed >= ALERT_INTERVAL_MINUTES
    except (ValueError, TypeError):
        return True


def send_lark_notification(message, max_retries=2):
    """发送 Lark 通知，带重试机制（看门狗通知是关键路径）"""
    for attempt in range(max_retries + 1):
        try:
            token_req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(token_req, timeout=10) as resp:
                resp_data = json.loads(resp.read())
                token = resp_data.get("tenant_access_token")
                if not token:
                    logmsg(f"Lark token 响应异常: {resp_data}")
                    continue

            send_req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
                data=json.dumps({
                    "receive_id": CARL_CHAT,
                    "msg_type": "text",
                    "content": json.dumps({"text": message})
                }).encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(send_req, timeout=10):
                logmsg("Lark 通知已发送")
                return True

        except Exception as e:
            logmsg(f"Lark 通知异常 (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2)

    logmsg("❌ Lark 通知最终失败")
    return False


def send_alert(reason, state):
    """发告警但不重启（心跳死了但系统还活着）"""
    if not should_alert(state):
        logmsg(f"告警限频中，跳过: {reason}")
        return

    logmsg(f"⚠️ 发送告警（不重启）: {reason}")
    send_lark_notification(
        f"⚠️ 看门狗告警（未重启）\n"
        f"原因: {reason}\n"
        f"时间: {datetime.now(SGT).strftime('%H:%M:%S')}\n"
        f"说明: 系统仍在处理消息，仅心跳调度器异常。下次心跳应会自动恢复。"
    )
    state["last_alert"] = datetime.now(SGT).isoformat()
    state["alert_count"] = state.get("alert_count", 0) + 1
    save_state(state)


def restart_gateway(reason, state):
    logmsg(f"🔄 执行重启: {reason}")

    marker = {
        "reason": f"[独立看门狗] {reason}",
        "timestamp": datetime.now(SGT).isoformat(),
        "target_chat": CARL_CHAT,
        "source": "independent-watchdog"
    }
    atomic_write_json(RESTART_MARKER, marker)

    send_lark_notification(
        f"🐕 独立看门狗触发重启\n"
        f"原因: {reason}\n"
        f"时间: {datetime.now(SGT).strftime('%H:%M:%S')}\n"
        f"重启后心跳会自动恢复"
    )

    try:
        subprocess.run(
            [OPENCLAW, "gateway", "restart"],
            capture_output=True, text=True, timeout=30
        )
        logmsg("✅ 重启完成")
    except subprocess.TimeoutExpired:
        logmsg("⚠️ 重启超时，强制 kill")
        try:
            subprocess.run(["pkill", "-f", "openclaw-gateway"], timeout=5)
            time.sleep(2)
            subprocess.run([OPENCLAW, "gateway", "start"], timeout=30)
        except Exception as e:
            logmsg(f"❌ 强制重启失败: {e}")
    except Exception as e:
        logmsg(f"❌ 重启失败: {e}")

    state["last_restart"] = datetime.now(SGT).isoformat()
    state["restarts"].append(time.time())
    state["total_restarts"] = state.get("total_restarts", 0) + 1
    state["alert_count"] = 0  # 重启后重置告警计数
    now_ts = time.time()
    state["restarts"] = [t for t in state["restarts"] if isinstance(t, (int, float)) and now_ts - t < 3600]
    save_state(state)


def main():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if not acquire_lock():
        return

    try:
        state = load_state()
        now_utc = datetime.now(timezone.utc)

        # ── Check 1: 进程存活 ──
        running, pids = is_gateway_running()
        if not running:
            logmsg("❌ Gateway 进程不存在")
            if not check_cooldown(state):
                restart_gateway("进程不存在", state)
            return

        logmsg(f"✅ 进程存活 (PID: {pids[0] if pids else '?'})")

        # ── Check 2: 冷却期 ──
        if check_cooldown(state):
            return

        # ── Check 3: 多信号综合判断 ──
        # 动态获取心跳阈值（基于配置的心跳间隔）
        heartbeat_threshold = get_heartbeat_threshold()
        logmsg(f"心跳阈值: {heartbeat_threshold} 分钟（基于配置间隔 × {HEARTBEAT_THRESHOLD_MULTIPLIER}）")
        
        last_heartbeat = get_last_heartbeat_time()
        last_session = get_last_session_time()
        last_log = get_last_log_time()

        # 计算各信号的分钟数
        hb_minutes = None
        sess_minutes = None
        log_minutes = None

        if last_heartbeat:
            hb_minutes = (now_utc - last_heartbeat).total_seconds() / 60
            logmsg(f"最后心跳: {hb_minutes:.1f} 分钟前")

        if last_session:
            sess_minutes = (now_utc - last_session).total_seconds() / 60
            logmsg(f"最后 Session 更新: {sess_minutes:.1f} 分钟前")

        if last_log:
            log_minutes = (now_utc - last_log).total_seconds() / 60
            logmsg(f"最后日志: {log_minutes:.1f} 分钟前")

        # ── 判断心跳是否超时 ──
        if hb_minutes is not None:
            heartbeat_dead = hb_minutes > heartbeat_threshold
        else:
            # 心跳状态文件不存在（首次启动/损坏）
            # 给宽限期：如果进程和其他信号都正常，不立即判死
            logmsg(f"⚠️ 心跳状态不可用，检查其他信号（宽限期 {GRACE_PERIOD_MINUTES}分钟）")
            session_alive = sess_minutes is not None and sess_minutes < GRACE_PERIOD_MINUTES
            log_alive = log_minutes is not None and log_minutes < GRACE_PERIOD_MINUTES
            if session_alive or log_alive:
                logmsg("✅ 心跳状态不可用但其他信号正常，跳过")
                save_state(state)
                return
            else:
                heartbeat_dead = True

        if not heartbeat_dead:
            # 心跳正常 → 一切 OK
            logmsg("✅ 系统正常")
            save_state(state)
            return

        # ── 心跳超时了，看其他信号 ──
        session_alive = sess_minutes is not None and sess_minutes < SESSION_THRESHOLD_MINUTES
        log_alive = log_minutes is not None and log_minutes < LOG_THRESHOLD_MINUTES

        if session_alive or log_alive:
            # 心跳死了，但系统还活着（有人在聊天或日志在更新）
            # → 只告警，不重启！
            alive_signals = []
            if session_alive:
                alive_signals.append(f"Session {sess_minutes:.1f}分钟前更新")
            if log_alive:
                alive_signals.append(f"日志 {log_minutes:.1f}分钟前更新")

            reason = (
                f"心跳停止 {int(hb_minutes) if hb_minutes else '?'}分钟"
                f"（阈值 {heartbeat_threshold} 分钟），"
                f"但系统仍活跃（{', '.join(alive_signals)}）"
            )
            logmsg(f"⚠️ {reason}")
            send_alert(reason, state)
            return

        # ── 所有信号都超时 → 系统真的死了 ──
        reason_parts = []
        if hb_minutes is not None:
            reason_parts.append(f"心跳停止 {hb_minutes:.0f}分钟")
        else:
            reason_parts.append("心跳状态不可用")
        if sess_minutes is not None:
            reason_parts.append(f"Session 无更新 {sess_minutes:.0f}分钟")
        else:
            reason_parts.append("无 Session 数据")
        if log_minutes is not None:
            reason_parts.append(f"日志无更新 {log_minutes:.0f}分钟")
        else:
            reason_parts.append("无日志数据")

        restart_gateway(" + ".join(reason_parts), state)

    finally:
        release_lock()


if __name__ == "__main__":
    main()
