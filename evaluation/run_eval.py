#!/usr/bin/env python3
"""
Evaluation CLI — run benchmarks against a trained model.

Usage:
    python -m evaluation.run_eval \
        --model_path checkpoints/step-10000 \
        --benchmarks mmlu gsm8k humaneval \
        --num_fewshot 5 \
        --output_dir eval_results/run1

    # Quick test with synthetic data:
    python -m evaluation.run_eval --benchmarks mmlu --max_samples 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from evaluation import BENCHMARK_REGISTRY
from evaluation.evaluator import Evaluator, EvalConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run evaluation benchmarks on a language model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model_path",
        type=str,
        default="",
        help="Path to model checkpoint (directory or .pt file). "
             "If empty, a dummy model is used for testing.",
    )
    parser.add_argument(
        "--benchmarks",
        type=str,
        nargs="+",
        default=["mmlu"],
        choices=list(BENCHMARK_REGISTRY.keys()),
        help="Benchmarks to run (default: mmlu).",
    )
    parser.add_argument(
        "--num_fewshot",
        type=int,
        default=0,
        help="Number of few-shot examples (default: 0).",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="eval_results",
        help="Directory for results output.",
    )
    parser.add_argument(
        "--max_samples",
        type=int,
        default=None,
        help="Limit number of samples per benchmark (for quick testing).",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1,
        help="Batch size for generation.",
    )
    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=256,
        help="Maximum tokens to generate per sample.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (0.0 = greedy).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device for inference (cpu, cuda, cuda:0, etc.).",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        default="float32",
        choices=["float32", "float16", "bfloat16"],
        help="Model dtype.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Dummy model/tokenizer for testing without a real checkpoint
# ---------------------------------------------------------------------------

class DummyTokenizer:
    """Minimal tokenizer that maps characters to ints."""

    def encode(self, text: str) -> list[int]:
        return [ord(c) % 256 for c in text]

    def decode(self, token_ids: list[int] | torch.Tensor) -> str:
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.tolist()
        return "".join(chr(max(32, t % 128)) for t in token_ids)


class DummyGenerator:
    """Generator that returns random tokens — for testing the framework."""

    def __init__(self, vocab_size: int = 256, seed: int = 42):
        self.vocab_size = vocab_size
        self.rng = torch.Generator()
        self.rng.manual_seed(seed)

    def generate(
        self,
        prompt_tokens: torch.Tensor,
        max_new_tokens: int = 128,
        **kwargs,
    ) -> torch.Tensor:
        bsz, prompt_len = prompt_tokens.shape
        new_tokens = torch.randint(
            32, self.vocab_size,
            (bsz, max_new_tokens),
            generator=self.rng,
        )
        return torch.cat([prompt_tokens, new_tokens], dim=-1)


def load_model_and_tokenizer(config: EvalConfig):
    """Load the model and tokenizer from checkpoint, or return dummies."""
    if config.model_path:
        from inference.generate import TextGenerator
        from model.configuration import ModelArgs

        generator = TextGenerator.from_checkpoint(
            config.model_path,
            device=config.device,
            dtype=config.torch_dtype,
        )

        # Try to load tokenizer
        ckpt_path = Path(config.model_path)
        tokenizer_path = ckpt_path / "tokenizer.json" if ckpt_path.is_dir() else None
        if tokenizer_path and tokenizer_path.exists():
            try:
                from tokenizers import Tokenizer  # type: ignore
                tok = Tokenizer.from_file(str(tokenizer_path))

                class HFTokenizerWrapper:
                    def __init__(self, tok):
                        self._tok = tok
                    def encode(self, text: str) -> list[int]:
                        return self._tok.encode(text).ids
                    def decode(self, ids) -> str:
                        if isinstance(ids, torch.Tensor):
                            ids = ids.tolist()
                        return self._tok.decode(ids)

                return generator, HFTokenizerWrapper(tok)
            except ImportError:
                pass

        print("[WARN] No tokenizer found, using DummyTokenizer", file=sys.stderr)
        return generator, DummyTokenizer()

    print("[INFO] No model_path provided, using DummyGenerator for testing", file=sys.stderr)
    return DummyGenerator(seed=config.seed), DummyTokenizer()


def main():
    args = parse_args()

    config = EvalConfig(
        model_path=args.model_path,
        benchmarks=args.benchmarks,
        num_fewshot=args.num_fewshot,
        output_dir=args.output_dir,
        max_samples=args.max_samples,
        batch_size=args.batch_size,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        device=args.device,
        dtype=args.dtype,
        seed=args.seed,
    )

    # Set seed
    torch.manual_seed(config.seed)

    # Load model
    generator, tokenizer = load_model_and_tokenizer(config)

    # Instantiate benchmarks
    benchmarks = []
    for name in config.benchmarks:
        cls = BENCHMARK_REGISTRY[name]
        benchmarks.append(cls())

    # Run evaluation
    evaluator = Evaluator(generator, tokenizer, config)
    print(f"Running benchmarks: {config.benchmarks}")
    print(f"  Few-shot: {config.num_fewshot}")
    print(f"  Max samples: {config.max_samples or 'all'}")
    print(f"  Output: {config.output_dir}")
    print()

    results = evaluator.run(benchmarks)

    # Save
    json_path, md_path = Evaluator.save_results(results, config.output_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    for r in results:
        print(f"  {r.benchmark_name:12s}  acc={r.accuracy:.4f}  "
              f"({r.num_correct}/{r.num_samples})  {r.elapsed_seconds:.1f}s")
    print("=" * 60)
    print(f"\nResults saved to: {json_path}")
    print(f"Report saved to:  {md_path}")


if __name__ == "__main__":
    main()
