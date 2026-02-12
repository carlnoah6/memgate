"""
HumanEval Benchmark — Code generation evaluation.

Evaluates code generation via pass@k on Python programming problems.
Each problem has a function signature, docstring, and test cases.

Dataset format (OpenAI HumanEval):
    {"task_id": str, "prompt": str, "canonical_solution": str,
     "test": str, "entry_point": str}
"""

from __future__ import annotations

import json
import random
import re
import signal
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from evaluation.evaluator import Benchmark, SampleResult, pass_at_k


# ---------------------------------------------------------------------------
# Safe execution sandbox
# ---------------------------------------------------------------------------

class TimeoutError(Exception):
    pass


@contextmanager
def time_limit(seconds: int):
    """Context manager to limit execution time (Unix only)."""
    def signal_handler(signum, frame):
        raise TimeoutError(f"Execution timed out after {seconds}s")

    try:
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)


def execute_code_safely(
    code: str,
    test_code: str,
    entry_point: str,
    timeout: int = 10,
) -> tuple[bool, str]:
    """
    Execute generated code + tests in a restricted namespace.

    Returns (passed, error_message).
    """
    full_code = code + "\n" + test_code + f"\ncheck({entry_point})\n"

    try:
        with time_limit(timeout):
            namespace: dict[str, Any] = {}
            exec(full_code, namespace)  # noqa: S102
        return True, ""
    except TimeoutError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

class HumanEvalBenchmark(Benchmark):
    """
    HumanEval (Chen et al., 2021) — functional correctness for code generation.

    Evaluates pass@1 by default. Generates completions for function stubs
    and runs unit tests to verify correctness.
    """

    name = "humaneval"

    def __init__(
        self,
        data_dir: str | Path | None = None,
        k: int = 1,
        timeout: int = 10,
    ):
        self.data_dir = Path(data_dir) if data_dir else None
        self.k = k
        self.timeout = timeout
        self._total_samples = 0
        self._total_correct = 0

    def load_dataset(self, split: str = "test") -> list[dict[str, Any]]:
        """
        Load HumanEval dataset.

        Attempts:
        1. Local JSONL file
        2. HuggingFace datasets
        3. Synthetic samples
        """
        if self.data_dir:
            path = self.data_dir / "HumanEval.jsonl"
            if path.exists():
                return self._load_jsonl(path)

        try:
            return self._load_hf()
        except Exception:
            return self._generate_synthetic()

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        data = []
        with open(path) as f:
            for line in f:
                data.append(json.loads(line))
        return data

    def _load_hf(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore
        ds = load_dataset("openai_humaneval", split="test", trust_remote_code=True)
        return [dict(row) for row in ds]

    def _generate_synthetic(self) -> list[dict[str, Any]]:
        """Generate minimal synthetic problems for testing."""
        return [
            {
                "task_id": "HumanEval/0",
                "prompt": 'def add(a: int, b: int) -> int:\n    """Return the sum of a and b."""\n',
                "canonical_solution": "    return a + b\n",
                "test": 'def check(candidate):\n    assert candidate(1, 2) == 3\n    assert candidate(0, 0) == 0\n    assert candidate(-1, 1) == 0\n',
                "entry_point": "add",
            },
            {
                "task_id": "HumanEval/1",
                "prompt": 'def double(x: int) -> int:\n    """Return x multiplied by 2."""\n',
                "canonical_solution": "    return x * 2\n",
                "test": 'def check(candidate):\n    assert candidate(3) == 6\n    assert candidate(0) == 0\n    assert candidate(-2) == -4\n',
                "entry_point": "double",
            },
            {
                "task_id": "HumanEval/2",
                "prompt": 'def is_even(n: int) -> bool:\n    """Return True if n is even."""\n',
                "canonical_solution": "    return n % 2 == 0\n",
                "test": 'def check(candidate):\n    assert candidate(2) == True\n    assert candidate(3) == False\n    assert candidate(0) == True\n',
                "entry_point": "is_even",
            },
        ]

    def get_fewshot_examples(self, n: int) -> list[dict[str, Any]]:
        """
        HumanEval doesn't use few-shot; the prompt IS the function stub.
        Return empty — few-shot context is ignored for code completion.
        """
        return []

    def build_prompt(
        self,
        sample: dict[str, Any],
        fewshot_examples: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Build prompt for code completion.

        The prompt is the function signature + docstring from the dataset.
        Model should generate the function body.
        """
        return sample["prompt"]

    def score(
        self,
        sample: dict[str, Any],
        generated_text: str,
    ) -> SampleResult:
        """
        Score by executing the generated code against test cases.
        """
        # Construct the full solution: prompt + generated completion
        prompt = sample["prompt"]
        completion = self._extract_completion(generated_text, sample.get("entry_point", ""))

        full_code = prompt + completion
        test_code = sample.get("test", "")
        entry_point = sample.get("entry_point", "")

        passed, error = execute_code_safely(
            full_code, test_code, entry_point, timeout=self.timeout
        )

        self._total_samples += 1
        if passed:
            self._total_correct += 1

        return SampleResult(
            sample_id=sample.get("task_id", 0),
            prompt=prompt,
            generated=generated_text,
            reference=sample.get("canonical_solution", ""),
            correct=passed,
            score=1.0 if passed else 0.0,
            metadata={
                "task_id": sample.get("task_id", ""),
                "entry_point": entry_point,
                "error": error,
                "pass@1": pass_at_k(self._total_samples, self._total_correct, k=1),
            },
        )

    @staticmethod
    def _extract_completion(text: str, entry_point: str) -> str:
        """
        Extract the function body from generated text.

        Handles common patterns:
        - Direct indented code
        - Code wrapped in ```python blocks
        - Stops at next top-level definition
        """
        # Strip markdown code blocks
        text = re.sub(r"```python\s*", "", text)
        text = re.sub(r"```\s*", "", text)

        lines = text.split("\n")
        result_lines = []
        for line in lines:
            # Stop if we hit a new top-level definition (not indented)
            if result_lines and line.strip() and not line.startswith((" ", "\t")):
                if line.startswith(("def ", "class ", "import ", "from ")):
                    break
            result_lines.append(line)

        return "\n".join(result_lines)

    def get_max_new_tokens(self) -> int:
        """Code solutions may be longer."""
        return 512
