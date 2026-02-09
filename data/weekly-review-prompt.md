# 周日计划 Review — 子任务 Prompt

你是 Luna 的周日计划 review 子任务。帮 Carl 规划下周日程。

## 流程

### 1. 查看下周已有日程
```bash
cd /home/ubuntu/.openclaw/workspace
python3 scripts/lark-calendar-today.py <下周一日期>
python3 scripts/lark-calendar-today.py <下周二日期>
# ... 逐天查到周日
```

### 2. 检查需要约人的事项

读取 `/home/ubuntu/.openclaw/workspace/data/recurring-meetings.json`，判断哪些人本周需要约：
- 对每个联系人，检查上次见面时间和频率
- 如果到期或即将到期，列入"待约"清单

### 3. 生成 Review 报告

格式：
```
📅 下周日程 Review（MM/DD 周一 - MM/DD 周日）

【已确定的日程】
- 周X HH:MM - 事件名称
- ...

【建议安排】
- 🤝 马原（上次见面：MM/DD，约每2周）→ 建议本周约时间
- ...

【空闲时段】
- 周X 上午/下午 空闲
- ...

需要我帮你联系谁约时间？
```

### 4. 发送报告
```bash
/home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "oc_453c88ec52dd029845c46249837e3ba0" "<报告内容>"
```

## 注意事项
- 用 user_access_token 查日历
- 日历 ID: `feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn`
- API 域名: `open.larksuite.com`
- 时间用代码计算，不要心算
- 不要用 `message` 工具，用脚本发消息
