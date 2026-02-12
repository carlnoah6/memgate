import json
import requests
import time
from datetime import datetime, timedelta

# Load Token
try:
    with open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json', 'r') as f:
        token_data = json.load(f)
        access_token = token_data['access_token']
except Exception as e:
    print(f"Error loading token: {e}")
    exit(1)

# Config
calendar_id = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{calendar_id}/events"

# Time Range: Now to Tomorrow End
now = datetime.now()
start_time = int(now.timestamp())
end_time_dt = now + timedelta(days=2)
end_time_dt = end_time_dt.replace(hour=23, minute=59, second=59)
end_time = int(end_time_dt.timestamp())

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json; charset=utf-8"
}

params = {
    "start_time": str(start_time),
    "end_time": str(end_time),
    "page_size": 50
}

try:
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    
    if data.get("code") != 0:
        print(f"Error fetching calendar: {data}")
    else:
        events = data.get("data", {}).get("items", [])
        if not events:
            print("No upcoming events found for today and tomorrow.")
        else:
            print(f"Found {len(events)} events:")
            for event in events:
                summary = event.get("summary", "No Title")
                start = event.get("start_time", {}).get("timestamp")
                # timestamp is string in seconds or ms? Lark usually seconds string
                if start:
                    dt = datetime.fromtimestamp(int(start))
                    print(f"- [{dt}] {summary}")
                else:
                    print(f"- [No Time] {summary}")

except Exception as e:
    print(f"Request failed: {e}")
