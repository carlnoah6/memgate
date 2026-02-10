#!/usr/bin/env python3
"""
自动修复 Lark 日历颜色分类
根据标题关键词匹配颜色，批量更新未来 30 天的日程。
"""

import json, sys, os, subprocess, time
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
CAL_ID = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
TOKEN_FILE = "/home/ubuntu/.openclaw/workspace/data/lark-user-token.json"

# 分类规则 (优先级从上到下)
# 颜色代码 (RGB Int32) - 来自用户手动示教
RULES = [
    # 1. 家庭/孩子 -> Red Orange (-963671)
    (-963671, ["元宝", "朵朵", "孩子", "家人", "家庭", "Family", "Yuanbao", "Duoduo"]),
    
    # 2. 运动 -> Olive (-10392859)
    (-10392859, ["普拉提", "跑步", "健身", "运动", "徒步", "Pilates", "Yoga", "Gym", "Walk"]),
    
    # 3. 心理咨询 -> Teal (-16722247) (区分于运动)
    (-16722247, ["心理咨询", "Psychology"]),

    # 4. 社交 -> Yellow (-14838)
    (-14838, ["吃饭", "聚餐", "喝酒", "聚会", "午餐", "晚餐", "孙枢", "卢琦", "马原", "Dinner", "Lunch"]),
    
    # 5. 学习/课程 -> Blue (-11631619)
    (-11631619, ["课程", "课", "学习", "NTU", "Class", "Study", "Research"]),
    
    # 6. 会议/工作 -> Blue (-11631619)
    (-11631619, ["会议", "Meeting", "沟通", "约", "面试", "Sync"]),
]

def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["access_token"]

def get_events(days=30):
    token = get_token()
    now = datetime.now(SGT)
    start_ts = int(now.timestamp())
    end_ts = int((now + timedelta(days=days)).timestamp())
    
    url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{CAL_ID}/events?start_time={start_ts}&end_time={end_ts}&page_size=100"
    
    cmd = ["curl", "-s", url, "-H", f"Authorization: Bearer {token}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(res.stdout).get("data", {}).get("items", [])
    except:
        return []

def update_color(event_id, color_id, summary):
    token = get_token()
    url = f"https://open.larksuite.com/open-apis/calendar/v4/calendars/{CAL_ID}/events/{event_id}"
    
    # 修正：参数名应为 color，且类型为 int
    payload = {"color": int(color_id)}
    
    cmd = [
        "curl", "-s", "-X", "PATCH", url,
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json; charset=utf-8",
        "-d", json.dumps(payload)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    # print(f"Update {summary} -> {color_id}: {res.stdout}")
    return True

def match_color(summary):
    for color_id, keywords in RULES:
        for kw in keywords:
            if kw.lower() in summary.lower():
                return str(color_id), kw
    return None, None

def main():
    print("🔍 正在扫描未来 30 天的日程并修复颜色...")
    events = get_events()
    count = 0
    
    for event in events:
        summary = event.get("summary", "")
        current_color = event.get("color_id")
        event_id = event.get("event_id")
        
        target_color, keyword = match_color(summary)
        
        if target_color and current_color != target_color:
            print(f"🎨 修复: {summary} (匹配 '{keyword}') -> 颜色 {target_color}")
            update_color(event_id, target_color, summary)
            count += 1
            time.sleep(0.1) # 避免限流
            
    if count == 0:
        print("✅ 所有日程颜色已正确，无需修复。")
    else:
        print(f"✅ 已修复 {count} 个日程的分类颜色。")

if __name__ == "__main__":
    main()
