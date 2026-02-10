"""
Arena — Red-Blue Adversarial Arena

Coordinates AttackerAgent, DefenderAgent, and Evaluator for multi-round adversarial testing.
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
    Adversarial arena.

    Runs N rounds of attack-defense adversarial testing, records results, and generates reports.

    Three roles:
    - Red Team (AttackerAgent): Generates attack prompts
    - Blue Team (DefenderAgent): Generates responses + MemGate review
    - Judge (Evaluator): Independently determines whether leaks occurred
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
        """Get the list of strategies to use."""
        if self.strategy_filter == "all":
            return list_strategies()
        return [self.strategy_filter]

    def run(self) -> dict:
        """
        Run the full adversarial test.

        Returns:
            JSON-serializable report dict
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
        """Run a single round of adversarial testing."""
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
