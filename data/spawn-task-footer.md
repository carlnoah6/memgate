## 任务管理
- 任务 ID: {task_id}
- 完成后运行: python3 /home/ubuntu/.openclaw/workspace/scripts/task-manager.py complete {task_id} "结果摘要"
- 失败时运行: python3 /home/ubuntu/.openclaw/workspace/scripts/task-manager.py fail {task_id} "错误原因"
- 结果发送到: /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "{source_chat_id}" "✅ {task_id} 完成：..."
- 不要用 message 工具发消息
