#!/bin/bash
# Log Google API quota snapshot to JSONL file
LOG_DIR="/home/ubuntu/.openclaw/workspace/data"
LOG_FILE="$LOG_DIR/quota-snapshots.jsonl"
mkdir -p "$LOG_DIR"

QUOTA_JSON=$(curl -s 'http://localhost:8080/account-limits?format=json' 2>/dev/null)
if [ -z "$QUOTA_JSON" ]; then
  exit 0
fi

# Extract key quota values and append as one JSONL line
python3 -c "
import json, sys
from datetime import datetime, timezone, timedelta

sgt = timezone(timedelta(hours=8))
now = datetime.now(sgt).isoformat()

try:
    data = json.loads('''$QUOTA_JSON''')
    account = data['accounts'][0]
    limits = account.get('limits', {})
    
    snapshot = {
        'timestamp': now,
        'date': datetime.now(sgt).strftime('%Y-%m-%d'),
        'hour': datetime.now(sgt).strftime('%H:%M'),
        'quotas': {}
    }
    
    for model, info in limits.items():
        snapshot['quotas'][model] = {
            'remaining': info.get('remainingFraction', 0),
            'resetTime': info.get('resetTime', '')
        }
    
    print(json.dumps(snapshot))
except Exception as e:
    sys.exit(0)
" >> "$LOG_FILE"
