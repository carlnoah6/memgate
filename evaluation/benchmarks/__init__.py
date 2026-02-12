"""Benchmark plugin package."""

from evaluation.benchmarks.mmlu import MMLUBenchmark
from evaluation.benchmarks.humaneval import HumanEvalBenchmark
from evaluation.benchmarks.gsm8k import GSM8KBenchmark

__all__ = ["MMLUBenchmark", "HumanEvalBenchmark", "GSM8KBenchmark"]
