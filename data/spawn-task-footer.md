## 任务管理
- 任务 ID: {task_id}
- 完成后运行: python3 /home/ubuntu/.openclaw/workspace/scripts/task-manager.py complete {task_id} "结果摘要"
- 失败时运行: python3 /home/ubuntu/.openclaw/workspace/scripts/task-manager.py fail {task_id} "错误原因"
- 不要用 message 工具发消息

## 任务群聊（如有）
- 任务群 chat_id: {task_chat_id}
- 发进度更新到群聊（重要节点时发，不要每步都发）:
  ```bash
  python3 -c "
  import json, urllib.request
  token = json.loads(urllib.request.urlopen(urllib.request.Request(
    'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal',
    data=json.dumps({'app_id':'cli_a90c3a6163785ed2','app_secret':'***LARK_SECRET_REMOVED***'}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')).read())['tenant_access_token']
  urllib.request.urlopen(urllib.request.Request(
    'https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id',
    data=json.dumps({'receive_id':'{task_chat_id}','msg_type':'text','content':json.dumps({'text':'进度消息'})}).encode(),
    headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'}, method='POST'))
  "
  ```
- 结果也发到源 chat: /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "{source_chat_id}" "✅ {task_id} 完成：..."
