#!/usr/bin/env python3
"""跳过循环日程的指定日期范围。

用法:
    python3 scripts/skip-recurring-dates.py <event_id_0> <skip_start> <skip_end>

示例:
    # 跳过心理咨询 2/13-2/19
    python3 scripts/skip-recurring-dates.py a995c8ef-..._0 2026-02-13 2026-02-19

原理:
    Lark API 不支持直接删除循环事件的虚拟实例。
    本脚本通过 UNTIL + 重建方式实现跳过特定日期范围：
    1. 给原事件加 UNTIL（在 skip_start 前一天截止）
    2. 创建新循环事件（从 skip_end 后的第一个匹配日开始）

⚠️ 测试确认 (2026-02-10):
    - Events LIST API 永远返回 master_0，不返回实例 ID
    - Instances API 返回的 _{timestamp} ID 不能 DELETE (404)
    - UNTIL + 重建是唯一可靠方案
"""

import json, sys, os, requests
from datetime import datetime, timezone, timedelta

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_user_token, DEFAULT_CALENDAR_ID

SGT = timezone(timedelta(hours=8))
CAL_ID = DEFAULT_CALENDAR_ID

def get_token():
    return get_user_token()

def get_event(token, event_id):
    url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{CAL_ID}/events/{event_id}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    return r.json().get("data", {}).get("event", {})

def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    
    event_id = sys.argv[1]
    skip_start = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    skip_end = datetime.strptime(sys.argv[3], "%Y-%m-%d").date()
    
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{CAL_ID}/events"
    
    # 1. 获取原事件信息
    ev = get_event(token, event_id)
    if not ev:
        print(f"❌ 事件不存在: {event_id}")
        sys.exit(1)
    
    recurrence = ev.get("recurrence", "")
    if not recurrence:
        print(f"❌ 不是循环事件: {ev.get('summary', '')}")
        sys.exit(1)
    
    start_ts = int(ev["start_time"]["timestamp"])
    end_ts = int(ev["end_time"]["timestamp"])
    duration = end_ts - start_ts
    tz = ev["start_time"].get("timezone", "Asia/Singapore")
    summary = ev.get("summary", "")
    color = ev.get("color", -1)
    desc = ev.get("description", "")
    location = ev.get("location", {})
    
    orig_dt = datetime.fromtimestamp(start_ts, tz=SGT)
    
    print(f"📅 {summary}")
    print(f"   循环规则: {recurrence}")
    print(f"   原始时间: {orig_dt.strftime('%Y-%m-%d %a %H:%M')}")
    print(f"   跳过范围: {skip_start} ~ {skip_end}")
    
    # 2. 设置 UNTIL（skip_start 前一天的 23:59 UTC）
    until_date = skip_start - timedelta(days=1)
    until_utc = datetime(until_date.year, until_date.month, until_date.day, 23, 59, 59,
                         tzinfo=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new_recurrence = f"{recurrence};UNTIL={until_utc}"
    
    r1 = requests.patch(f"{base_url}/{event_id}", headers=headers,
                        json={"recurrence": new_recurrence})
    if r1.json().get("code") != 0:
        print(f"❌ UNTIL 设置失败: {r1.json().get('msg', '')}")
        sys.exit(1)
    print(f"✅ UNTIL 设置为 {until_date}")
    
    # 3. 找到 skip_end 后的第一个匹配日期
    # 解析 BYDAY
    rules = {}
    for part in recurrence.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            rules[k] = v
    
    freq = rules.get("FREQ", "WEEKLY")
    target_weekday = orig_dt.weekday()
    
    resume_date = skip_end + timedelta(days=1)
    while resume_date.weekday() != target_weekday:
        resume_date += timedelta(days=1)
    
    new_start = datetime(resume_date.year, resume_date.month, resume_date.day,
                         orig_dt.hour, orig_dt.minute, tzinfo=SGT)
    new_end_ts = int(new_start.timestamp()) + duration
    
    # 4. 创建新循环事件
    new_event = {
        "summary": summary,
        "description": desc,
        "start_time": {"timestamp": str(int(new_start.timestamp())), "timezone": tz},
        "end_time": {"timestamp": str(new_end_ts), "timezone": tz},
        "recurrence": recurrence,  # 原始规则（无 UNTIL）
        "color": color,
    }
    if location.get("name"):
        new_event["location"] = location
    
    r2 = requests.post(base_url, headers=headers, json=new_event)
    if r2.json().get("code") != 0:
        print(f"❌ 新事件创建失败: {r2.json().get('msg', '')}")
        sys.exit(1)
    
    new_id = r2.json()["data"]["event"]["event_id"]
    print(f"✅ 新循环从 {resume_date} 恢复 (id: {new_id[:30]}...)")
    print(f"🎉 完成！{skip_start} ~ {skip_end} 期间无 {summary}")

if __name__ == "__main__":
    main()
