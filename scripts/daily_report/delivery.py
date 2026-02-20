import os
from .config import log, run_cmd, WORKSPACE
from .data_collector import DataCollector
from .formatter import ReportAssembler

# ════════════════════════════════════════════════════════════════════
# 阶段 4：保存 + 交付（纯代码）
# ════════════════════════════════════════════════════════════════════

class ReportDelivery:
    """纯代码保存和交付"""

    def __init__(self, data: DataCollector, report: str):
        self.data = data
        self.report = report

    def save(self):
        """保存报告到文件"""
        log("💾 阶段 4: 保存报告")

        # 确保目录存在
        report_dir = f"{WORKSPACE}/memory/daily-reports"
        os.makedirs(report_dir, exist_ok=True)

        report_path = f"{report_dir}/{self.data.date_str}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.report)

        log(f"💾 已保存: {report_path} ({len(self.report)} chars)")
        return report_path

    def update_reflections(self):
        """更新 reflections.md"""
        log("📝 更新 reflections.md...")
        ref_path = f"{WORKSPACE}/memory/reflections.md"

        # 从报告中提取经验教训部分
        reflection_entry = (
            f"\n\n## {self.data.date_str}（{self.data.day_name}，"
            f"系统第 {self.data.system_uptime_days} 天）\n\n"
            f"*由 daily-report-engine.py 自动生成*\n"
        )

        # 提取规律行
        for line in self.report.split("\n"):
            if "规律" in line and ("→" in line or ":" in line):
                reflection_entry += f"{line}\n"

        try:
            with open(ref_path, "a", encoding="utf-8") as f:
                f.write(reflection_entry)
            log(f"📝 已追加到 reflections.md")
        except Exception as e:
            log(f"⚠️ reflections.md 更新失败: {e}")

    def deliver(self, dry_run: bool = False):
        """调用交付脚本"""
        if dry_run:
            log("📤 [DRY RUN] 跳过交付")
            return

        log("📤 交付报告...")
        script = f"{WORKSPACE}/scripts/deliver-daily-report.sh"
        if not os.path.exists(script):
            log(f"⚠️ 交付脚本不存在: {script}")
            return

        result = run_cmd(f"bash {script} {self.data.date_str} --skip-chat", timeout=120)
        log(f"📤 交付结果:\n{result}")
