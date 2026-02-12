import math
from typing import Optional, Tuple, List

import torch
import torch.nn as nn
import torch.nn.functional as F

from model.configuration import ModelArgs

class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def _norm(self, x):
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)

    def forward(self, x):
        output = self._norm(x.float()).type_as(x)
        return output * self.weight

def precompute_freqs_cis(dim: int, end: int, theta: float = 10000.0):
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
    t = torch.arange(end, device=freqs.device, dtype=torch.float32)
    freqs = torch.outer(t, freqs)
    freqs_cis = torch.polar(torch.ones_like(freqs), freqs)  # complex64
    return freqs_cis

def reshape_for_broadcast(freqs_cis: torch.Tensor, x: torch.Tensor):
    ndim = x.ndim
    assert 0 <= 1 < ndim
    assert freqs_cis.shape == (x.shape[1], x.shape[-1])
    shape = [d if i == 1 or i == ndim - 1 else 1 for i, d in enumerate(x.shape)]
    return freqs_cis.view(*shape)

def apply_rotary_emb(xq: torch.Tensor, xk: torch.Tensor, freqs_cis: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    xq_ = torch.view_as_complex(xq.float().reshape(*xq.shape[:-1], -1, 2))
    xk_ = torch.view_as_complex(xk.float().reshape(*xk.shape[:-1], -1, 2))
    freqs_cis = reshape_for_broadcast(freqs_cis, xq_)
    xq_out = torch.view_as_real(xq_ * freqs_cis).flatten(3)
    xk_out = torch.view_as_real(xk_ * freqs_cis).flatten(3)
    return xq_out.type_as(xq), xk_out.type_as(xk)

class KVCache:
    """Key-Value cache for efficient autoregressive generation."""

    def __init__(self, batch_size: int, max_seq_len: int, n_kv_heads: int,
                 head_dim: int, device: torch.device, dtype: torch.dtype = torch.float32):
        self.cache_k = torch.zeros(batch_size, n_kv_heads, max_seq_len, head_dim,
                                   device=device, dtype=dtype)
        self.cache_v = torch.zeros(batch_size, n_kv_heads, max_seq_len, head_dim,
                                   device=device, dtype=dtype)
        self.seq_len = 0

    def update(self, k: torch.Tensor, v: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Append new K/V to cache and return full K/V tensors."""
        bsz, n_kv_heads, seqlen, head_dim = k.shape
        self.cache_k[:bsz, :, self.seq_len:self.seq_len + seqlen, :] = k
        self.cache_v[:bsz, :, self.seq_len:self.seq_len + seqlen, :] = v
        self.seq_len += seqlen
        return self.cache_k[:bsz, :, :self.seq_len, :], self.cache_v[:bsz, :, :self.seq_len, :]

    def reset(self):
        self.cache_k.zero_()
        self.cache_v.zero_()
        self.seq_len = 0


class Attention(nn.Module):
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.n_kv_heads = args.n_heads if args.n_kv_heads is None else args.n_kv_heads
        self.n_heads = args.n_heads
        self.n_rep = self.n_heads // self.n_kv_heads
        self.head_dim = args.dim // args.n_heads

        self.wq = nn.Linear(args.dim, args.n_heads * self.head_dim, bias=False)
        self.wk = nn.Linear(args.dim, self.n_kv_heads * self.head_dim, bias=False)
        self.wv = nn.Linear(args.dim, self.n_kv_heads * self.head_dim, bias=False)
        self.wo = nn.Linear(args.n_heads * self.head_dim, args.dim, bias=False)

        self.kv_cache: Optional[KVCache] = None

    def forward(
        self,
        x: torch.Tensor,
        freqs_cis: torch.Tensor,
        use_cache: bool = False,
    ):
        bsz, seqlen, _ = x.shape
        xq, xk, xv = self.wq(x), self.wk(x), self.wv(x)

        xq = xq.view(bsz, seqlen, self.n_heads, self.head_dim)
        xk = xk.view(bsz, seqlen, self.n_kv_heads, self.head_dim)
        xv = xv.view(bsz, seqlen, self.n_kv_heads, self.head_dim)

        xq, xk = apply_rotary_emb(xq, xk, freqs_cis=freqs_cis)

        # Transpose for SDPA: (bsz, n_heads, seqlen, head_dim)
        xq = xq.transpose(1, 2)
        xk = xk.transpose(1, 2)
        xv = xv.transpose(1, 2)

        # Use KV-cache if available
        if use_cache and self.kv_cache is not None:
            xk, xv = self.kv_cache.update(xk, xv)
            # When using cache, only the new query attends to all cached K/V
            # Not causal in the SDPA sense since full K/V is explicitly managed
            is_causal = seqlen > 1  # Prefill is causal; single-token decode is not
        else:
            is_causal = True

        # GQA: Repeat KV heads if necessary
        total_kv_len = xk.shape[2]
        if self.n_rep > 1:
            xk = xk[:, :, None, :, :].expand(bsz, self.n_kv_heads, self.n_rep, total_kv_len, self.head_dim).reshape(bsz, self.n_heads, total_kv_len, self.head_dim)
            xv = xv[:, :, None, :, :].expand(bsz, self.n_kv_heads, self.n_rep, total_kv_len, self.head_dim).reshape(bsz, self.n_heads, total_kv_len, self.head_dim)

        # Flash Attention
        output = F.scaled_dot_product_attention(xq, xk, xv, is_causal=is_causal)

        output = output.transpose(1, 2).contiguous().view(bsz, seqlen, -1)
        return self.wo(output)

    def init_cache(self, batch_size: int, max_seq_len: int, device: torch.device,
                   dtype: torch.dtype = torch.float32):
        self.kv_cache = KVCache(batch_size, max_seq_len, self.n_kv_heads,
                                self.head_dim, device, dtype)

    def clear_cache(self):
        if self.kv_cache is not None:
            self.kv_cache.reset()
        self.kv_cache = None

class FeedForward(nn.Module):
    def __init__(self, args: ModelArgs):
        super().__init__()
        
        hidden_dim = 4 * args.dim
        hidden_dim = int(2 * hidden_dim / 3)
        if args.ffn_dim_multiplier is not None:
            hidden_dim = int(args.ffn_dim_multiplier * hidden_dim)
        hidden_dim = args.multiple_of * ((hidden_dim + args.multiple_of - 1) // args.multiple_of)

        self.w1 = nn.Linear(args.dim, hidden_dim, bias=False)
        self.w2 = nn.Linear(hidden_dim, args.dim, bias=False)
        self.w3 = nn.Linear(args.dim, hidden_dim, bias=False)

    def forward(self, x):
        return self.w2(F.silu(self.w1(x)) * self.w3(x))

class TransformerBlock(nn.Module):
    def __init__(self, layer_id: int, args: ModelArgs):
        super().__init__()
        self.n_heads = args.n_heads
        self.dim = args.dim
        self.head_dim = args.dim // args.n_heads
        self.attention = Attention(args)
        self.feed_forward = FeedForward(args)
        self.attention_norm = RMSNorm(args.dim, eps=args.norm_eps)
        self.ffn_norm = RMSNorm(args.dim, eps=args.norm_eps)

    def forward(
        self,
        x: torch.Tensor,
        freqs_cis: torch.Tensor,
        use_cache: bool = False,
    ):
        h = x + self.attention(self.attention_norm(x), freqs_cis, use_cache=use_cache)
        out = h + self.feed_forward(self.ffn_norm(h))
        return out

class Transformer(nn.Module):
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args
        self.vocab_size = args.vocab_size
        self.n_layers = args.n_layers
        self.tok_embeddings = nn.Embedding(args.vocab_size, args.dim)

        self.layers = torch.nn.ModuleList()
        for layer_id in range(args.n_layers):
            self.layers.append(TransformerBlock(layer_id, args))

        self.norm = RMSNorm(args.dim, eps=args.norm_eps)
        self.output = nn.Linear(args.dim, args.vocab_size, bias=False)

        # Precompute freqs_cis
        self.freqs_cis = precompute_freqs_cis(
            self.args.dim // self.args.n_heads,
            self.args.max_seq_len * 2,
            self.args.rope_theta
        )

    def forward(self, tokens: torch.Tensor, start_pos: int = 0, use_cache: bool = False):
        bsz, seqlen = tokens.shape
        h = self.tok_embeddings(tokens)
        
        # Ensure freqs_cis is on the correct device and sliced for current position range
        freqs_cis = self.freqs_cis[start_pos:start_pos + seqlen].to(h.device)

        for layer in self.layers:
            h = layer(h, freqs_cis, use_cache=use_cache)
            
        h = self.norm(h)
        output = self.output(h)
        return output

    def init_cache(self, batch_size: int, max_seq_len: int, device: torch.device,
                   dtype: torch.dtype = torch.float32):
        """Initialize KV-cache for all layers."""
        for layer in self.layers:
            layer.attention.init_cache(batch_size, max_seq_len, device, dtype)

    def clear_cache(self):
        """Clear KV-cache for all layers."""
        for layer in self.layers:
            layer.attention.clear_cache()
