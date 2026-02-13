#!/usr/bin/env python3
"""Lark 任务 API 测试脚本 v2 - 修复参数格式

测试 Lark Task API v2 的功能：
1. 创建任务（支持各种参数格式）
2. 获取任务详情
3. 更新任务
4. 完成任务
5. 删除任务

API 文档: https://open.feishu.cn/document/server-docs/task-v2/overview

重要发现：
- due 字段需要是毫秒级时间戳（整数），不是 ISO 8601 字符串
- completed_at 同样需要毫秒级时间戳
- 评论 API 可能是 /task/v2/tasks/{guid}/comments 或其他路径
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from lark_common import lark_api, get_tenant_token, get_user_token, LarkAPIError

# API 基础路径
TASK_API_BASE = "/task/v2"

def to_timestamp_ms(dt: datetime) -> int:
    """将 datetime 转换为毫秒级时间戳"""
    return int(dt.timestamp() * 1000)

class TaskAPITester:
    def __init__(self):
        self.tenant_token = get_tenant_token()
        self.user_token = get_user_token()
        self.created_tasks = []  # 记录创建的任务用于清理
        
    def test_create_task(self, summary: str, **kwargs) -> dict:
        """测试创建任务"""
        print(f"\n📝 测试创建任务: {summary}")
        
        body = {
            "summary": summary,
        }
        
        # 可选参数
        if "description" in kwargs:
            body["description"] = kwargs["description"]
        if "due" in kwargs:
            body["due"] = kwargs["due"]  # 毫秒级时间戳
        if "assignee" in kwargs:
            body["assignee"] = kwargs["assignee"]
        if "followers" in kwargs:
            body["followers"] = kwargs["followers"]
        if "start" in kwargs:
            body["start"] = kwargs["start"]  # 毫秒级时间戳
        if "is_all_day" in kwargs:
            body["is_all_day"] = kwargs["is_all_day"]
        if "parent_task_guid" in kwargs:
            body["parent_task_guid"] = kwargs["parent_task_guid"]
            
        try:
            result = lark_api(
                "POST",
                f"{TASK_API_BASE}/tasks",
                body=body,
                token=self.user_token,
                token_type="user"
            )
            task = result.get("task", result)
            self.created_tasks.append(task.get("guid"))
            print(f"  ✅ 创建成功: guid={task.get('guid')}")
            print(f"  📋 任务摘要: {task.get('summary')}")
            creator = task.get('creator', {})
            if isinstance(creator, dict):
                print(f"  👤 创建者: {creator.get('name', 'N/A')} ({creator.get('open_id', 'N/A')})")
            else:
                print(f"  👤 创建者: {creator}")
            return task
        except LarkAPIError as e:
            print(f"  ❌ 创建失败: {e}")
            if e.response:
                print(f"     响应: {json.dumps(e.response, indent=2, ensure_ascii=False)}")
            raise
    
    def test_get_task(self, task_guid: str) -> dict:
        """测试获取任务详情"""
        print(f"\n🔍 测试获取任务详情: {task_guid}")
        
        try:
            result = lark_api(
                "GET",
                f"{TASK_API_BASE}/tasks/{task_guid}",
                token=self.user_token,
                token_type="user"
            )
            task = result.get("task", result)
            print(f"  ✅ 获取成功")
            print(f"  📋 摘要: {task.get('summary')}")
            print(f"  📊 状态: {task.get('status')}")
            if task.get('due'):
                due_ts = task.get('due')
                due_dt = datetime.fromtimestamp(due_ts / 1000, tz=timezone.utc)
                print(f"  ⏰ 截止日期: {due_dt} (ts={due_ts})")
            return task
        except LarkAPIError as e:
            print(f"  ❌ 获取失败: {e}")
            raise
    
    def test_update_task(self, task_guid: str, **kwargs) -> dict:
        """测试更新任务"""
        print(f"\n✏️  测试更新任务: {task_guid}")
        
        body = {}
        for key in ["summary", "description", "due", "assignee", "start", "is_all_day", "completed_at"]:
            if key in kwargs:
                body[key] = kwargs[key]
                
        try:
            result = lark_api(
                "PATCH",
                f"{TASK_API_BASE}/tasks/{task_guid}",
                body=body,
                token=self.user_token,
                token_type="user"
            )
            task = result.get("task", result)
            print(f"  ✅ 更新成功")
            return task
        except LarkAPIError as e:
            print(f"  ❌ 更新失败: {e}")
            if e.response:
                print(f"     响应: {json.dumps(e.response, indent=2, ensure_ascii=False)}")
            raise
    
    def test_complete_task(self, task_guid: str) -> dict:
        """测试完成任务 - 使用毫秒时间戳"""
        print(f"\n✅ 测试完成任务: {task_guid}")
        
        # 使用毫秒级时间戳
        completed_ts = to_timestamp_ms(datetime.now(timezone.utc))
        return self.test_update_task(task_guid, completed_at=completed_ts)
    
    def test_uncomplete_task(self, task_guid: str) -> dict:
        """测试取消完成任务 - 将 completed_at 设为 null"""
        print(f"\n🔄 测试取消完成任务: {task_guid}")
        return self.test_update_task(task_guid, completed_at=None)
    
    def test_delete_task(self, task_guid: str) -> bool:
        """测试删除任务"""
        print(f"\n🗑️  测试删除任务: {task_guid}")
        
        try:
            lark_api(
                "DELETE",
                f"{TASK_API_BASE}/tasks/{task_guid}",
                token=self.user_token,
                token_type="user"
            )
            print(f"  ✅ 删除成功")
            if task_guid in self.created_tasks:
                self.created_tasks.remove(task_guid)
            return True
        except LarkAPIError as e:
            print(f"  ❌ 删除失败: {e}")
            raise
    
    def test_list_tasks(self, **filters) -> list:
        """测试列出任务 - 支持筛选"""
        print(f"\n📋 测试列出任务")
        
        # 构建查询参数
        params = []
        if filters.get('status'):
            params.append(f"status={filters['status']}")
        if filters.get('page_size'):
            params.append(f"page_size={filters['page_size']}")
        else:
            params.append("page_size=20")
            
        query = "?" + "&".join(params) if params else ""
        
        try:
            result = lark_api(
                "GET",
                f"{TASK_API_BASE}/tasks{query}",
                token=self.user_token,
                token_type="user"
            )
            tasks = result.get("tasks", [])
            print(f"  ✅ 获取成功，共 {len(tasks)} 个任务")
            for task in tasks[:5]:  # 只显示前5个
                status_icon = "✅" if task.get("completed_at") else "⬜"
                due_info = ""
                if task.get("due"):
                    due_dt = datetime.fromtimestamp(task.get("due") / 1000, tz=timezone.utc)
                    due_info = f" (截止: {due_dt.strftime('%m-%d')})"
                print(f"     {status_icon} {task.get('summary', 'N/A')[:25]}{due_info}")
            return tasks
        except LarkAPIError as e:
            print(f"  ❌ 获取失败: {e}")
            raise
    
    def cleanup(self):
        """清理创建的任务"""
        print(f"\n🧹 清理测试任务...")
        for task_guid in list(self.created_tasks):
            try:
                self.test_delete_task(task_guid)
            except Exception as e:
                print(f"  ⚠️  清理失败 {task_guid}: {e}")


def main():
    print("=" * 60)
    print("Lark Task API v2 功能测试 (修复版)")
    print("=" * 60)
    
    tester = TaskAPITester()
    results = []
    task1 = task2 = task3 = None
    
    try:
        # 1. 测试列出任务
        try:
            tasks = tester.test_list_tasks()
            results.append(("列出任务", True, f"获取到 {len(tasks)} 个任务"))
        except Exception as e:
            results.append(("列出任务", False, str(e)))
        
        # 2. 测试创建简单任务
        try:
            task1 = tester.test_create_task(
                "API测试 - 简单任务",
                description="这是一个测试任务，用于验证 Lark Task API 的基本功能"
            )
            results.append(("创建简单任务", True, f"guid={task1.get('guid')[:8]}..."))
        except Exception as e:
            results.append(("创建简单任务", False, str(e)))
        
        # 3. 测试创建带截止日期的任务 (使用毫秒时间戳)
        try:
            due_ts = to_timestamp_ms(datetime.now() + timedelta(days=7))
            task2 = tester.test_create_task(
                "API测试 - 带截止日期的任务",
                description="这是一个带截止日期的测试任务",
                due=due_ts
            )
            results.append(("创建带截止日期任务", True, f"due_ts={due_ts}"))
        except Exception as e:
            results.append(("创建带截止日期任务", False, str(e)))
        
        # 4. 测试获取任务详情
        if task1:
            try:
                tester.test_get_task(task1.get("guid"))
                results.append(("获取任务详情", True, "成功"))
            except Exception as e:
                results.append(("获取任务详情", False, str(e)))
        
        # 5. 测试更新任务
        if task1:
            try:
                tester.test_update_task(
                    task1.get("guid"),
                    summary="API测试 - 已更新的任务",
                    description="任务已被更新，这是新的描述"
                )
                results.append(("更新任务", True, "成功"))
            except Exception as e:
                results.append(("更新任务", False, str(e)))
        
        # 6. 测试完成任务
        if task2:
            try:
                tester.test_complete_task(task2.get("guid"))
                results.append(("完成任务", True, "成功"))
            except Exception as e:
                results.append(("完成任务", False, str(e)))
        
        # 7. 测试取消完成任务
        if task2:
            try:
                tester.test_uncomplete_task(task2.get("guid"))
                results.append(("取消完成任务", True, "成功"))
            except Exception as e:
                results.append(("取消完成任务", False, str(e)))
        
        # 8. 测试创建全天任务
        try:
            task3 = tester.test_create_task(
                "API测试 - 全天任务",
                description="这是一个全天任务",
                is_all_day=True,
                due=to_timestamp_ms(datetime.now() + timedelta(days=3))
            )
            results.append(("创建全天任务", True, f"guid={task3.get('guid')[:8]}..."))
        except Exception as e:
            results.append(("创建全天任务", False, str(e)))
        
        # 9. 再次列出任务查看状态
        try:
            tasks = tester.test_list_tasks()
            results.append(("列出任务(二次)", True, f"获取到 {len(tasks)} 个任务"))
        except Exception as e:
            results.append(("列出任务(二次)", False, str(e)))
        
    finally:
        # 清理
        tester.cleanup()
    
    # 输出测试报告
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
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
