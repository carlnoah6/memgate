## 任务管理
- 任务 ID: {task_id}
- 完成后运行: python3 /home/ubuntu/.openclaw/workspace/scripts/task-manager.py complete {task_id} "结果摘要"
- 失败时运行: python3 /home/ubuntu/.openclaw/workspace/scripts/task-manager.py fail {task_id} "错误原因"
- 不要用 message 工具发消息
- ⚠️ complete/fail 会自动：①发结果到任务群 ②发结果到源 chat ③解散群聊。你不需要手动做这些。

## 任务群聊（如有）
- 任务群 chat_id: {task_chat_id}
- 发进度更新到群聊（重要节点时发，不要每步都发）:
  ```bash
  bash /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "{task_chat_id}" "🔄 进度：XXX"
  ```
- 进度消息要有实质内容，告诉 Carl 你在做什么、发现了什么、下一步是什么
