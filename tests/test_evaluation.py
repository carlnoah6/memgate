"""
Tests for the evaluation framework.

Validates:
- Evaluator orchestration with mock model
- Prompt formatting for each benchmark
- Scoring logic for MMLU, HumanEval, GSM8K
- Few-shot prompt construction
- Result serialization
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import torch

from evaluation.evaluator import (
    Evaluator,
    EvalConfig,
    BenchmarkResult,
    SampleResult,
    exact_match,
    accuracy_score,
    pass_at_k,
)
from evaluation.benchmarks.mmlu import MMLUBenchmark
from evaluation.benchmarks.humaneval import HumanEvalBenchmark
from evaluation.benchmarks.gsm8k import GSM8KBenchmark, _extract_number


# ---------------------------------------------------------------------------
# Mock model & tokenizer
# ---------------------------------------------------------------------------

class MockTokenizer:
    """Simple tokenizer: one byte per character."""

    def encode(self, text: str) -> list[int]:
        return [ord(c) % 256 for c in text]

    def decode(self, token_ids: list[int] | torch.Tensor) -> str:
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.tolist()
        return "".join(chr(max(32, t % 128)) for t in token_ids)


class MockGenerator:
    """Generator that returns a pre-configured response."""

    def __init__(self, response_text: str = "A"):
        self.response_text = response_text
        self._tokenizer = MockTokenizer()

    def generate(
        self,
        prompt_tokens: torch.Tensor,
        max_new_tokens: int = 128,
        **kwargs,
    ) -> torch.Tensor:
        response_ids = self._tokenizer.encode(self.response_text)
        response_tensor = torch.tensor([response_ids], dtype=torch.long)
        return torch.cat([prompt_tokens, response_tensor], dim=-1)


# ---------------------------------------------------------------------------
# Scoring utilities
# ---------------------------------------------------------------------------

class TestScoringUtilities:
    """Test scoring helper functions."""

    def test_exact_match_basic(self):
        assert exact_match("hello", "hello")
        assert exact_match("Hello", "hello")  # case insensitive
        assert not exact_match("hello", "world")

    def test_exact_match_whitespace(self):
        assert exact_match("  hello  world  ", "hello world")
        assert exact_match("hello\n", "hello")

    def test_exact_match_no_normalize(self):
        assert not exact_match("  hello  ", "hello", normalize=False)

    def test_accuracy_score_perfect(self):
        results = [
            SampleResult(i, "", "", "", correct=True) for i in range(10)
        ]
        assert accuracy_score(results) == 1.0

    def test_accuracy_score_zero(self):
        results = [
            SampleResult(i, "", "", "", correct=False) for i in range(10)
        ]
        assert accuracy_score(results) == 0.0

    def test_accuracy_score_half(self):
        results = [
            SampleResult(i, "", "", "", correct=(i % 2 == 0)) for i in range(10)
        ]
        assert accuracy_score(results) == 0.5

    def test_accuracy_score_empty(self):
        assert accuracy_score([]) == 0.0

    def test_pass_at_k_all_correct(self):
        assert pass_at_k(10, 10, k=1) == 1.0

    def test_pass_at_k_none_correct(self):
        assert pass_at_k(10, 0, k=1) == 0.0

    def test_pass_at_k_partial(self):
        # 5 out of 10 correct, k=1: P(at least 1 correct) = 1 - C(5,1)/C(10,1) = 0.5
        result = pass_at_k(10, 5, k=1)
        assert abs(result - 0.5) < 1e-6

    def test_pass_at_k_higher_k(self):
        # More draws → higher probability
        p1 = pass_at_k(10, 5, k=1)
        p3 = pass_at_k(10, 5, k=3)
        assert p3 > p1


# ---------------------------------------------------------------------------
# MMLU
# ---------------------------------------------------------------------------

class TestMMLUBenchmark:
    """Test MMLU benchmark implementation."""

    @pytest.fixture
    def benchmark(self):
        return MMLUBenchmark(subjects=["abstract_algebra", "anatomy"])

    def test_load_synthetic(self, benchmark):
        data = benchmark.load_dataset("test")
        assert len(data) > 0
        sample = data[0]
        assert "question" in sample
        assert "choices" in sample
        assert len(sample["choices"]) == 4
        assert "answer" in sample
        assert 0 <= sample["answer"] <= 3

    def test_build_prompt_zero_shot(self, benchmark):
        sample = {
            "question": "What is 2+2?",
            "choices": ["3", "4", "5", "6"],
            "answer": 1,
            "subject": "elementary_mathematics",
        }
        prompt = benchmark.build_prompt(sample, fewshot_examples=None)

        assert "Elementary Mathematics" in prompt
        assert "What is 2+2?" in prompt
        assert "A. 3" in prompt
        assert "B. 4" in prompt
        assert "C. 5" in prompt
        assert "D. 6" in prompt
        assert prompt.endswith("Answer:")

    def test_build_prompt_few_shot(self, benchmark):
        sample = {
            "question": "Target question?",
            "choices": ["a", "b", "c", "d"],
            "answer": 0,
            "subject": "anatomy",
        }
        fewshot = [
            {
                "question": "Example question?",
                "choices": ["x", "y", "z", "w"],
                "answer": 2,
                "subject": "anatomy",
            }
        ]
        prompt = benchmark.build_prompt(sample, fewshot_examples=fewshot)

        assert "Example question?" in prompt
        assert "Answer: C" in prompt  # few-shot answer
        assert "Target question?" in prompt
        assert prompt.endswith("Answer:")

    def test_score_correct(self, benchmark):
        sample = {"question": "Q?", "choices": ["a", "b", "c", "d"], "answer": 0}
        result = benchmark.score(sample, "A")
        assert result.correct is True
        assert result.score == 1.0

    def test_score_incorrect(self, benchmark):
        sample = {"question": "Q?", "choices": ["a", "b", "c", "d"], "answer": 0}
        result = benchmark.score(sample, "B")
        assert result.correct is False
        assert result.score == 0.0

    def test_extract_answer_variants(self, benchmark):
        assert benchmark._extract_answer("A") == "A"
        assert benchmark._extract_answer("B.") == "B"
        assert benchmark._extract_answer("(C)") == "C"
        assert benchmark._extract_answer("The answer is D") == "D"
        assert benchmark._extract_answer(" a ") == "A"


# ---------------------------------------------------------------------------
# HumanEval
# ---------------------------------------------------------------------------

class TestHumanEvalBenchmark:
    """Test HumanEval benchmark implementation."""

    @pytest.fixture
    def benchmark(self):
        return HumanEvalBenchmark()

    def test_load_synthetic(self, benchmark):
        data = benchmark.load_dataset("test")
        assert len(data) >= 3
        sample = data[0]
        assert "task_id" in sample
        assert "prompt" in sample
        assert "test" in sample
        assert "entry_point" in sample

    def test_build_prompt(self, benchmark):
        sample = {
            "task_id": "HumanEval/0",
            "prompt": 'def add(a, b):\n    """Add a and b."""\n',
        }
        prompt = benchmark.build_prompt(sample)
        assert prompt == sample["prompt"]

    def test_score_correct_solution(self, benchmark):
        sample = {
            "task_id": "HumanEval/0",
            "prompt": 'def add(a: int, b: int) -> int:\n    """Return the sum."""\n',
            "canonical_solution": "    return a + b\n",
            "test": 'def check(candidate):\n    assert candidate(1, 2) == 3\n    assert candidate(0, 0) == 0\n',
            "entry_point": "add",
        }
        result = benchmark.score(sample, "    return a + b\n")
        assert result.correct is True

    def test_score_wrong_solution(self, benchmark):
        sample = {
            "task_id": "HumanEval/0",
            "prompt": 'def add(a: int, b: int) -> int:\n    """Return the sum."""\n',
            "canonical_solution": "    return a + b\n",
            "test": 'def check(candidate):\n    assert candidate(1, 2) == 3\n',
            "entry_point": "add",
        }
        result = benchmark.score(sample, "    return a * b\n")
        assert result.correct is False

    def test_fewshot_returns_empty(self, benchmark):
        assert benchmark.get_fewshot_examples(5) == []


# ---------------------------------------------------------------------------
# GSM8K
# ---------------------------------------------------------------------------

class TestGSM8KBenchmark:
    """Test GSM8K benchmark implementation."""

    @pytest.fixture
    def benchmark(self):
        return GSM8KBenchmark()

    def test_load_synthetic(self, benchmark):
        data = benchmark.load_dataset("test")
        assert len(data) >= 3
        sample = data[0]
        assert "question" in sample
        assert "answer" in sample

    def test_build_prompt_zero_shot(self, benchmark):
        sample = {"question": "What is 2+3?", "answer": "2+3=5\n#### 5"}
        prompt = benchmark.build_prompt(sample, fewshot_examples=None)
        assert "Q: What is 2+3?" in prompt
        assert "Let's think step by step" in prompt

    def test_build_prompt_few_shot(self, benchmark):
        sample = {"question": "Target?", "answer": "#### 10"}
        fewshot = [{"question": "Example?", "answer": "work\n#### 5"}]
        prompt = benchmark.build_prompt(sample, fewshot_examples=fewshot)
        assert "Q: Example?" in prompt
        assert "#### 5" in prompt
        assert "Q: Target?" in prompt

    def test_extract_number_gsm8k_format(self):
        assert _extract_number("Some steps\n#### 42") == "42"
        assert _extract_number("#### 1,234") == "1234"

    def test_extract_number_boxed(self):
        assert _extract_number("\\boxed{42}") == "42"

    def test_extract_number_answer_is(self):
        assert _extract_number("The answer is 42.") == "42"

    def test_extract_number_last_number(self):
        assert _extract_number("First 10 then 20 finally 30") == "30"

    def test_score_correct(self, benchmark):
        sample = {"question": "Q?", "answer": "steps\n#### 42"}
        result = benchmark.score(sample, "The answer is 42")
        assert result.correct is True

    def test_score_incorrect(self, benchmark):
        sample = {"question": "Q?", "answer": "steps\n#### 42"}
        result = benchmark.score(sample, "The answer is 99")
        assert result.correct is False

    def test_score_no_number(self, benchmark):
        sample = {"question": "Q?", "answer": "steps\n#### 42"}
        result = benchmark.score(sample, "I don't know")
        assert result.correct is False


# ---------------------------------------------------------------------------
# Evaluator integration
# ---------------------------------------------------------------------------

class TestEvaluator:
    """Integration tests for the Evaluator orchestration."""

    def test_run_mmlu_with_mock(self):
        """Run MMLU with a mock model that always answers 'A'."""
        generator = MockGenerator(response_text="A")
        tokenizer = MockTokenizer()
        config = EvalConfig(max_samples=5, temperature=0.0)

        benchmark = MMLUBenchmark(subjects=["abstract_algebra"])
        evaluator = Evaluator(generator, tokenizer, config)
        results = evaluator.run([benchmark])

        assert len(results) == 1
        r = results[0]
        assert r.benchmark_name == "mmlu"
        assert r.num_samples == 5
        assert 0.0 <= r.accuracy <= 1.0
        assert r.elapsed_seconds >= 0

    def test_run_gsm8k_with_mock(self):
        """Run GSM8K with a mock model."""
        generator = MockGenerator(response_text=" The answer is 8\n#### 8")
        tokenizer = MockTokenizer()
        config = EvalConfig(max_samples=3, temperature=0.0)

        benchmark = GSM8KBenchmark()
        evaluator = Evaluator(generator, tokenizer, config)
        results = evaluator.run([benchmark])

        assert len(results) == 1
        r = results[0]
        assert r.benchmark_name == "gsm8k"
        assert r.num_samples == 3

    def test_run_multiple_benchmarks(self):
        """Run multiple benchmarks in one evaluation."""
        generator = MockGenerator(response_text="A")
        tokenizer = MockTokenizer()
        config = EvalConfig(max_samples=3, temperature=0.0)

        benchmarks = [
            MMLUBenchmark(subjects=["abstract_algebra"]),
            GSM8KBenchmark(),
        ]
        evaluator = Evaluator(generator, tokenizer, config)
        results = evaluator.run(benchmarks)

        assert len(results) == 2
        assert results[0].benchmark_name == "mmlu"
        assert results[1].benchmark_name == "gsm8k"

    def test_save_results(self):
        """Test result serialization to JSON and Markdown."""
        result = BenchmarkResult(
            benchmark_name="test",
            num_samples=10,
            num_correct=7,
            accuracy=0.7,
            metrics={"accuracy": 0.7},
            elapsed_seconds=1.5,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = Evaluator.save_results([result], tmpdir)

            assert json_path.exists()
            assert md_path.exists()

            # Validate JSON
            data = json.loads(json_path.read_text())
            assert "results" in data
            assert "summary" in data
            assert data["summary"]["test"]["accuracy"] == 0.7

            # Validate Markdown
            md = md_path.read_text()
            assert "# Evaluation Report" in md
            assert "test" in md
            assert "0.7000" in md

    def test_config_defaults(self):
        """Test EvalConfig default values."""
        config = EvalConfig()
        assert config.num_fewshot == 0
        assert config.temperature == 0.0
        assert config.device == "cpu"
        assert config.torch_dtype == torch.float32

    def test_sample_result_dataclass(self):
        """Test SampleResult creation."""
        r = SampleResult(
            sample_id=0,
            prompt="test prompt",
            generated="A",
            reference="A",
            correct=True,
            score=1.0,
        )
        assert r.correct
        assert r.score == 1.0


# ---------------------------------------------------------------------------
# Few-shot prompts
# ---------------------------------------------------------------------------

class TestFewShotPrompts:
    """Verify few-shot prompt construction across benchmarks."""

    def test_mmlu_5shot_format(self):
        benchmark = MMLUBenchmark(subjects=["abstract_algebra"])
        fewshot = benchmark.get_fewshot_examples(5)

        sample = {
            "question": "Test?",
            "choices": ["a", "b", "c", "d"],
            "answer": 0,
            "subject": "abstract_algebra",
        }
        prompt = benchmark.build_prompt(sample, fewshot)

        # Count "Answer:" occurrences — should be 5 (fewshot) + 1 (target)
        assert prompt.count("Answer:") == 6

    def test_gsm8k_5shot_format(self):
        benchmark = GSM8KBenchmark()
        fewshot = benchmark.get_fewshot_examples(5)

        sample = {"question": "Test?", "answer": "#### 1"}
        prompt = benchmark.build_prompt(sample, fewshot)

        # Should have 6 "Q:" lines (5 fewshot + 1 target)
        assert prompt.count("Q:") == 6

    def test_zero_shot_no_examples(self):
        benchmark = MMLUBenchmark(subjects=["abstract_algebra"])
        sample = {
            "question": "Q?",
            "choices": ["a", "b", "c", "d"],
            "answer": 0,
            "subject": "abstract_algebra",
        }
        prompt = benchmark.build_prompt(sample, fewshot_examples=None)
        assert prompt.count("Answer:") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
