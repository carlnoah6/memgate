#!/usr/bin/env python3
"""查询 Carl 的 Lark 日历事件，正确处理重复事件和时区。

用法:
    python3 scripts/lark-calendar-today.py                # 今天
    python3 scripts/lark-calendar-today.py 2026-02-08     # 指定日期
    python3 scripts/lark-calendar-today.py tomorrow        # 明天
    python3 scripts/lark-calendar-today.py --range 3       # 今天起3天

输出: 按时间排序的事件列表，只包含指定日期内的事件。
"""

import json, sys, os
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
CAL_ID = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
TOKEN_FILE = "/home/ubuntu/.openclaw/workspace/data/lark-user-token.json"

def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["access_token"]

def parse_date_arg(arg):
    """解析日期参数，返回 (start_date, end_date) 作为 SGT date 对象"""
    now = datetime.now(SGT)
    today = now.date()
    
    if arg is None or arg == "today":
        return today, today
    elif arg == "tomorrow":
        tm = today + timedelta(days=1)
        return tm, tm
    elif arg == "yesterday":
        yd = today - timedelta(days=1)
        return yd, yd
    else:
        try:
            d = datetime.strptime(arg, "%Y-%m-%d").date()
            return d, d
        except ValueError:
            print(f"无法解析日期: {arg}", file=sys.stderr)
            sys.exit(1)

