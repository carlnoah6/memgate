#!/usr/bin/env python3
"""
daily-report-engine.py — 代码驱动的日报生成引擎 (Refactored)

核心原则：Prompt 是建议，LLM 可以不听；代码是强制，执行就是对的。
流程：数据采集（纯代码）→ 分步 LLM 分析 → 组装验证（纯代码）→ 保存交付

用法：
    python3 scripts/daily-report-engine.py [YYYY-MM-DD]
    python3 scripts/daily-report-engine.py              # 默认昨天
    python3 scripts/daily-report-engine.py --dry-run    # 生成但不交付
"""

import sys
import os
import datetime
import traceback
import importlib.util

# Ensure we can import from the package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from daily_report.config import log, LLM_MODEL, LLM_MODEL_HEAVY, SGT, MAX_REVIEW_FILES
from daily_report.data_collector import DataCollector
from daily_report.analyzer import LLMAnalyzer
from daily_report.formatter import ReportAssembler
from daily_report.delivery import ReportDelivery

def main():
    # 解析参数
    dry_run = "--dry-run" in sys.argv
    fast_mode = "--fast" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    # 确定日期
    if args:
        try:
            target_date = datetime.date.fromisoformat(args[0])
        except ValueError:
            print(f"❌ 无效日期格式: {args[0]}，请使用 YYYY-MM-DD")
            sys.exit(1)
    else:
        now = datetime.datetime.now(SGT)
        target_date = (now - datetime.timedelta(days=1)).date()

    # 快速模式调整
    max_review_files = MAX_REVIEW_FILES
    if fast_mode:
        max_review_files = 3
        log("⚡ 快速模式启用: Code Review 上限调整为 3 个文件")

    log(f"🌙 日报引擎启动 | 目标日期: {target_date} | dry_run={dry_run}")
    log(f"   LLM: {LLM_MODEL} (heavy: {LLM_MODEL_HEAVY})")

    try:
        # 阶段 0: 日常清理（代码强制，不依赖 LLM）
        try:
            # 动态导入同目录下的 cleanup-task-chats.py
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cleanup_script = os.path.join(script_dir, "cleanup-task-chats.py")
            
            if os.path.exists(cleanup_script):
                spec = importlib.util.spec_from_file_location("cleanup_task_chats", cleanup_script)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                log("🧹 阶段 0: 清理过期任务群聊 (>24h)")
                cleanup_result = mod.cleanup_old_task_chats(hours=24, dry_run=dry_run)
                dissolved_count = len(cleanup_result.get("dissolved", []))
                failed_count = len(cleanup_result.get("failed", []))
                if dissolved_count or failed_count:
                    log(f"   解散 {dissolved_count} 个旧群聊, {failed_count} 个失败")
                else:
                    log(f"   无需清理 (共 {cleanup_result.get('task_chats_found', 0)} 个任务群, 全部 <24h)")
            else:
                log(f"⚠️ 清理脚本未找到: {cleanup_script}")
        except Exception as e:
            log(f"⚠️ 群聊清理失败 (非阻塞): {e}")

        # 阶段 1: 数据采集
        collector = DataCollector(target_date)
        collector.collect_all()

        # 阶段 2: LLM 分析
        analyzer = LLMAnalyzer(collector, max_review_files=max_review_files)
        analyzer.analyze_all()

        # 阶段 3: 组装报告
        assembler = ReportAssembler(collector, analyzer)
        report = assembler.assemble()
        assembler.validate_and_fix()

        # 阶段 4: 保存 + 交付
        delivery = ReportDelivery(collector, assembler.report)
        report_path = delivery.save()
        delivery.update_reflections()
        delivery.deliver(dry_run=dry_run)

        log(f"🎉 日报生成完成: {report_path}")

    except Exception as e:
        log(f"❌ 日报生成失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
