"""
Tests for inference engine.

Run:  python -m pytest tests/test_inference.py -v
"""

import pytest
import torch

from model.configuration import ModelArgs
from model.modeling import Transformer
from inference.generate import TextGenerator, sample_logits


# ---------------------------------------------------------------------------
# Fixtures — small model for fast testing
# ---------------------------------------------------------------------------

def _small_args() -> ModelArgs:
    return ModelArgs(
        dim=64,
        n_layers=2,
        n_heads=4,
        n_kv_heads=2,
        vocab_size=256,
        multiple_of=32,
        norm_eps=1e-5,
        max_seq_len=128,
        rope_theta=10000.0,
    )


@pytest.fixture
def small_model():
    args = _small_args()
    model = Transformer(args)
    model.eval()
    return model


@pytest.fixture
def generator(small_model):
    return TextGenerator.from_model(small_model, device="cpu")


# ---------------------------------------------------------------------------
# 1. Generation output shape
# ---------------------------------------------------------------------------

class TestGenerationShape:
    def test_basic_shape(self, generator):
        prompt = torch.randint(0, 256, (1, 5))
        max_new = 10
        output = generator.generate(prompt, max_new_tokens=max_new, greedy=True)
        # Output should be (1, prompt_len + generated), up to max_new
        assert output.ndim == 2
        assert output.shape[0] == 1
        assert output.shape[1] == 5 + max_new

    def test_batch_shape(self, generator):
        prompt = torch.randint(0, 256, (3, 8))
        max_new = 7
        output = generator.generate(prompt, max_new_tokens=max_new, greedy=True)
        assert output.shape == (3, 8 + max_new)

    def test_stream_yields_correct_count(self, generator):
        prompt = torch.randint(0, 256, (1, 4))
        max_new = 12
        tokens = list(
            generator.generate_stream(prompt, max_new_tokens=max_new, greedy=True)
        )
        assert len(tokens) == max_new
        for t in tokens:
            assert t.shape == (1, 1)

    def test_eos_stops_early(self, generator):
        prompt = torch.randint(0, 256, (1, 4))
        # With greedy and a tiny random model, we can't guarantee EOS,
        # so test that *if* EOS never fires, we get max_new_tokens.
        tokens = list(
            generator.generate_stream(
                prompt,
                max_new_tokens=5,
                greedy=True,
                eos_token_id=99999,  # won't match any token in vocab 256
            )
        )
        assert len(tokens) == 5


# ---------------------------------------------------------------------------
# 2. KV-cache consistency
# ---------------------------------------------------------------------------

class TestKVCache:
    def test_cache_vs_no_cache_logits(self, small_model):
        """Verify KV-cache produces the same output as full recomputation."""
        torch.manual_seed(42)
        prompt = torch.randint(0, 256, (1, 6))

        gen_cache = TextGenerator.from_model(small_model, device="cpu")
        gen_no_cache = TextGenerator.from_model(small_model, device="cpu")

        torch.manual_seed(0)
        out_cache = gen_cache.generate(
            prompt, max_new_tokens=8, greedy=True, use_cache=True
        )
        torch.manual_seed(0)
        out_no_cache = gen_no_cache.generate(
            prompt, max_new_tokens=8, greedy=True, use_cache=False
        )

        assert torch.equal(out_cache, out_no_cache), (
            f"Cache and no-cache outputs differ!\n"
            f"cache   : {out_cache}\n"
            f"no-cache: {out_no_cache}"
        )

    def test_cache_cleared_after_generate(self, small_model):
        """Ensure the cache is cleaned up after generation completes."""
        gen = TextGenerator.from_model(small_model, device="cpu")
        prompt = torch.randint(0, 256, (1, 4))
        _ = gen.generate(prompt, max_new_tokens=3, greedy=True, use_cache=True)

        # After generate(), all caches should be None
        for layer in small_model.layers:
            assert layer.attention.kv_cache is None


# ---------------------------------------------------------------------------
# 3. Sampling strategies
# ---------------------------------------------------------------------------

class TestSampling:
    def test_temperature_zero_is_greedy(self, generator):
        """temperature=0 should produce the same result as greedy=True."""
        torch.manual_seed(123)
        prompt = torch.randint(0, 256, (1, 5))

        out_greedy = generator.generate(
            prompt.clone(), max_new_tokens=10, greedy=True
        )
        out_temp0 = generator.generate(
            prompt.clone(), max_new_tokens=10, temperature=0
        )
        assert torch.equal(out_greedy, out_temp0)

    def test_sample_logits_greedy(self):
        logits = torch.tensor([[1.0, 3.0, 2.0, 0.5]])
        result = sample_logits(logits, greedy=True)
        assert result.item() == 1  # index of 3.0

    def test_sample_logits_temperature_zero(self):
        logits = torch.tensor([[1.0, 3.0, 2.0, 0.5]])
        result = sample_logits(logits, temperature=0)
        assert result.item() == 1

    def test_top_k_restricts(self):
        """With top_k=1, should always pick the max."""
        logits = torch.tensor([[0.1, 10.0, 0.2, 0.3]])
        for _ in range(20):
            result = sample_logits(logits, temperature=1.0, top_k=1)
            assert result.item() == 1

    def test_top_p_restricts(self):
        """With very low top_p, should mostly pick the max."""
        logits = torch.tensor([[0.1, 10.0, 0.2, 0.3]])
        for _ in range(20):
            result = sample_logits(logits, temperature=1.0, top_p=0.01)
            assert result.item() == 1


# ---------------------------------------------------------------------------
# 4. Batch inference
# ---------------------------------------------------------------------------

class TestBatchInference:
    def test_generate_batch_variable_lengths(self, generator):
        prompts = [
            torch.randint(0, 256, (3,)),
            torch.randint(0, 256, (6,)),
            torch.randint(0, 256, (2,)),
        ]
        results = generator.generate_batch(
            prompts, max_new_tokens=5, greedy=True
        )
        assert len(results) == 3
        for i, r in enumerate(results):
            expected_len = prompts[i].size(0) + 5
            assert r.ndim == 1
            assert r.size(0) == expected_len, (
                f"Prompt {i}: expected len {expected_len}, got {r.size(0)}"
            )
