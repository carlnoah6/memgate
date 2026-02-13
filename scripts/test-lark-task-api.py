#!/usr/bin/env python3
"""Lark 任务 API 测试脚本 v3 - 最终版

测试 Lark Task API v2 的功能：
1. 创建任务（支持各种参数格式）
2. 获取任务详情
3. 更新任务
4. 完成任务
5. 删除任务

API 格式要点：
- due/start 字段格式: {"timestamp": "毫秒时间戳字符串"}
- 更新任务格式: {"task": {...}, "update_fields": ["field1", ...]}
- completed_at: 毫秒时间戳字符串（直接设置即完成任务）

API 文档: https://open.feishu.cn/document/server-docs/task-v2/overview
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lark_common import lark_api, get_tenant_token, get_user_token, LarkAPIError, CARL_OPEN_ID

TASK_API_BASE = "/task/v2"

def to_timestamp_ms(dt: datetime) -> str:
    """将 datetime 转换为毫秒级时间戳字符串"""
    return str(int(dt.timestamp() * 1000))

class TaskAPITester:
    def __init__(self):
        self.tenant_token = get_tenant_token()
        self.user_token = get_user_token()
        self.created_tasks = []
        
    def test_create_task(self, summary: str, **kwargs) -> dict:
        """测试创建任务"""
        print(f"\n📝 创建任务: {summary}")
        
        body = {"summary": summary}
        
        if "description" in kwargs:
            body["description"] = kwargs["description"]
        if "due" in kwargs:
            # due 是对象格式: {"timestamp": "毫秒时间戳字符串"}
            body["due"] = {"timestamp": kwargs["due"]}
        if "start" in kwargs:
            body["start"] = {"timestamp": kwargs["start"]}
        if "is_all_day" in kwargs:
            body["is_all_day"] = kwargs["is_all_day"]
        if "parent_task_guid" in kwargs:
            body["parent_task_guid"] = kwargs["parent_task_guid"]
            
        try:
            result = lark_api(
                "POST", f"{TASK_API_BASE}/tasks",
                body=body, token=self.user_token, token_type="user"
            )
            task = result.get("task", result)
            self.created_tasks.append(task.get("guid"))
            print(f"  ✅ 创建成功: guid={task.get('guid')}")
            print(f"  📋 摘要: {task.get('summary')}")
            if task.get('due'):
                print(f"  ⏰ 截止: {task.get('due')}")
            print(f"  🔗 URL: {task.get('url', 'N/A')}")
            return task
        except LarkAPIError as e:
            print(f"  ❌ 失败: {e}")
            raise
    
    def test_get_task(self, task_guid: str) -> dict:
        """测试获取任务详情"""
        print(f"\n🔍 获取任务: {task_guid}")
        
        try:
            result = lark_api(
                "GET", f"{TASK_API_BASE}/tasks/{task_guid}",
                token=self.user_token, token_type="user"
            )
            task = result.get("task", result)
            print(f"  ✅ 成功")
            print(f"  📋 {task.get('summary')}")
            print(f"  📊 状态: {task.get('status')}")
            if task.get('due'):
                ts = int(task.get('due', {}).get('timestamp', 0))
                due_str = datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                print(f"  ⏰ 截止: {due_str}")
            return task
        except LarkAPIError as e:
            print(f"  ❌ 失败: {e}")
            raise
    
    def test_update_task(self, task_guid: str, **kwargs) -> dict:
        """测试更新任务 - 使用正确的格式"""
        print(f"\n✏️  更新任务: {task_guid}")
        
        task_body = {}
        update_fields = []
        
        field_mapping = {
            "summary": "summary",
            "description": "description", 
            "completed_at": "completed_at",
            "is_all_day": "is_all_day",
            "start": "start",
            "due": "due"
        }
        
        for key, api_field in field_mapping.items():
            if key in kwargs:
                value = kwargs[key]
                # due/start 需要对象格式
                if key in ["due", "start"] and isinstance(value, str):
                    value = {"timestamp": value}
                task_body[api_field] = value
                update_fields.append(api_field)
        
        body = {
            "task": task_body,
            "update_fields": update_fields
        }
                
        try:
            result = lark_api(
                "PATCH", f"{TASK_API_BASE}/tasks/{task_guid}",
                body=body, token=self.user_token, token_type="user"
            )
            task = result.get("task", result)
            print(f"  ✅ 更新成功")
            return task
        except LarkAPIError as e:
            print(f"  ❌ 失败: {e}")
            if e.response:
                print(f"     {json.dumps(e.response, indent=2, ensure_ascii=False)[:200]}")
            raise
    
    def test_complete_task(self, task_guid: str) -> dict:
        """测试完成任务"""
        print(f"\n✅ 完成任务: {task_guid}")
        completed_ts = to_timestamp_ms(datetime.now(timezone.utc))
        return self.test_update_task(task_guid, completed_at=completed_ts)
    
    def test_uncomplete_task(self, task_guid: str) -> dict:
        """测试取消完成 - 使用空字符串或 null"""
        print(f"\n🔄 取消完成: {task_guid}")
        return self.test_update_task(task_guid, completed_at="0")
    
    def test_delete_task(self, task_guid: str) -> bool:
        """测试删除任务"""
        print(f"\n🗑️  删除任务: {task_guid}")
        
        try:
            lark_api(
                "DELETE", f"{TASK_API_BASE}/tasks/{task_guid}",
                token=self.user_token, token_type="user"
            )
            print(f"  ✅ 删除成功")
            if task_guid in self.created_tasks:
                self.created_tasks.remove(task_guid)
            return True
        except LarkAPIError as e:
            print(f"  ❌ 失败: {e}")
            raise
    
    def test_list_tasks(self) -> list:
        """测试列出任务"""
        print(f"\n📋 列出任务")
        
        try:
            result = lark_api(
                "GET", f"{TASK_API_BASE}/tasks?page_size=20",
                token=self.user_token, token_type="user"
            )
            tasks = result.get("tasks", [])
            print(f"  ✅ 共 {len(tasks)} 个任务")
            for task in tasks[:5]:
                icon = "✅" if task.get("completed_at") != "0" else "⬜"
                print(f"     {icon} {task.get('summary', 'N/A')[:25]}")
            return tasks
        except LarkAPIError as e:
            print(f"  ❌ 失败: {e}")
            raise
    
    def test_list_tasklists(self) -> list:
        """测试获取任务清单列表"""
        print(f"\n📚 列出任务清单")
        
        try:
            result = lark_api(
                "GET", f"{TASK_API_BASE}/tasklists",
                token=self.user_token, token_type="user"
            )
            items = result.get("items", [])
            print(f"  ✅ 共 {len(items)} 个清单")
            for item in items:
                print(f"     📁 {item.get('name', 'N/A')}")
            return items
        except LarkAPIError as e:
            print(f"  ❌ 失败: {e}")
            raise
    
    def cleanup(self):
        """清理创建的任务"""
        print(f"\n🧹 清理...")
        for task_guid in list(self.created_tasks):
            try:
                self.test_delete_task(task_guid)
            except Exception as e:
                print(f"  ⚠️  清理失败 {task_guid}: {e}")


def main():
    print("=" * 60)
    print("Lark Task API v2 功能测试")
    print("=" * 60)
    
    tester = TaskAPITester()
    results = []
    task1 = task2 = None
    
    try:
        # 1. 列出任务清单
        try:
            lists = tester.test_list_tasklists()
            results.append(("获取任务清单", True, f"{len(lists)} 个"))
        except Exception as e:
            results.append(("获取任务清单", False, str(e)))
        
        # 2. 列出任务
        try:
            tasks = tester.test_list_tasks()
            results.append(("列出任务", True, f"{len(tasks)} 个"))
        except Exception as e:
            results.append(("列出任务", False, str(e)))
        
        # 3. 创建简单任务
        try:
            task1 = tester.test_create_task(
                "API测试 - 简单任务",
                description="基础功能测试"
            )
            results.append(("创建简单任务", True, task1.get('guid', '')[:8]))
        except Exception as e:
            results.append(("创建简单任务", False, str(e)))
        
        # 4. 创建带截止日期的任务
        try:
            due_ts = to_timestamp_ms(datetime.now() + timedelta(days=7))
            task2 = tester.test_create_task(
                "API测试 - 截止任务",
                description="带截止日期",
                due=due_ts
            )
            results.append(("创建带截止任务", True, f"due={due_ts[:10]}..."))
        except Exception as e:
            results.append(("创建带截止任务", False, str(e)))
        
        # 5. 获取详情
        if task1:
            try:
                tester.test_get_task(task1.get("guid"))
                results.append(("获取任务详情", True, "OK"))
            except Exception as e:
                results.append(("获取任务详情", False, str(e)))
        
        # 6. 更新任务
        if task1:
            try:
                tester.test_update_task(
                    task1.get("guid"),
                    summary="API测试 - 已更新",
                    description="已更新描述"
                )
                results.append(("更新任务", True, "OK"))
            except Exception as e:
                results.append(("更新任务", False, str(e)))
        
        # 7. 完成任务
        if task2:
            try:
                tester.test_complete_task(task2.get("guid"))
                results.append(("完成任务", True, "OK"))
            except Exception as e:
                results.append(("完成任务", False, str(e)))
        
        # 8. 取消完成
        if task2:
            try:
                tester.test_uncomplete_task(task2.get("guid"))
                results.append(("取消完成", True, "OK"))
            except Exception as e:
                results.append(("取消完成", False, str(e)))
        
    finally:
        tester.cleanup()
    
    # 测试报告
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = failed = 0
    for name, success, detail in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}: {detail}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
