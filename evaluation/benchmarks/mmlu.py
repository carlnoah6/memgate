"""
MMLU Benchmark — Massive Multitask Language Understanding.

57 subjects across STEM, humanities, social sciences, and more.
Evaluates multi-choice accuracy with optional few-shot prompting.

Dataset format (HuggingFace ``cais/mmlu``):
    {"question": str, "choices": [str, str, str, str], "answer": int, "subject": str}
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from evaluation.evaluator import Benchmark, SampleResult, exact_match


# 57 MMLU subjects
MMLU_SUBJECTS = [
    "abstract_algebra", "anatomy", "astronomy", "business_ethics",
    "clinical_knowledge", "college_biology", "college_chemistry",
    "college_computer_science", "college_mathematics", "college_medicine",
    "college_physics", "computer_security", "conceptual_physics",
    "econometrics", "electrical_engineering", "elementary_mathematics",
    "formal_logic", "global_facts", "high_school_biology",
    "high_school_chemistry", "high_school_computer_science",
    "high_school_european_history", "high_school_geography",
    "high_school_government_and_politics", "high_school_macroeconomics",
    "high_school_mathematics", "high_school_microeconomics",
    "high_school_physics", "high_school_psychology",
    "high_school_statistics", "high_school_us_history",
    "high_school_world_history", "human_aging", "human_sexuality",
    "international_law", "jurisprudence", "logical_fallacies",
    "machine_learning", "management", "marketing", "medical_genetics",
    "miscellaneous", "moral_disputes", "moral_scenarios", "nutrition",
    "philosophy", "prehistory", "professional_accounting",
    "professional_law", "professional_medicine", "professional_psychology",
    "public_relations", "security_studies", "sociology", "us_foreign_policy",
    "virology", "world_religions",
]

CHOICES = ["A", "B", "C", "D"]


def _format_subject(subject: str) -> str:
    """Convert snake_case subject to human-readable title."""
    return subject.replace("_", " ").title()


def _format_question(sample: dict[str, Any]) -> str:
    """Format a single MMLU question with choices."""
    question = sample["question"].strip()
    choices = sample["choices"]
    lines = [question]
    for i, choice in enumerate(choices):
        lines.append(f"{CHOICES[i]}. {choice}")
    return "\n".join(lines)


class MMLUBenchmark(Benchmark):
    """
    MMLU (Hendrycks et al., 2021) — 57-subject multiple-choice benchmark.

    Supports:
    - Loading from HuggingFace datasets or local JSONL files
    - Configurable subjects (default: all 57)
    - 0-shot and few-shot evaluation
    - Per-subject and aggregate accuracy
    """

    name = "mmlu"

    def __init__(
        self,
        subjects: list[str] | None = None,
        data_dir: str | Path | None = None,
    ):
        self.subjects = subjects or MMLU_SUBJECTS
        self.data_dir = Path(data_dir) if data_dir else None
        self._train_data: list[dict[str, Any]] = []
        self._test_data: list[dict[str, Any]] = []

    def load_dataset(self, split: str = "test") -> list[dict[str, Any]]:
        """
        Load MMLU dataset.

        Attempts in order:
        1. Local JSONL files in data_dir (``{split}/{subject}.jsonl``)
        2. HuggingFace ``datasets`` library
        3. Synthetic sample data (for testing)
        """
        if self.data_dir and self.data_dir.exists():
            return self._load_local(split)

        try:
            return self._load_hf(split)
        except Exception:
            return self._generate_synthetic(split)

    def _load_local(self, split: str) -> list[dict[str, Any]]:
        """Load from local JSONL files."""
        data = []
        for subject in self.subjects:
            path = self.data_dir / split / f"{subject}.jsonl"
            if not path.exists():
                continue
            with open(path) as f:
                for line in f:
                    sample = json.loads(line)
                    sample.setdefault("subject", subject)
                    data.append(sample)
        return data

    def _load_hf(self, split: str) -> list[dict[str, Any]]:
        """Load from HuggingFace datasets."""
        from datasets import load_dataset  # type: ignore

        data = []
        for subject in self.subjects:
            ds = load_dataset("cais/mmlu", subject, split=split, trust_remote_code=True)
            for row in ds:
                data.append({
                    "question": row["question"],
                    "choices": row["choices"],
                    "answer": int(row["answer"]),
                    "subject": subject,
                })
        return data

    def _generate_synthetic(self, split: str) -> list[dict[str, Any]]:
        """Generate minimal synthetic data for testing."""
        rng = random.Random(42)
        data = []
        for subject in self.subjects[:5]:  # only 5 subjects for synthetic
            for i in range(10):
                answer = rng.randint(0, 3)
                data.append({
                    "question": f"Sample {subject} question {i}?",
                    "choices": [
                        f"Choice A for {i}",
                        f"Choice B for {i}",
                        f"Choice C for {i}",
                        f"Choice D for {i}",
                    ],
                    "answer": answer,
                    "subject": subject,
                })
        return data

    def get_fewshot_examples(self, n: int) -> list[dict[str, Any]]:
        """Get n few-shot examples from the dev/validation split."""
        if n == 0:
            return []

        if not self._train_data:
            try:
                self._train_data = self.load_dataset(split="validation")
            except Exception:
                self._train_data = self._generate_synthetic("validation")

        # Sample deterministically
        rng = random.Random(42)
        examples = list(self._train_data)
        rng.shuffle(examples)
        return examples[:n]

    def build_prompt(
        self,
        sample: dict[str, Any],
        fewshot_examples: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Build prompt for MMLU.

        Format:
            The following are multiple choice questions about {subject}.

            {few-shot examples with answers}

            {question}
            A. ...
            B. ...
            C. ...
            D. ...
            Answer:
        """
        subject = _format_subject(sample.get("subject", "general knowledge"))
        parts = [f"The following are multiple choice questions about {subject}.\n"]

        # Few-shot examples
        if fewshot_examples:
            for ex in fewshot_examples:
                q = _format_question(ex)
                answer_letter = CHOICES[ex["answer"]]
                parts.append(f"{q}\nAnswer: {answer_letter}\n")

        # Target question
        q = _format_question(sample)
        parts.append(f"{q}\nAnswer:")

        return "\n".join(parts)

    def score(
        self,
        sample: dict[str, Any],
        generated_text: str,
    ) -> SampleResult:
        """
        Score by extracting the first A/B/C/D token from generated text.
        """
        expected = CHOICES[sample["answer"]]
        predicted = self._extract_answer(generated_text)
        correct = predicted == expected

        return SampleResult(
            sample_id=0,
            prompt="",
            generated=generated_text,
            reference=expected,
            correct=correct,
            score=1.0 if correct else 0.0,
            metadata={
                "subject": sample.get("subject", ""),
                "predicted": predicted,
                "expected": expected,
            },
        )

    @staticmethod
    def _extract_answer(text: str) -> str:
        """Extract the answer letter from generated text."""
        text = text.strip()
        if not text:
            return ""

        # Direct single-letter answer (possibly followed by punctuation)
        if len(text) == 1 and text.upper() in CHOICES:
            return text.upper()
        if len(text) >= 1 and text[0].upper() in CHOICES and (
            len(text) == 1 or text[1] in (".", ")", " ", ",", "\n")
        ):
            return text[0].upper()

        # "answer is X" or "Answer: X" pattern
        import re
        m = re.search(r"(?:answer|result)\s*(?:is|:)\s*([A-Da-d])\b", text)
        if m:
            return m.group(1).upper()

        # Look for "A.", "B.", etc.
        for ch in CHOICES:
            if f"{ch}." in text or f"{ch})" in text or f"({ch})" in text:
                return ch

        # Fallback: first capital letter that's a valid choice
        for c in text:
            if c.upper() in CHOICES:
                return c.upper()
        return ""

    def get_max_new_tokens(self) -> int:
        """MMLU only needs a single token (A/B/C/D)."""
        return 5
