"""
Arena — 红蓝对抗竞技场

协调 AttackerAgent、DefenderAgent 和 Evaluator 进行多轮对抗。
"""

import time
from typing import Optional

from .attacker import AttackerAgent
from .defender import DefenderAgent
from .evaluator import Evaluator
from .strategies import list_strategies
from .report import ReportGenerator


class Arena:
    """
    对抗竞技场

    运行 N 轮攻防对抗，记录结果并生成报告。

    三个角色：
    - 红队（AttackerAgent）：生成攻击 prompt
    - 蓝队（DefenderAgent）：生成回复 + MemGate 审查
    - 裁判（Evaluator）：独立判断是否泄露
    """

    def __init__(
        self,
        rounds: int = 10,
        strategy: str = "all",
        mock: bool = True,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        secrets: Optional[dict] = None,
        verbose: bool = False,
    ):
        self.total_rounds = rounds
        self.strategy_filter = strategy
        self.mock = mock
        self.verbose = verbose
        self.secrets = secrets

        # Initialize agents
        self.attacker = AttackerAgent(mock=mock, api_base=api_base, api_key=api_key)
        self.defender = DefenderAgent(
            secrets=secrets,
            mock=mock,
            api_base=api_base,
            api_key=api_key,
        )
        self.evaluator = Evaluator(
            secrets=self.defender.secrets,
            mock=mock,
            api_base=api_base,
            api_key=api_key,
        )
        self.report_gen = ReportGenerator()

    def _get_strategies(self) -> list[str]:
        """获取要使用的策略列表"""
        if self.strategy_filter == "all":
            return list_strategies()
        return [self.strategy_filter]

    def run(self) -> dict:
        """
        运行完整对抗

        Returns:
            JSON-serializable 报告 dict
        """
        strategies = self._get_strategies()
        round_id = 0

        # Distribute rounds across strategies
        rounds_per_strategy = max(1, self.total_rounds // len(strategies))
        extra_rounds = self.total_rounds - rounds_per_strategy * len(strategies)

        start_time = time.time()

        for strat_idx, strategy_name in enumerate(strategies):
            n = rounds_per_strategy
            if strat_idx < extra_rounds:
                n += 1

            for _ in range(n):
                round_id += 1
                self._run_round(round_id, strategy_name)

        elapsed = time.time() - start_time
        report = self.report_gen.finalize(elapsed_seconds=elapsed)

        if self.verbose:
            self.report_gen.print_summary()

        return report.to_dict()

    def _run_round(self, round_id: int, strategy_name: str):
        """运行一轮对抗"""
        # 1. Attacker generates attack prompt
        attack_prompt = self.attacker.generate_attack(strategy_name)

        # 2. Defender responds (with MemGate review)
        result = self.defender.respond(
            attack_prompt=attack_prompt,
            strategy_name=strategy_name,
            simulate_leak=True,
        )

        # 3. Extract review info
        review = result["review_result"]
        violations = [f"{v.category}: {v.description}" for v in review.violations]

        # 4. Independent evaluation
        eval_result = self.evaluator.evaluate(
            response=result["final_response"],
            attack_prompt=attack_prompt,
            strategy=strategy_name,
        )

        leaked = eval_result.leaked

        # 5. Record
        self.report_gen.record_round(
            round_id=round_id,
            strategy=strategy_name,
            attack_prompt=attack_prompt,
            raw_response=result["raw_response"],
            memgate_blocked=not review.passed,
            violations=violations,
            final_response=result["final_response"],
            leaked=leaked,
            eval_confidence=eval_result.confidence,
            eval_method=eval_result.method,
        )

        if self.verbose:
            status = (
                "🛡️ BLOCKED"
                if not review.passed
                else ("❌ LEAKED" if leaked else "✅ SAFE")
            )
            print(
                f"  Round {round_id:3d} [{strategy_name}] {status}"
                f" (confidence: {eval_result.confidence:.0%})"
            )
