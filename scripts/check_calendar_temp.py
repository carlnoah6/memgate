import json
import requests
import time
from datetime import datetime, timedelta

# Load Token
with open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json') as f:
    token = json.load(f)['access_token']

calendar_id = 'feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn'
headers = {
    'Authorization': f'Bearer {token}'
}

def get_events(start_ts, end_ts):
    url = f'https://open.larksuite.com/open-apis/calendar/v4/calendars/{calendar_id}/events'
    params = {
        'start_time': str(start_ts),
        'end_time': str(end_ts),
        'page_size': 50
    }
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return []
    return resp.json().get('data', {}).get('items', [])

# 1. Check Today/Tomorrow (Routine)
now = datetime.now()
start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
end_tomorrow = (start_today + timedelta(days=2)).replace(microsecond=0) - timedelta(seconds=1)

print(f"--- Routine Check ({start_today.date()} to {end_tomorrow.date()}) ---")
events_routine = get_events(int(start_today.timestamp()), int(end_tomorrow.timestamp()))
if not events_routine:
    print("No events found for today/tomorrow.")
for e in events_routine:
    print(f"  - {e.get('summary', 'No Title')} ({e.get('start_time', {}).get('timestamp')})")

# 2. Check Specific Dates from Emails
target_dates = [
    ("2026-02-22", "Charlie Cook"),
    ("2026-03-29", "Silence Wang"),
    ("2026-04-15", "Les Misérables")
]

print("\n--- Email Match Check ---")
for date_str, label in target_dates:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    start_dt = dt.replace(hour=0, minute=0, second=0)
    end_dt = dt.replace(hour=23, minute=59, second=59)
    
    events = get_events(int(start_dt.timestamp()), int(end_dt.timestamp()))
    print(f"Checking {date_str} for '{label}': Found {len(events)} events")
    for e in events:
        print(f"  - FOUND: {e.get('summary', 'No Title')} (ID: {e.get('event_id')})")
