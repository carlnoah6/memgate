"""
Text generation inference engine with KV-cache, sampling strategies, batch
inference, and streaming support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator, List, Optional, Union

import torch
import torch.nn.functional as F

from model.configuration import ModelArgs
from model.modeling import Transformer


# ---------------------------------------------------------------------------
# Sampling utilities
# ---------------------------------------------------------------------------

def _apply_temperature(logits: torch.Tensor, temperature: float) -> torch.Tensor:
    """Scale logits by temperature (must be > 0)."""
    if temperature <= 0:
        raise ValueError("temperature must be > 0.  Use greedy=True for argmax.")
    return logits / temperature


def _top_k_filter(logits: torch.Tensor, k: int) -> torch.Tensor:
    """Zero-out logits outside top-k."""
    if k <= 0 or k >= logits.size(-1):
        return logits
    topk_vals, _ = torch.topk(logits, k, dim=-1)
    threshold = topk_vals[..., -1:]
    return logits.masked_fill(logits < threshold, float("-inf"))


def _top_p_filter(logits: torch.Tensor, p: float) -> torch.Tensor:
    """Nucleus (top-p) filtering."""
    if p >= 1.0:
        return logits
    sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
    # Mask tokens with cumulative prob above p (keep at least one)
    mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) >= p
    sorted_logits[mask] = float("-inf")
    # Unsort: scatter the filtered sorted_logits back into original positions
    output = torch.empty_like(logits)
    output.scatter_(-1, sorted_indices, sorted_logits)
    return output


def sample_logits(
    logits: torch.Tensor,
    temperature: float = 1.0,
    top_k: int = 0,
    top_p: float = 1.0,
    greedy: bool = False,
) -> torch.Tensor:
    """
    Sample next-token ids from logits ``(batch, vocab)``.

    Returns tensor of shape ``(batch, 1)``.
    """
    if greedy or temperature == 0:
        return logits.argmax(dim=-1, keepdim=True)

    logits = _apply_temperature(logits, temperature)
    logits = _top_k_filter(logits, top_k)
    logits = _top_p_filter(logits, top_p)
    probs = F.softmax(logits, dim=-1)
    return torch.multinomial(probs, num_samples=1)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class TextGenerator:
    """
    Wraps a :class:`Transformer` model and provides high-level generation
    utilities with KV-cache acceleration.

    Usage::

        gen = TextGenerator.from_checkpoint("checkpoints/step-10000")
        tokens = gen.generate(prompt_ids, max_new_tokens=128)

        # Streaming
        for tok in gen.generate_stream(prompt_ids, max_new_tokens=128):
            print(tok, end="", flush=True)
    """

    def __init__(
        self,
        model: Transformer,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ):
        self.model = model
        self.device = torch.device(device)
        self.dtype = dtype
        self.model.to(self.device)
        self.model.eval()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str | Path,
        device: str = "cpu",
        dtype: torch.dtype = torch.float32,
        model_args_override: dict | None = None,
    ) -> "TextGenerator":
        """
        Load a ``TextGenerator`` from a saved checkpoint directory or file.

        The checkpoint is expected to be either:
        * A directory containing ``model_args.json`` and ``model.pt``, **or**
        * A single ``.pt`` file that is a dict with keys ``model_args`` and
          ``model_state_dict``.
        """
        checkpoint_path = Path(checkpoint_path)

        if checkpoint_path.is_dir():
            args_file = checkpoint_path / "model_args.json"
            if args_file.exists():
                with open(args_file) as f:
                    args_dict = json.load(f)
            else:
                args_dict = {}
            state_path = checkpoint_path / "model.pt"
            state_dict = torch.load(state_path, map_location=device, weights_only=True)
        else:
            ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
            args_dict = ckpt.get("model_args", {})
            state_dict = ckpt.get("model_state_dict", ckpt)

        if model_args_override:
            args_dict.update(model_args_override)

        model_args = ModelArgs(**args_dict)
        model = Transformer(model_args)
        model.load_state_dict(state_dict, strict=False)
        return cls(model, device=device, dtype=dtype)

    @classmethod
    def from_model(
        cls,
        model: Transformer,
        device: str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> "TextGenerator":
        """Wrap an already-instantiated model."""
        return cls(model, device=device, dtype=dtype)

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    @torch.inference_mode()
    def generate(
        self,
        prompt_tokens: torch.Tensor,
        max_new_tokens: int = 128,
        temperature: float = 1.0,
        top_k: int = 0,
        top_p: float = 1.0,
        greedy: bool = False,
        eos_token_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> torch.Tensor:
        """
        Generate token ids autoregressively.

        Args:
            prompt_tokens: ``(batch, prompt_len)`` int tensor of prompt ids.
            max_new_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature.
            top_k: Top-k filtering (0 = disabled).
            top_p: Nucleus filtering (1.0 = disabled).
            greedy: If ``True``, always pick argmax.
            eos_token_id: Stop early if this token is emitted by all seqs.
            use_cache: Use KV-cache for acceleration.

        Returns:
            ``(batch, prompt_len + generated_len)`` tensor including the prompt.
        """
        tokens = list(
            self.generate_stream(
                prompt_tokens,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                greedy=greedy,
                eos_token_id=eos_token_id,
                use_cache=use_cache,
            )
        )
        if len(tokens) == 0:
            return prompt_tokens
        return torch.cat([prompt_tokens.to(self.device)] + tokens, dim=-1)

    @torch.inference_mode()
    def generate_stream(
        self,
        prompt_tokens: torch.Tensor,
        max_new_tokens: int = 128,
        temperature: float = 1.0,
        top_k: int = 0,
        top_p: float = 1.0,
        greedy: bool = False,
        eos_token_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> Generator[torch.Tensor, None, None]:
        """
        Streaming token generator – yields one ``(batch, 1)`` tensor per step.
        """
        prompt_tokens = prompt_tokens.to(self.device)
        bsz, prompt_len = prompt_tokens.shape
        total_len = prompt_len + max_new_tokens

        if use_cache:
            self.model.init_cache(bsz, total_len, self.device, self.dtype)

        try:
            # ---------- Prefill ----------
            if use_cache:
                logits = self.model(prompt_tokens, start_pos=0, use_cache=True)
            else:
                logits = self.model(prompt_tokens)
            next_logits = logits[:, -1, :]  # (batch, vocab)
            cur_pos = prompt_len

            all_tokens: List[torch.Tensor] = []

            for _ in range(max_new_tokens):
                next_token = sample_logits(
                    next_logits,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    greedy=greedy,
                )  # (batch, 1)

                yield next_token

                # Check EOS
                if eos_token_id is not None and (next_token == eos_token_id).all():
                    break

                # ---------- Decode step ----------
                if use_cache:
                    logits = self.model(next_token, start_pos=cur_pos, use_cache=True)
                else:
                    all_tokens.append(next_token)
                    full_seq = torch.cat([prompt_tokens] + all_tokens, dim=-1)
                    logits = self.model(full_seq)

                next_logits = logits[:, -1, :]
                cur_pos += 1
        finally:
            if use_cache:
                self.model.clear_cache()

    # ------------------------------------------------------------------
    # Batch convenience
    # ------------------------------------------------------------------

    @torch.inference_mode()
    def generate_batch(
        self,
        prompts: List[torch.Tensor],
        max_new_tokens: int = 128,
        pad_token_id: int = 0,
        **sampling_kwargs,
    ) -> List[torch.Tensor]:
        """
        Generate for a list of variable-length prompts by padding to the
        longest and running a single batched forward pass.

        Returns a list of 1-D tensors (padding stripped).
        """
        max_prompt_len = max(p.size(-1) for p in prompts)
        batch = torch.full(
            (len(prompts), max_prompt_len),
            pad_token_id,
            dtype=torch.long,
            device=self.device,
        )
        prompt_lengths: List[int] = []
        for i, p in enumerate(prompts):
            p = p.view(-1)
            prompt_lengths.append(p.size(0))
            batch[i, max_prompt_len - p.size(0):] = p  # right-align (left-pad)

        result = self.generate(
            batch,
            max_new_tokens=max_new_tokens,
            use_cache=False,  # padding + cache is tricky; keep simple
            **sampling_kwargs,
        )

        outputs: List[torch.Tensor] = []
        for i, plen in enumerate(prompt_lengths):
            start = max_prompt_len - plen
            outputs.append(result[i, start:])
        return outputs
