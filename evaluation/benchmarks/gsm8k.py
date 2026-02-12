"""
GSM8K Benchmark — Grade School Math 8K.

Tests mathematical reasoning via chain-of-thought word problems.
Each problem requires multi-step arithmetic reasoning.

Dataset format (HuggingFace ``gsm8k``):
    {"question": str, "answer": str}
    answer format: "step1\nstep2\n...\n#### {final_number}"
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from evaluation.evaluator import Benchmark, SampleResult


def _extract_number(text: str) -> str | None:
    """
    Extract the final numerical answer from text.

    Handles:
    - GSM8K format: "#### 42"
    - Boxed LaTeX: "\\boxed{42}"
    - Last number in text: "The answer is 42."
    - Numbers with commas: "1,234"
    """
    # GSM8K canonical format
    match = re.search(r"####\s*(-?[\d,]+\.?\d*)", text)
    if match:
        return match.group(1).replace(",", "")

    # LaTeX boxed
    match = re.search(r"\\boxed\{(-?[\d,]+\.?\d*)\}", text)
    if match:
        return match.group(1).replace(",", "")

    # "answer is X" pattern — capture number, exclude trailing period that's a sentence end
    match = re.search(r"(?:answer|result)\s+(?:is|=)\s*(-?[\d,]+(?:\.\d+)?)", text, re.I)
    if match:
        return match.group(1).replace(",", "")

    # Last number in text
    numbers = re.findall(r"-?[\d,]+\.?\d*", text)
    if numbers:
        return numbers[-1].replace(",", "")

    return None


def _normalize_number(s: str) -> float | None:
    """Parse a number string to float, handling commas."""
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


class GSM8KBenchmark(Benchmark):
    """
    GSM8K (Cobbe et al., 2021) — grade school math word problems.

    Evaluates mathematical reasoning with chain-of-thought prompting.
    Scoring: extract final numerical answer and compare to reference.
    """

    name = "gsm8k"

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else None

    def load_dataset(self, split: str = "test") -> list[dict[str, Any]]:
        """Load GSM8K dataset."""
        if self.data_dir:
            path = self.data_dir / f"{split}.jsonl"
            if path.exists():
                return self._load_jsonl(path)

        try:
            return self._load_hf(split)
        except Exception:
            return self._generate_synthetic()

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        data = []
        with open(path) as f:
            for line in f:
                data.append(json.loads(line))
        return data

    def _load_hf(self, split: str) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore
        ds = load_dataset("gsm8k", "main", split=split, trust_remote_code=True)
        return [{"question": row["question"], "answer": row["answer"]} for row in ds]

    def _generate_synthetic(self) -> list[dict[str, Any]]:
        """Generate minimal synthetic math problems for testing."""
        return [
            {
                "question": "Tom has 5 apples. He buys 3 more. How many apples does he have?",
                "answer": "Tom starts with 5 apples.\nHe buys 3 more.\n5 + 3 = 8.\n#### 8",
            },
            {
                "question": "A store has 20 items. They sell 7 in the morning and 5 in the afternoon. How many items are left?",
                "answer": "Start with 20 items.\nSold 7 in morning: 20 - 7 = 13.\nSold 5 in afternoon: 13 - 5 = 8.\n#### 8",
            },
            {
                "question": "Each box has 6 chocolates. If you have 4 boxes, how many chocolates do you have?",
                "answer": "Each box has 6 chocolates.\n4 boxes total.\n6 × 4 = 24.\n#### 24",
            },
            {
                "question": "Lisa has $15. She earns $8 from chores and spends $6 on lunch. How much does she have?",
                "answer": "Start with $15.\nEarns $8: 15 + 8 = 23.\nSpends $6: 23 - 6 = 17.\n#### 17",
            },
            {
                "question": "A train travels at 60 mph. How far does it go in 3 hours?",
                "answer": "Speed = 60 mph.\nTime = 3 hours.\nDistance = 60 × 3 = 180 miles.\n#### 180",
            },
        ]

    def get_fewshot_examples(self, n: int) -> list[dict[str, Any]]:
        """Get few-shot examples from the train split."""
        if n == 0:
            return []

        try:
            train_data = self.load_dataset(split="train")
        except Exception:
            train_data = self._generate_synthetic()

        rng = random.Random(42)
        examples = list(train_data)
        rng.shuffle(examples)
        return examples[:n]

    def build_prompt(
        self,
        sample: dict[str, Any],
        fewshot_examples: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Build chain-of-thought prompt for GSM8K.

        Format:
            Q: {question}
            A: Let's think step by step. {chain_of_thought}

            ...

            Q: {target_question}
            A: Let's think step by step.
        """
        parts = []

        # Few-shot examples with chain-of-thought
        if fewshot_examples:
            for ex in fewshot_examples:
                parts.append(f"Q: {ex['question']}")
                parts.append(f"A: Let's think step by step. {ex['answer']}")
                parts.append("")

        # Target question
        parts.append(f"Q: {sample['question']}")
        parts.append("A: Let's think step by step.")

        return "\n".join(parts)

    def score(
        self,
        sample: dict[str, Any],
        generated_text: str,
    ) -> SampleResult:
        """
        Score by comparing extracted numerical answers.
        """
        # Extract reference answer
        ref_number_str = _extract_number(sample["answer"])
        ref_number = _normalize_number(ref_number_str) if ref_number_str else None

        # Extract predicted answer
        pred_number_str = _extract_number(generated_text)
        pred_number = _normalize_number(pred_number_str) if pred_number_str else None

        # Compare
        correct = False
        if ref_number is not None and pred_number is not None:
            # Allow small floating point tolerance
            correct = abs(ref_number - pred_number) < 1e-6

        return SampleResult(
            sample_id=0,
            prompt="",
            generated=generated_text,
            reference=sample["answer"],
            correct=correct,
            score=1.0 if correct else 0.0,
            metadata={
                "expected_number": ref_number_str,
                "predicted_number": pred_number_str,
            },
        )

    def get_max_new_tokens(self) -> int:
        """Math reasoning needs more tokens for chain-of-thought."""
        return 512
