#!/usr/bin/env python3
"""
Token 每小时用量统计脚本（多租户版）
读取 API Proxy 用量数据，按小时/租户统计 token 用量，写入 Lark 表格

每小时明细列：日期 | 时段 | 租户/API Key | 输入 Tokens | 输出 Tokens | 总 Tokens | 请求次数
             | Claude 4.6 配额% | Gemini 3 Pro 配额% | Claude Tokens | Gemini Tokens | Kimi Tokens | DeepSeek Tokens
每日汇总列：  日期 | 租户/API Key | 输入 Tokens | 输出 Tokens | 总 Tokens | 请求次数 
             | Claude Tokens | Gemini Tokens | Kimi Tokens | DeepSeek Tokens | 备注

用法:
  python3 token-hourly-stats.py last                  # 统计上一个小时 + 更新当日汇总（默认）
  python3 token-hourly-stats.py backfill 2026-02-08   # 回填指定日期至今
  python3 token-hourly-stats.py summary               # 仅更新每日汇总（从小时表明细求和）
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token

SGT = timezone(timedelta(hours=8))
API_PROXY_URL = "http://localhost:8180"
ADMIN_KEY = "sk-admin-luna2026"

# Lark 表格配置
SPREADSHEET_ID = "FlYsskRe8h1LtDtFYs5lcS1hgBf"
HOURLY_SHEET = "2CAfEk"    # 小时明细表
DAILY_SHEET = "2f25d2"      # 每日汇总表

# 追踪的模型（按实际使用排序）
TRACKED_MODELS = [
    "claude-opus-4-6-thinking",
    "gemini-3-pro-high", 
    "kimi-k2.5",
    "deepseek-chat",
]


def fetch_hourly_usage(date_str):
    """从 API Proxy 获取指定日期的小时级别用量（按租户+模型）"""
    try:
        url = f"{API_PROXY_URL}/admin/usage/hourly?date={date_str}"
        resp = requests.get(url, headers={"x-api-key": ADMIN_KEY}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"WARNING: Failed to fetch hourly usage: {e}")
        return {"hours": []}


def fetch_daily_usage(date_str):
    """从 API Proxy 获取指定日期的日级别用量（按租户）"""
    try:
        url = f"{API_PROXY_URL}/admin/usage/daily?date={date_str}"
        resp = requests.get(url, headers={"x-api-key": ADMIN_KEY}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"WARNING: Failed to fetch daily usage: {e}")
        return {"days": []}


def fetch_quota_data():
    """获取当前配额状态（全局）"""
    try:
        url = f"{API_PROXY_URL}/account-limits?format=json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        result = {}
        for acc in data.get("accounts", []):
            limits = acc.get("limits", {})
            for model_id in TRACKED_MODELS:
                info = limits.get(model_id, {})
                result[model_id] = {
                    "remaining": info.get("remaining", "N/A"),
                    "fraction": info.get("remainingFraction", None),
                }
        return result
    except Exception as e:
        print(f"WARNING: Failed to fetch quota: {e}")
        return {}


def read_sheet(token, sheet_range):
    """读取表格指定范围"""
    url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_ID}/values/{sheet_range}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    data = r.json()
    return data.get("data", {}).get("valueRange", {}).get("values", [])


def update_cells(token, sheet_range, values):
    """更新指定范围的单元格"""
    url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_ID}/values"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"valueRange": {"range": sheet_range, "values": values}}
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code, r.text[:300]


def find_hourly_row(token, date_str, hour_str, tenant):
    """查找指定日期+时段+租户的行号"""
    # 读取 A列(日期)、B列(时段)、C列(租户)
    rows_a = read_sheet(token, f"{HOURLY_SHEET}!A1:A1000")
    rows_b = read_sheet(token, f"{HOURLY_SHEET}!B1:B1000")
    rows_c = read_sheet(token, f"{HOURLY_SHEET}!C1:C1000")
    
    last_data_row = 0
    for i in range(len(rows_a)):
        row_idx = i + 1
        date_val = rows_a[i][0] if rows_a[i] else ""
        hour_val = rows_b[i][0] if i < len(rows_b) and rows_b[i] else ""
        tenant_val = rows_c[i][0] if i < len(rows_c) and rows_c[i] else ""
        
        if date_val and date_val.startswith('20'):
            last_data_row = row_idx
            if date_val == date_str and hour_val == hour_str and tenant_val == tenant:
                return row_idx, True, last_data_row
    
    return None, False, last_data_row


def make_hourly_row(date_str, hour_str, tenant, usage_by_model, quota_data):
    """构造每小时明细行
    
    usage_by_model: {model_id: {"input": N, "output": N, "total": N, "requests": N}}
    """
    # 汇总所有模型的用量
    total_input = sum(m.get("input", 0) for m in usage_by_model.values())
    total_output = sum(m.get("output", 0) for m in usage_by_model.values())
    total_tokens = sum(m.get("total", 0) for m in usage_by_model.values())
    total_requests = sum(m.get("requests", 0) for m in usage_by_model.values())
    
    row = [
        date_str,
        hour_str,
        tenant,
        total_input,
        total_output,
        total_tokens,
        total_requests,
    ]
    
    # 配额列（全局，所有租户共享）
    if quota_data:
        for model_id in TRACKED_MODELS[:2]:  # 只显示前2个模型的配额
            info = quota_data.get(model_id, {})
            remaining = info.get("remaining", "N/A")
            if isinstance(remaining, (int, float)):
                row.append(f"{remaining:.0f}")
            else:
                row.append(str(remaining))
    else:
        row.extend(["", ""])
    
    # 各模型用量列
    for model_id in TRACKED_MODELS:
        model_usage = usage_by_model.get(model_id, {})
        row.append(model_usage.get("total", 0))
    
    return row


def upsert_hourly_row(token, row):
    """写入或更新每小时明细行"""
    date_str = row[0]
    hour_str = row[1]
    tenant = row[2]
    
    row_num, exists, last_data_row = find_hourly_row(token, date_str, hour_str, tenant)
    
    num_cols = len(row)
    col_letter = chr(ord('A') + num_cols - 1)
    
    if exists:
        cell_range = f"{HOURLY_SHEET}!A{row_num}:{col_letter}{row_num}"
        status, text = update_cells(token, cell_range, [row])
        print(f"  Updated hourly row {row_num} ({date_str} {hour_str} {tenant}): {status}")
    else:
        target_row = last_data_row + 1
        cell_range = f"{HOURLY_SHEET}!A{target_row}:{col_letter}{target_row}"
        status, text = update_cells(token, cell_range, [row])
        print(f"  Created hourly row {target_row} ({date_str} {hour_str} {tenant}): {status}")
    
    return exists


def find_daily_row(token, date_str, tenant):
    """查找每日汇总表中指定日期+租户的行号"""
    rows_a = read_sheet(token, f"{DAILY_SHEET}!A1:A500")
    rows_b = read_sheet(token, f"{DAILY_SHEET}!B1:B500")
    
    last_data_row = 0
    for i in range(len(rows_a)):
        row_idx = i + 1
        date_val = rows_a[i][0] if rows_a[i] else ""
        tenant_val = rows_b[i][0] if i < len(rows_b) and rows_b[i] else ""
        
        if date_val and date_val.startswith('20'):
            last_data_row = row_idx
            if date_val == date_str and tenant_val == tenant:
                return row_idx, True, last_data_row
    
    return None, False, last_data_row


def make_daily_row(day_data):
    """构造每日汇总行"""
    # day_data 格式: {
    #   "date": "2026-02-12",
    #   "keys": [{"name": "Jose", "input": N, "output": N, "requests": N}],
    #   "by_model": {"claude-opus": {"total": N, "requests": N}, ...}
    # }
    date_str = day_data.get("date", "")
    
    rows = []
    for key_info in day_data.get("keys", []):
        tenant = key_info.get("name", "unknown")
        inp = key_info.get("input", 0)
        out = key_info.get("output", 0)
        tot = inp + out
        cnt = key_info.get("requests", 0)
        
        row = [date_str, tenant, inp, out, tot, cnt]
        
        # 各模型用量
        by_model = day_data.get("by_model", {})
        for model_id in TRACKED_MODELS:
            model_data = by_model.get(model_id, {})
            row.append(model_data.get("total", 0))
        
        row.append("")  # 备注列
        rows.append((tenant, row))
    
    return rows


def update_daily_summary(token, target_date):
    """更新每日汇总表"""
    date_str = target_date.strftime("%Y-%m-%d")
    print(f"\nUpdating daily summary for {date_str}...")
    
    # 从 API Proxy 获取每日数据
    daily_data = fetch_daily_usage(date_str)
    days = daily_data.get("days", [])
    
    if not days:
        print(f"  No daily data found for {date_str}")
        return
    
    day_data = days[0]  # 通常只有一个日期的数据
    tenant_rows = make_daily_row(day_data)
    
    for tenant, row in tenant_rows:
        row_num, exists, last_data_row = find_daily_row(token, date_str, tenant)
        
        num_cols = len(row)
        col_letter = chr(ord('A') + num_cols - 1)
        
        if exists:
            cell_range = f"{DAILY_SHEET}!A{row_num}:{col_letter}{row_num}"
            status, text = update_cells(token, cell_range, [row])
            print(f"  Updated daily row {row_num} ({tenant}): {status}")
        else:
            target_row = last_data_row + 1
            cell_range = f"{DAILY_SHEET}!A{target_row}:{col_letter}{target_row}"
            status, text = update_cells(token, cell_range, [row])
            print(f"  Created daily row {target_row} ({tenant}): {status}")


def process_hour(target_hour):
    """处理单个小时的统计"""
    date_str = target_hour.strftime("%Y-%m-%d")
    hour_str = target_hour.strftime("%H:00-%H:59")
    
    print(f"\nProcessing {date_str} {hour_str}...")
    
    # 获取配额数据（全局，每小时只需获取一次）
    quota_data = fetch_quota_data()
    
    # 从 API Proxy 获取小时级用量
    hourly_data = fetch_hourly_usage(date_str)
    hours = hourly_data.get("hours", [])
    
    target_key = target_hour.strftime("%Y-%m-%d %H:00")
    
    token = get_tenant_token()
    if not token:
        print("ERROR: Failed to get tenant token")
        return False
    
    found = False
    for hour_data in hours:
        if hour_data.get("hour") == target_key:
            found = True
            # 按租户分组统计
            by_tenant = hour_data.get("by_tenant", {})
            
            if not by_tenant:
                print(f"  No tenant data found for {target_key}")
                return False
            
            for tenant, tenant_data in by_tenant.items():
                usage_by_model = tenant_data.get("by_model", {})
                row = make_hourly_row(date_str, hour_str, tenant, usage_by_model, quota_data)
                upsert_hourly_row(token, row)
            
            break
    
    if not found:
        print(f"  No data found for {target_key}")
        return False
    
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "last"
    
    if mode == "last":
        # 统计上一个小时
        now = datetime.now(SGT)
        target_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        
        success = process_hour(target_hour)
        
        if success:
            # 更新当天的每日汇总
            token = get_tenant_token()
            if token:
                update_daily_summary(token, now)
    
    elif mode == "backfill":
        # 回填模式
        start_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now(SGT).strftime("%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=SGT, hour=0)
        now = datetime.now(SGT)
        
        print(f"Backfilling from {start_date} to {now.strftime('%Y-%m-%d')}...")
        
        current = start_dt
        while current < now:
            process_hour(current)
            current += timedelta(hours=1)
        
        # 更新涉及的所有日期的汇总
        token = get_tenant_token()
        if token:
            dates_seen = set()
            current = start_dt
            while current < now:
                dates_seen.add(current.strftime("%Y-%m-%d"))
                current += timedelta(hours=1)
            dates_seen.add(now.strftime("%Y-%m-%d"))
            
            for date_str in sorted(dates_seen):
                day_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=SGT, hour=12)
                update_daily_summary(token, day_dt)
    
    elif mode == "summary":
        # 仅更新每日汇总
        now = datetime.now(SGT)
        token = get_tenant_token()
        if token:
            update_daily_summary(token, now)
    
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: token-hourly-stats.py [last|backfill YYYY-MM-DD|summary]")


if __name__ == "__main__":
    main()
