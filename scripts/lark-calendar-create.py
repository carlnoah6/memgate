#!/usr/bin/env python3
"""创建 Lark 日历事件

用法:
    python3 scripts/lark-calendar-create.py "标题" "2026-02-09 16:00" "2026-02-09 16:30"
    python3 scripts/lark-calendar-create.py "每周例会" "2026-02-09 10:00" "2026-02-09 11:00" --recurrence "FREQ=WEEKLY;INTERVAL=1"

"""

import json, sys, os, argparse, subprocess
from datetime import datetime, timezone, timedelta

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_user_token, DEFAULT_CALENDAR_ID

SGT = timezone(timedelta(hours=8))
CAL_ID = DEFAULT_CALENDAR_ID

def get_token():
    return get_user_token()

def create_event(summary, start_dt, end_dt, description="", recurrence=""):
    token = get_token()
    url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{CAL_ID}/events"
    
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    
    payload = {
        "summary": summary,
        "description": description,
        "start_time": {"timestamp": str(start_ts), "timezone": "Asia/Singapore"},
        "end_time": {"timestamp": str(end_ts), "timezone": "Asia/Singapore"},
    }
    
    if recurrence:
        payload["recurrence"] = recurrence

    # Call curl
    cmd = [
        "curl", "-s", "-X", "POST", url,
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json; charset=utf-8",
        "-d", json.dumps(payload)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"❌ API Error (Invalid JSON): {result.stdout}")
        return False

    if data.get("code") != 0:
        print(f"❌ API Error: {data.get('msg')} (Code: {data.get('code')})")
        return False
    
    event_id = data.get("data", {}).get("event", {}).get("event_id")
    print(f"✅ Created event: {summary} ({start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}) [ID: {event_id}]")
    return True

def main():
    parser = argparse.ArgumentParser(description="Create Lark calendar event")
    parser.add_argument("summary", help="Event title")
    parser.add_argument("start", help="Start time (YYYY-MM-DD HH:MM)")
    parser.add_argument("end", help="End time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--description", default="", help="Event description")
    parser.add_argument("--recurrence", default="", help="Recurrence rule (e.g. FREQ=WEEKLY)")
    
    args = parser.parse_args()
    
    try:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d %H:%M").replace(tzinfo=SGT)
        end_dt = datetime.strptime(args.end, "%Y-%m-%d %H:%M").replace(tzinfo=SGT)
    except ValueError as e:
        print(f"❌ Date format error: {e}. Use YYYY-MM-DD HH:MM")
        sys.exit(1)
        
    create_event(args.summary, start_dt, end_dt, args.description, args.recurrence)

if __name__ == "__main__":
    main()
