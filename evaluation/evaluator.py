"""
Core evaluation framework — base classes, scoring utilities, and orchestration.

Design principles:
- Plugin-based benchmarks: subclass ``Benchmark`` to add new evaluations.
- Framework handles model I/O, benchmarks handle prompt construction & scoring.
- Supports n-shot prompting, batched generation, and multiple scoring metrics.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional, Protocol, Sequence

import torch


# ---------------------------------------------------------------------------
# Protocols — decouple from concrete model classes
# ---------------------------------------------------------------------------

class GeneratorProtocol(Protocol):
    """Minimal interface a generator must satisfy."""

    def generate(
        self,
        prompt_tokens: torch.Tensor,
        max_new_tokens: int = 128,
        temperature: float = 1.0,
        top_k: int = 0,
        top_p: float = 1.0,
        greedy: bool = False,
        eos_token_id: int | None = None,
        **kwargs: Any,
    ) -> torch.Tensor: ...


class TokenizerProtocol(Protocol):
    """Minimal tokenizer interface."""

    def encode(self, text: str) -> list[int]: ...
    def decode(self, token_ids: list[int] | torch.Tensor) -> str: ...


# ---------------------------------------------------------------------------
# Config & result data classes
# ---------------------------------------------------------------------------

@dataclass
class EvalConfig:
    """Configuration for an evaluation run."""

    model_path: str = ""
    benchmarks: list[str] = field(default_factory=lambda: ["mmlu"])
    num_fewshot: int = 0
    output_dir: str = "eval_results"
    max_samples: int | None = None  # limit samples per benchmark (for testing)
    batch_size: int = 1
    max_new_tokens: int = 256
    temperature: float = 0.0  # greedy by default for eval
    device: str = "cpu"
    dtype: str = "float32"
    seed: int = 42

    @property
    def torch_dtype(self) -> torch.dtype:
        return getattr(torch, self.dtype, torch.float32)


@dataclass
class SampleResult:
    """Result for a single evaluation sample."""

    sample_id: str | int
    prompt: str
    generated: str
    reference: str
    correct: bool
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Aggregated result for a single benchmark."""

    benchmark_name: str
    num_samples: int
    num_correct: int
    accuracy: float
    metrics: dict[str, float] = field(default_factory=dict)
    samples: list[SampleResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Truncate per-sample details for summary
        d["samples"] = d["samples"][:10]  # keep first 10 for inspection
        return d


# ---------------------------------------------------------------------------
# Scoring utilities
# ---------------------------------------------------------------------------

def exact_match(prediction: str, reference: str, normalize: bool = True) -> bool:
    """Case-insensitive exact match with optional whitespace normalization."""
    if normalize:
        prediction = " ".join(prediction.strip().split())
        reference = " ".join(reference.strip().split())
    return prediction.lower() == reference.lower()


def accuracy_score(results: Sequence[SampleResult]) -> float:
    """Compute accuracy over a list of sample results."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.correct) / len(results)


def pass_at_k(
    num_samples: int,
    num_correct: int,
    k: int = 1,
) -> float:
    """
    Unbiased estimator of pass@k (Chen et al., 2021).

    Given n total samples and c correct ones, estimates the probability
    that at least one of k random draws is correct.
    """
    if num_samples - num_correct < k:
        return 1.0
    result = 1.0
    for i in range(k):
        result *= (num_samples - num_correct - i) / (num_samples - i)
    return 1.0 - result


# ---------------------------------------------------------------------------
# Abstract Benchmark
# ---------------------------------------------------------------------------

class Benchmark(ABC):
    """
    Base class for all benchmarks.

    Subclasses must implement:
    - ``load_dataset()`` → load/download dataset
    - ``build_prompt(sample, fewshot_examples)`` → format prompt string
    - ``score(sample, generated_text)`` → evaluate one sample

    The framework calls these methods; benchmarks never touch the model directly.
    """

    name: str = "base"

    @abstractmethod
    def load_dataset(self, split: str = "test") -> list[dict[str, Any]]:
        """Load and return dataset samples as list of dicts."""
        ...

    @abstractmethod
    def get_fewshot_examples(self, n: int) -> list[dict[str, Any]]:
        """Return n few-shot examples (from train/dev split)."""
        ...

    @abstractmethod
    def build_prompt(
        self,
        sample: dict[str, Any],
        fewshot_examples: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build the full prompt string for a sample, including few-shot prefix."""
        ...

    @abstractmethod
    def score(
        self,
        sample: dict[str, Any],
        generated_text: str,
    ) -> SampleResult:
        """Score a single generated output against the reference."""
        ...

    def get_max_new_tokens(self) -> int:
        """Override to customize max generation length per benchmark."""
        return 256


# ---------------------------------------------------------------------------
# Evaluator — orchestrates benchmark runs
# ---------------------------------------------------------------------------

class Evaluator:
    """
    Main evaluation orchestrator.

    Usage::

        evaluator = Evaluator(generator, tokenizer, config)
        results = evaluator.run()
        evaluator.save_results(results, output_dir)
    """

    def __init__(
        self,
        generator: GeneratorProtocol,
        tokenizer: TokenizerProtocol,
        config: EvalConfig,
    ):
        self.generator = generator
        self.tokenizer = tokenizer
        self.config = config

    def run_benchmark(self, benchmark: Benchmark) -> BenchmarkResult:
        """Run a single benchmark and return aggregated results."""
        start_time = time.time()

        # Load data
        dataset = benchmark.load_dataset(split="test")
        if self.config.max_samples is not None:
            dataset = dataset[: self.config.max_samples]

        # Few-shot examples
        fewshot = benchmark.get_fewshot_examples(self.config.num_fewshot)

        # Evaluate each sample
        sample_results: list[SampleResult] = []
        max_new_tokens = benchmark.get_max_new_tokens()

        for i, sample in enumerate(dataset):
            prompt = benchmark.build_prompt(sample, fewshot)

            # Tokenize
            prompt_ids = self.tokenizer.encode(prompt)
            prompt_tensor = torch.tensor([prompt_ids], dtype=torch.long)

            # Generate
            greedy = self.config.temperature == 0.0
            output_tensor = self.generator.generate(
                prompt_tensor,
                max_new_tokens=max_new_tokens,
                temperature=max(self.config.temperature, 1e-6),  # avoid div-by-zero
                greedy=greedy,
                eos_token_id=None,
            )

            # Decode only the generated part
            generated_ids = output_tensor[0, len(prompt_ids):].tolist()
            generated_text = self.tokenizer.decode(generated_ids)

            # Score
            result = benchmark.score(sample, generated_text)
            result.sample_id = i
            result.prompt = prompt
            result.generated = generated_text
            sample_results.append(result)

        elapsed = time.time() - start_time
        num_correct = sum(1 for r in sample_results if r.correct)

        return BenchmarkResult(
            benchmark_name=benchmark.name,
            num_samples=len(sample_results),
            num_correct=num_correct,
            accuracy=accuracy_score(sample_results),
            metrics={"accuracy": accuracy_score(sample_results)},
            samples=sample_results,
            elapsed_seconds=elapsed,
        )

    def run(self, benchmarks: list[Benchmark]) -> list[BenchmarkResult]:
        """Run all benchmarks and return a list of results."""
        results = []
        for benchmark in benchmarks:
            result = self.run_benchmark(benchmark)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @staticmethod
    def save_results(
        results: list[BenchmarkResult],
        output_dir: str | Path,
    ) -> tuple[Path, Path]:
        """
        Save results as JSON and Markdown report.

        Returns (json_path, md_path).
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # --- JSON ---
        json_path = output_dir / "results.json"
        json_data = {
            "results": [r.to_dict() for r in results],
            "summary": {
                r.benchmark_name: {
                    "accuracy": r.accuracy,
                    "num_samples": r.num_samples,
                    "num_correct": r.num_correct,
                    "elapsed_seconds": round(r.elapsed_seconds, 2),
                    **r.metrics,
                }
                for r in results
            },
        }
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

        # --- Markdown ---
        md_path = output_dir / "report.md"
        lines = ["# Evaluation Report\n"]
        lines.append("| Benchmark | Samples | Correct | Accuracy | Time (s) |")
        lines.append("|-----------|---------|---------|----------|----------|")
        for r in results:
            lines.append(
                f"| {r.benchmark_name} | {r.num_samples} | {r.num_correct} "
                f"| {r.accuracy:.4f} | {r.elapsed_seconds:.1f} |"
            )
        lines.append("")

        # Per-benchmark details
        for r in results:
            lines.append(f"## {r.benchmark_name}\n")
            if r.metrics:
                for k, v in r.metrics.items():
                    lines.append(f"- **{k}**: {v:.4f}")
            lines.append(f"- **Samples**: {r.num_samples}")
            lines.append(f"- **Correct**: {r.num_correct}")
            lines.append("")

        md_path.write_text("\n".join(lines))
        return json_path, md_path