def query_events(start_date, end_date):
    """查询日历事件并正确过滤"""
    import subprocess
    
    # 转换为 Unix 时间戳（SGT 的 00:00 和 24:00）
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=SGT)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=SGT) + timedelta(seconds=1)
    
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    
    token = get_token()
    url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{CAL_ID}/events?start_time={start_ts}&end_time={end_ts}&page_size=50"
    
    result = subprocess.run(
        ["curl", "-s", url, "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True
    )
    
    data = json.loads(result.stdout)
    if data.get("code") != 0:
        print(f"API 错误: {data.get('msg', 'unknown')}", file=sys.stderr)
        sys.exit(1)
    
    items = data.get("data", {}).get("items", [])
    
    # 过滤和处理事件
    events = []
    for item in items:
        summary = item.get("summary", "(无标题)")
        start_time = item.get("start_time", {})
        end_time = item.get("end_time", {})
        recurrence = item.get("recurrence", "")
        status = item.get("status", "")
        
        # 跳过已取消的事件
        if status == "cancelled":
            continue
        
        # 全天事件
        if start_time.get("date"):
            events.append({
                "summary": summary,
                "all_day": True,
                "start_str": "全天",
                "sort_key": "00:00",
                "description": item.get("description", ""),
            })
            continue
        
        # 有时间戳的事件
        if start_time.get("timestamp"):
            st = datetime.fromtimestamp(int(start_time["timestamp"]), tz=SGT)
            et = datetime.fromtimestamp(int(end_time["timestamp"]), tz=SGT)
            
            # ⚠️ 关键修复：检查事件是否真的在查询日期范围内
            # 对于重复事件，Lark API 可能返回原始时间戳而不是展开后的时间
            event_date = st.date()
            
            if recurrence:
                # 重复事件：检查事件是否应该在目标日期出现
                if not event_occurs_on_date(recurrence, st, start_date, end_date):
                    continue
                # 使用目标日期 + 原始时间
                # 找到在范围内的出现日期
                occur_date = find_occurrence_in_range(recurrence, st, start_date, end_date)
                if occur_date:
                    st = st.replace(year=occur_date.year, month=occur_date.month, day=occur_date.day)
                    duration = et - datetime.fromtimestamp(int(start_time["timestamp"]), tz=SGT)
                    et = st + duration
                else:
                    continue
            else:
                # 非重复事件：直接检查日期
                if event_date < start_date or event_date > end_date:
                    continue
            
            events.append({
                "summary": summary,
                "all_day": False,
                "start_str": st.strftime("%H:%M"),
                "end_str": et.strftime("%H:%M"),
                "sort_key": st.strftime("%H:%M"),
                "start_dt": st,
                "end_dt": et,
                "description": item.get("description", ""),
                "recurrence": recurrence,
            })
    
    # 按时间排序
    events.sort(key=lambda e: e["sort_key"])
    return events

def event_occurs_on_date(recurrence, original_start, target_start, target_end):
    """简单检查重复事件是否在目标日期范围内出现"""
    return find_occurrence_in_range(recurrence, original_start, target_start, target_end) is not None

def find_occurrence_in_range(recurrence, original_start, target_start, target_end):
    """找到重复事件在目标日期范围内的出现日期"""
    from datetime import date
    
    # 解析 RRULE
    rules = {}
    for part in recurrence.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            rules[k] = v
    
    freq = rules.get("FREQ", "")
    interval = int(rules.get("INTERVAL", "1"))
    
    # 解析 UNTIL 截止时间
    until_dt = None
    until_str = rules.get("UNTIL", "")
    if until_str:
        try:
            if until_str.endswith("Z"):
                until_dt = datetime.strptime(until_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            else:
                until_dt = datetime.strptime(until_str, "%Y%m%dT%H%M%S").replace(tzinfo=SGT)
        except ValueError:
            pass
    
    def check_until(d):
        """检查日期上的事件是否在 UNTIL 截止时间之前。
        用事件在该日期的实际开始时间（UTC）与 UNTIL 比较。"""
        if not until_dt:
            return True
        # 构造该日期上事件的实际开始时间
        event_dt = datetime(d.year, d.month, d.day, 
                           original_start.hour, original_start.minute, 
                           tzinfo=SGT).astimezone(timezone.utc)
        return event_dt <= until_dt
    
    # WEEKLY 重复
    if freq == "WEEKLY":
        byday = rules.get("BYDAY", "")
        day_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        target_weekdays = [day_map[d] for d in byday.split(",") if d in day_map]
        
        if not target_weekdays:
            target_weekdays = [original_start.weekday()]
        
        # 检查目标范围内的每一天
        current = target_start
        while current <= target_end:
            if current.weekday() in target_weekdays:
                if current >= original_start.date() and check_until(current):
                    # 检查 interval（每 N 周）
                    if interval > 1:
                        weeks_diff = (current - original_start.date()).days // 7
                        if weeks_diff % interval != 0:
                            current += timedelta(days=1)
                            continue
                    return current
            current += timedelta(days=1)
    
    # DAILY 重复
    elif freq == "DAILY":
        orig_date = original_start.date()
        current = target_start
        while current <= target_end:
            diff = (current - orig_date).days
            if diff >= 0 and diff % interval == 0 and check_until(current):
                return current
            current += timedelta(days=1)
    
    # MONTHLY 重复
    elif freq == "MONTHLY":
        bymonthday = rules.get("BYMONTHDAY", str(original_start.day))
        target_day = int(bymonthday)
        current = target_start
        while current <= target_end:
            if current.day == target_day and current >= original_start.date() and check_until(current):
                return current
            current += timedelta(days=1)
    
    # YEARLY 重复
    elif freq == "YEARLY":
        orig_date = original_start.date()
        current = target_start
        while current <= target_end:
            if current.month == orig_date.month and current.day == orig_date.day:
                if current >= orig_date and check_until(current):
                    return current
            current += timedelta(days=1)
    
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="查询 Lark 日历事件")
    parser.add_argument("date", nargs="?", default="today", help="日期 (YYYY-MM-DD/today/tomorrow/yesterday)")
    parser.add_argument("--range", type=int, default=1, help="天数范围")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    
    start_date, end_date = parse_date_arg(args.date)
    if args.range > 1:
        end_date = start_date + timedelta(days=args.range - 1)
    
    events = query_events(start_date, end_date)
    
    if args.json:
        # JSON 输出（供其他脚本使用）
        out = []
        for e in events:
            entry = {"summary": e["summary"], "all_day": e.get("all_day", False)}
            if not e.get("all_day"):
                entry["start"] = e["start_str"]
                entry["end"] = e["end_str"]
            if e.get("recurrence"):
                entry["recurrence"] = e["recurrence"]
            out.append(entry)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        # 人类可读输出
        days = ["周一","周二","周三","周四","周五","周六","周日"]
        if start_date == end_date:
            print(f"📅 {start_date} {days[start_date.weekday()]} 的日程：")
        else:
            print(f"📅 {start_date} ~ {end_date} 的日程：")
        
        if not events:
            print("  （无日程）")
        else:
            for e in events:
                if e.get("all_day"):
                    print(f"  🔵 全天  {e['summary']}")
                else:
                    recur = " 🔁" if e.get("recurrence") else ""
                    print(f"  {e['start_str']}-{e['end_str']}  {e['summary']}{recur}")

if __name__ == "__main__":
    main()
