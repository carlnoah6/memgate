"""
Evaluation framework for benchmarking language models.

Supports pluggable benchmarks (MMLU, HumanEval, GSM8K) with configurable
few-shot prompting and automated scoring.
"""

from evaluation.evaluator import Evaluator, BenchmarkResult, EvalConfig
from evaluation.benchmarks.mmlu import MMLUBenchmark
from evaluation.benchmarks.humaneval import HumanEvalBenchmark
from evaluation.benchmarks.gsm8k import GSM8KBenchmark

BENCHMARK_REGISTRY: dict[str, type] = {
    "mmlu": MMLUBenchmark,
    "humaneval": HumanEvalBenchmark,
    "gsm8k": GSM8KBenchmark,
}

__all__ = [
    "Evaluator",
    "BenchmarkResult",
    "EvalConfig",
    "MMLUBenchmark",
    "HumanEvalBenchmark",
    "GSM8KBenchmark",
    "BENCHMARK_REGISTRY",
]
