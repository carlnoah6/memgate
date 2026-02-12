#!/usr/bin/env python3
"""
获取 Kimi 账户余额和今日消耗数据
用于日报生成

输出格式（JSON）:
{
  "balance_cny": 500.0,
  "last_updated": "2026-02-12T22:00:00+08:00",
  "today_input_tokens": 151129345,
  "today_output_tokens": 0,
  "today_total_tokens": 151129345,
  "today_requests": 1902,
  "rate_per_1m_cny": 12.0,
  "today_cost_cny": 1.81,
  "estimated_days_remaining": 276
}
"""

import json
import datetime
import sys
from pathlib import Path

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
BALANCE_FILE = WORKSPACE / "data" / "kimi-balance.json"

def get_kimi_usage_from_proxy(date_str: str = None):
    """从 API Proxy 获取 Kimi 今日用量"""
    if date_str is None:
        sgt = datetime.timezone(datetime.timedelta(hours=8))
        date_str = datetime.datetime.now(sgt).strftime("%Y-%m-%d")
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"http://localhost:8180/admin/usage/daily?date={date_str}",
            headers={"x-api-key": "sk-admin-luna2026"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            
        days = data.get("days", [])
        if not days:
            return None
            
        day_data = days[0]
        by_model = day_data.get("by_model", {})
        kimi_data = by_model.get("kimi-k2.5", {})
        
        return {
            "input_tokens": kimi_data.get("total", 0),  # Kimi API 只返回 total
            "output_tokens": 0,  # API Proxy 不区分 input/output for Kimi
            "total_tokens": kimi_data.get("total", 0),
            "requests": kimi_data.get("requests", 0)
        }
    except Exception as e:
        print(f"Warning: Failed to fetch usage from API Proxy: {e}", file=sys.stderr)
        return None

def get_kimi_balance():
    """读取本地余额文件"""
    try:
        with open(BALANCE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Failed to read balance file: {e}", file=sys.stderr)
        return None

def calculate_estimated_days(balance, today_cost, rate_per_1m):
    """计算预估剩余可用天数"""
    if today_cost <= 0:
        # 如果今天没有消耗，按平均每日消耗估算
        # 假设平均每天使用 500万 tokens
        avg_daily_cost = (5000000 / 1000000) * rate_per_1m
        if avg_daily_cost > 0:
            return round(balance / avg_daily_cost)
        return 999
    return round(balance / today_cost)

def main():
    # 获取余额数据
    balance_data = get_kimi_balance()
    if not balance_data:
        print(json.dumps({"error": "Failed to read balance data"}, indent=2))
        sys.exit(1)
    
    # 获取今日用量
    usage_data = get_kimi_usage_from_proxy()
    
    # 计算今日消耗（元）
    rate = balance_data.get("rate_per_1m_tokens_cny", 12.0)
    today_tokens = usage_data["total_tokens"] if usage_data else 0
    today_cost = (today_tokens / 1000000) * rate
    
    # 计算预估剩余天数
    balance = balance_data.get("balance_cny", 0)
    estimated_days = calculate_estimated_days(balance, today_cost, rate)
    
    result = {
        "balance_cny": balance,
        "last_updated": balance_data.get("last_updated"),
        "platform": balance_data.get("platform", "Moonshot (Kimi)"),
        "today_input_tokens": usage_data["input_tokens"] if usage_data else 0,
        "today_output_tokens": usage_data["output_tokens"] if usage_data else 0,
        "today_total_tokens": today_tokens,
        "today_requests": usage_data["requests"] if usage_data else 0,
        "rate_per_1m_cny": rate,
        "today_cost_cny": round(today_cost, 2),
        "estimated_days_remaining": estimated_days
    }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
