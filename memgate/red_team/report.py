"""
报告生成器

将对抗结果汇总为 JSON 和 Markdown 报告，包含统计数据和详细记录。
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta


SGT = timezone(timedelta(hours=8))


@dataclass
class RoundRecord:
    """一轮对抗的记录"""

    round_id: int
    strategy: str
    attack_prompt: str
    raw_response: str
    memgate_blocked: bool
    violations: list[str]
    final_response: str
    leaked: bool
    eval_confidence: float = 0.0
    eval_method: str = "pattern"


@dataclass
class StrategyStats:
    """单个策略的统计"""

    strategy: str
    total_rounds: int = 0
    blocked: int = 0
    leaked: int = 0
    safe_passed: int = 0

    @property
    def block_rate(self) -> float:
        return self.blocked / self.total_rounds if self.total_rounds else 0.0

    @property
    def leak_rate(self) -> float:
        return self.leaked / self.total_rounds if self.total_rounds else 0.0

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "total_rounds": self.total_rounds,
            "blocked": self.blocked,
            "leaked": self.leaked,
            "safe_passed": self.safe_passed,
            "block_rate": round(self.block_rate, 4),
            "leak_rate": round(self.leak_rate, 4),
        }


@dataclass
class Report:
    """完整的对抗报告"""

    total_rounds: int = 0
    total_blocked: int = 0
    total_leaked: int = 0
    total_safe: int = 0
    elapsed_seconds: float = 0.0
    strategy_stats: dict[str, StrategyStats] = field(default_factory=dict)
    rounds: list[RoundRecord] = field(default_factory=list)
    leaked_contents: list[dict] = field(default_factory=list)

    @property
    def overall_block_rate(self) -> float:
        return self.total_blocked / self.total_rounds if self.total_rounds else 0.0

    @property
    def overall_leak_rate(self) -> float:
        return self.total_leaked / self.total_rounds if self.total_rounds else 0.0

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_rounds": self.total_rounds,
                "total_blocked": self.total_blocked,
                "total_leaked": self.total_leaked,
                "total_safe_passed": self.total_safe,
                "overall_block_rate": round(self.overall_block_rate, 4),
                "overall_leak_rate": round(self.overall_leak_rate, 4),
                "elapsed_seconds": round(self.elapsed_seconds, 2),
                "timestamp": datetime.now(SGT).isoformat(),
            },
            "strategy_stats": {
                name: stats.to_dict() for name, stats in self.strategy_stats.items()
            },
            "leaked_contents": self.leaked_contents,
            "rounds": [asdict(r) for r in self.rounds],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        lines = []
        ts = datetime.now(SGT).strftime("%Y-%m-%d %H:%M SGT")

        lines.append("# 🏟️ MemGate Red Team Arena — Report")
        lines.append(f"\n**Generated:** {ts}")
        lines.append(f"**Duration:** {self.elapsed_seconds:.1f}s")
        lines.append("")

        lines.append("## 📊 Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Rounds | {self.total_rounds} |")
        lines.append(f"| 🛡️ Blocked by MemGate | {self.total_blocked} |")
        lines.append(f"| ❌ Leaked | {self.total_leaked} |")
        lines.append(f"| ✅ Safe Passed | {self.total_safe} |")
        lines.append(f"| Block Rate | {self.overall_block_rate:.1%} |")
        lines.append(f"| Leak Rate | {self.overall_leak_rate:.1%} |")
        lines.append("")

        lines.append("## 📈 Per-Strategy Results")
        lines.append("")
        lines.append("| Strategy | Rounds | Blocked | Leaked | Safe | Block Rate |")
        lines.append("|----------|--------|---------|--------|------|------------|")
        for name, stats in self.strategy_stats.items():
            lines.append(
                f"| {name} | {stats.total_rounds} | "
                f"{stats.blocked} | {stats.leaked} | "
                f"{stats.safe_passed} | {stats.block_rate:.0%} |"
            )
        lines.append("")

        if self.leaked_contents:
            lines.append("## ⚠️ Leaked Contents")
            lines.append("")
            for lc in self.leaked_contents:
                lines.append(f"### Round {lc['round_id']} [{lc['strategy']}]")
                lines.append("```")
                lines.append(lc["content"][:200])
                lines.append("```")
                lines.append("")
        else:
            lines.append("## ✅ No Leaks Detected!")
            lines.append("")
            lines.append("MemGate successfully blocked all attack attempts.")
            lines.append("")

        lines.append("## 🔍 Sample Rounds")
        lines.append("")

        blocked_rounds = [r for r in self.rounds if r.memgate_blocked][:3]
        safe_rounds = [
            r for r in self.rounds if not r.memgate_blocked and not r.leaked
        ][:3]

        if blocked_rounds:
            lines.append("### Blocked by MemGate")
            for r in blocked_rounds:
                lines.append(f"\n**Round {r.round_id}** [{r.strategy}]")
                lines.append(f"- 🔴 Attack: _{r.attack_prompt[:100]}..._")
                lines.append(f"- 🔵 Raw: _{r.raw_response[:100]}..._")
                lines.append(f"- 🛡️ Violations: {', '.join(r.violations[:3])}")
                lines.append(f"- ✅ Final: _{r.final_response[:100]}..._")

        if safe_rounds:
            lines.append("\n### Safe Passed")
            for r in safe_rounds:
                lines.append(f"\n**Round {r.round_id}** [{r.strategy}]")
                lines.append(f"- 🔴 Attack: _{r.attack_prompt[:100]}..._")
                lines.append(f"- ✅ Response: _{r.final_response[:100]}..._")

        lines.append("")
        return "\n".join(lines)


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        self.report = Report()

    def record_round(
        self,
        round_id: int,
        strategy: str,
        attack_prompt: str,
        raw_response: str,
        memgate_blocked: bool,
        violations: list[str],
        final_response: str,
        leaked: bool,
        eval_confidence: float = 0.0,
        eval_method: str = "pattern",
    ):
        """记录一轮对抗结果"""
        record = RoundRecord(
            round_id=round_id,
            strategy=strategy,
            attack_prompt=attack_prompt,
            raw_response=raw_response,
            memgate_blocked=memgate_blocked,
            violations=violations,
            final_response=final_response,
            leaked=leaked,
            eval_confidence=eval_confidence,
            eval_method=eval_method,
        )
        self.report.rounds.append(record)

        self.report.total_rounds += 1
        if memgate_blocked:
            self.report.total_blocked += 1
        if leaked:
            self.report.total_leaked += 1
            self.report.leaked_contents.append(
                {
                    "round_id": round_id,
                    "strategy": strategy,
                    "content": final_response,
                }
            )
        if not memgate_blocked and not leaked:
            self.report.total_safe += 1

        if strategy not in self.report.strategy_stats:
            self.report.strategy_stats[strategy] = StrategyStats(strategy=strategy)
        stats = self.report.strategy_stats[strategy]
        stats.total_rounds += 1
        if memgate_blocked:
            stats.blocked += 1
        if leaked:
            stats.leaked += 1
        if not memgate_blocked and not leaked:
            stats.safe_passed += 1

    def finalize(self, elapsed_seconds: float = 0.0) -> Report:
        """返回最终报告"""
        self.report.elapsed_seconds = elapsed_seconds
        return self.report

    def print_summary(self):
        """打印简洁的摘要"""
        r = self.report
        print(f"\n{'='*60}")
        print("🏟️  MemGate Red Team Arena — Report")
        print(f"{'='*60}")
        print(f"Total rounds:     {r.total_rounds}")
        print(f"Blocked by gate:  {r.total_blocked}")
        print(f"Leaked:           {r.total_leaked}")
        print(f"Safe passed:      {r.total_safe}")
        print(f"Overall block rate: {r.overall_block_rate:.1%}")
        print(f"Time elapsed:     {r.elapsed_seconds:.1f}s")
        print("\n--- Per Strategy ---")
        for name, stats in r.strategy_stats.items():
            print(
                f"  {name}: "
                f"{stats.blocked}/{stats.total_rounds} blocked "
                f"({stats.block_rate:.0%})"
            )
        if r.leaked_contents:
            print(f"\n⚠️  Leaked contents ({len(r.leaked_contents)}):")
            for lc in r.leaked_contents:
                print(f"  Round {lc['round_id']} [{lc['strategy']}]:")
                print(f"    {lc['content'][:100]}...")
        print(f"{'='*60}\n")
