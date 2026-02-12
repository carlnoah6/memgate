import json
import requests
import time
from datetime import datetime, timedelta, timezone

# Load Token
try:
    with open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json') as f:
        data = json.load(f)
        access_token = data['access_token']
except Exception as e:
    print(f"Error loading token: {e}")
    exit(1)

# Time Range (Today and Tomorrow)
# Current time is roughly 2026-02-10 16:15 GMT+8
# We want 2026-02-10 00:00:00 to 2026-02-11 23:59:59

tz_offset = timezone(timedelta(hours=8))
now = datetime.now(tz_offset)
start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
end_of_tomorrow = (start_of_today + timedelta(days=2)) - timedelta(seconds=1)

start_timestamp = str(int(start_of_today.timestamp()))
end_timestamp = str(int(end_of_tomorrow.timestamp()))

calendar_id = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{calendar_id}/events"

headers = {
    "Authorization": f"Bearer {access_token}"
}
params = {
    "start_time": start_timestamp,
    "end_time": end_timestamp
}

print(f"Checking Calendar from {start_of_today} to {end_of_tomorrow}")
try:
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        res_json = response.json()
        if res_json.get("code") == 0:
            events = res_json.get("data", {}).get("items", [])
            print(f"Found {len(events)} events.")
            for event in events:
                summary = event.get("summary", "No Title")
                start = event.get("start_time", {}).get("timestamp")
                # convert timestamp to human readable
                if start:
                    dt = datetime.fromtimestamp(int(start), tz_offset)
                    print(f"- [{dt.strftime('%Y-%m-%d %H:%M')}] {summary}")
                else:
                    print(f"- [No Date] {summary}")
        else:
            print(f"API Error: {res_json}")
    else:
        print(f"HTTP Error: {response.status_code} {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
