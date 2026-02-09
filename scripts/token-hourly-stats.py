#!/usr/bin/env python3
"""
Token 每小时用量统计脚本
读取 OpenClaw session jsonl 文件，按小时统计 token 用量，写入 Lark 表格
同时记录各模型剩余配额（从 API 代理 /account-limits 获取）

每小时明细列：日期 | 时段 (SGT) | 输入 Tokens | 输出 Tokens | 总 Tokens | 请求次数 | 会话来源
             | Claude 4.6 配额% | Gemini 3 Pro 配额% | Claude 4.5 配额% | Sonnet 4.5 配额%
每日汇总列：  日期 | 输入 Tokens | 输出 Tokens | 总 Tokens | 请求次数 | 主会话 | 子任务 | 备注

配额快照同时保存到本地 JSON（供日报使用）

用法:
  python3 token-hourly-stats.py last                  # 统计上一个小时 + 更新当日汇总（默认）
  python3 token-hourly-stats.py backfill 2026-02-08   # 回填指定日期至今
"""

import json, os, glob, sys, requests
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
SESSION_DIR = "/home/ubuntu/.openclaw/agents/main/sessions/"
SUBAGENT_DIR = "/home/ubuntu/.openclaw/subagents/"
SPREADSHEET_ID = "FlYsskRe8h1LtDtFYs5lcS1hgBf"
HOURLY_SHEET = "2CAfEk"
DAILY_SHEET = "2f25d2"
QUOTA_SNAPSHOT_DIR = "/home/ubuntu/.openclaw/workspace/data/quota-snapshots/"

APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"

ACCOUNT_LIMITS_URL = "http://localhost:8080/account-limits?includeHistory=true"

# 需要追踪的模型（只追踪实际使用的）
TRACKED_MODELS = [
    "claude-opus-4-6-thinking",
    "gemini-3-pro-high",
]


def get_tenant_token():
    r = requests.post("https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal", json={
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    })
    return r.json().get("tenant_access_token")


def scan_sessions(dirs, target_start, target_end):
    """扫描指定目录列表中时间范围内的 token 用量"""
    total_input = 0
    total_output = 0
    request_count = 0

    for session_dir in dirs:
        if not os.path.isdir(session_dir):
            continue
        for fpath in glob.glob(os.path.join(session_dir, "**", "*.jsonl"), recursive=True):
            try:
                with open(fpath) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                        except:
                            continue

                        msg = d.get("message", {})
                        if not isinstance(msg, dict):
                            continue
                        if msg.get("role") != "assistant":
                            continue

                        ts = d.get("timestamp") or msg.get("timestamp")
                        if not ts:
                            continue

                        try:
                            if isinstance(ts, (int, float)):
                                ts_s = ts / 1000 if ts > 1e12 else ts
                                dt = datetime.fromtimestamp(ts_s, tz=SGT)
                            else:
                                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(SGT)
                        except:
                            continue

                        if dt < target_start or dt >= target_end:
                            continue

                        usage = msg.get("usage", {})
                        if not usage:
                            continue

                        total_input += usage.get("input", 0) or 0
                        total_output += usage.get("output", 0) or 0
                        request_count += 1
            except Exception:
                pass

    total_tokens = total_input + total_output
    return total_input, total_output, total_tokens, request_count


def scan_hour(target_hour_start, target_hour_end):
    """扫描指定时间范围内的 token 用量（包含主会话 + 子任务）"""
    return scan_sessions([SESSION_DIR, SUBAGENT_DIR], target_hour_start, target_hour_end)


def fetch_account_limits():
    """从 API 代理获取各模型剩余配额"""
    try:
        r = requests.get(ACCOUNT_LIMITS_URL, timeout=10)
        r.raise_for_status()
        data = r.json()

        result = {}
        for acc in data.get("accounts", []):
            limits = acc.get("limits", {})
            for model_id in TRACKED_MODELS:
                info = limits.get(model_id, {})
                result[model_id] = {
                    "remaining": info.get("remaining", "N/A"),
                    "fraction": info.get("remainingFraction", None),
                    "resetTime": info.get("resetTime", None),
                }

            # 也提取 rate limit 状态
            rate_limits = acc.get("modelRateLimits", {})
            for model_id in TRACKED_MODELS:
                rl = rate_limits.get(model_id, {})
                if model_id in result:
                    result[model_id]["isRateLimited"] = rl.get("isRateLimited", False)

            # 提取 history（当前小时请求数）
            history = data.get("history", {})
            result["_history"] = history
            result["_subscription"] = acc.get("subscription", {})

        return result
    except Exception as e:
        print(f"WARNING: Failed to fetch account-limits: {e}")
        return {}


def save_quota_snapshot(quota_data, timestamp):
    """保存配额快照到本地 JSON（供日报使用）"""
    os.makedirs(QUOTA_SNAPSHOT_DIR, exist_ok=True)

    date_str = timestamp.strftime("%Y-%m-%d")
    hour_str = timestamp.strftime("%H")
    snapshot_file = os.path.join(QUOTA_SNAPSHOT_DIR, f"{date_str}.json")

    # 读取已有数据
    existing = {}
    if os.path.exists(snapshot_file):
        try:
            with open(snapshot_file) as f:
                existing = json.load(f)
        except:
            existing = {}

    # 添加当前小时的快照
    hour_key = f"{hour_str}:00"
    snapshot = {
        "timestamp": timestamp.isoformat(),
    }
    for model_id in TRACKED_MODELS:
        info = quota_data.get(model_id, {})
        snapshot[model_id] = {
            "remaining": info.get("remaining", "N/A"),
            "fraction": info.get("fraction"),
            "isRateLimited": info.get("isRateLimited", False),
        }

    existing[hour_key] = snapshot

    with open(snapshot_file, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Saved quota snapshot for {date_str} {hour_key}")


def scan_day(target_date):
    """扫描指定日期全天的 token 用量（SGT 00:00 到 23:59）"""
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return scan_hour(day_start, day_end)


def append_to_sheet(token, sheet_range, rows):
    """批量追加行到表格"""
    url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_ID}/values_append"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"valueRange": {"range": sheet_range, "values": rows}}
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code, r.text[:300]


def update_cells(token, sheet_range, values):
    """更新指定范围的单元格"""
    url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_ID}/values"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"valueRange": {"range": sheet_range, "values": values}}
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code, r.text[:300]


def read_sheet(token, sheet_range):
    """读取表格指定范围"""
    url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_ID}/values/{sheet_range}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    data = r.json()
    return data.get("data", {}).get("valueRange", {}).get("values", [])


def find_daily_row(token, target_date_str):
    """在每日汇总表中查找指定日期的行号，返回 (row_number, exists)"""
    rows = read_sheet(token, f"{DAILY_SHEET}!A1:A50")
    for i, row in enumerate(rows, 1):
        if row and len(row) > 0 and row[0] == target_date_str:
            return i, True
    # 找到第一个空行
    for i, row in enumerate(rows, 1):
        if not row or not row[0]:
            return i, False
    # 所有行都有数据，追加到末尾
    return len(rows) + 1, False


def update_daily_summary(token, target_date):
    """更新每日汇总表中指定日期的行"""
    target_date_str = target_date.strftime("%Y-%m-%d")
    inp, out, tot, cnt = scan_day(target_date)

    print(f"Daily {target_date_str}: input={inp} output={out} total={tot} requests={cnt}")

    row_num, exists = find_daily_row(token, target_date_str)
    # 日期 | 输入 | 输出 | 总 | 请求次数 | 主会话 | 子任务 | 备注
    row_data = [[target_date_str, inp, out, tot, cnt, cnt, 0, ""]]

    cell_range = f"{DAILY_SHEET}!A{row_num}:H{row_num}"
    status, text = update_cells(token, cell_range, row_data)
    action = "Updated" if exists else "Created"
    print(f"{action} daily row {row_num}: {status} {text}")


def make_hourly_row(dt, inp, out, tot, cnt, quota_data=None):
    """构造每小时明细行（含配额信息）"""
    row = [
        dt.strftime("%Y-%m-%d"),
        dt.strftime("%H:00-%H:59"),
        inp,
        out,
        tot,
        cnt,
        "main" if cnt > 0 else "-"
    ]
    # 追加配额列：Claude 4.6 | Gemini 3 Pro | Claude 4.5 | Sonnet 4.5
    if quota_data:
        for model_id in TRACKED_MODELS:
            info = quota_data.get(model_id, {})
            remaining = info.get("remaining", "N/A")
            row.append(remaining)
    else:
        row.extend([""] * len(TRACKED_MODELS))
    return row


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "last"

    if mode == "backfill":
        start_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now(SGT).strftime("%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=SGT, hour=0)
        now = datetime.now(SGT)

        rows = []
        current = start_dt
        while current < now:
            hour_end = current + timedelta(hours=1)
            inp, out, tot, cnt = scan_hour(current, hour_end)
            hour_label = current.strftime("%Y-%m-%d %H:00")
            print(f"{hour_label}: input={inp} output={out} total={tot} requests={cnt}")
            if cnt > 0:
                rows.append(make_hourly_row(current, inp, out, tot, cnt))
            current = hour_end

        if rows:
            token = get_tenant_token()
            if not token:
                print("ERROR: Failed to get tenant token")
                sys.exit(1)
            status, text = append_to_sheet(token, HOURLY_SHEET, rows)
            print(f"Appended {len(rows)} hourly rows: {status} {text}")

            # 同时更新每日汇总
            update_daily_summary(token, now)
        else:
            print("No hourly data to append")

    elif mode == "last":
        now = datetime.now(SGT)
        hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hour_end = hour_start + timedelta(hours=1)

        inp, out, tot, cnt = scan_hour(hour_start, hour_end)
        hour_label = hour_start.strftime("%Y-%m-%d %H:00")
        print(f"{hour_label}: input={inp} output={out} total={tot} requests={cnt}")

        # 获取配额数据
        quota_data = fetch_account_limits()
        if quota_data:
            for model_id in TRACKED_MODELS:
                info = quota_data.get(model_id, {})
                rl = "⚠️ RATE LIMITED" if info.get("isRateLimited") else ""
                print(f"  {model_id}: {info.get('remaining', 'N/A')} {rl}")

            # 保存配额快照到本地
            save_quota_snapshot(quota_data, now)

        token = get_tenant_token()
        if not token:
            print("ERROR: Failed to get tenant token")
            sys.exit(1)

        # 写入每小时明细（总是写入，即使没有请求也记录配额状态）
        row = make_hourly_row(hour_start, inp, out, tot, cnt, quota_data)
        status, text = append_to_sheet(token, HOURLY_SHEET, [row])
        print(f"Appended hourly (with quota): {status} {text}")

        # 更新当天的每日汇总
        update_daily_summary(token, now)

    elif mode == "quota":
        # 仅获取并打印当前配额（调试用）
        quota_data = fetch_account_limits()
        if quota_data:
            print(json.dumps({k: v for k, v in quota_data.items() if not k.startswith("_")}, indent=2))
        else:
            print("Failed to fetch quota data")


if __name__ == "__main__":
    main()
