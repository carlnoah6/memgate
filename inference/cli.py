#!/usr/bin/env python3
"""
CLI for text generation inference.

Usage:
    python -m inference.cli --model_path checkpoints/step-10000 --max_tokens 128

Interactive REPL starts by default when no --prompt is given.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

from inference.generate import TextGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Text generation inference CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model_path",
        type=str,
        required=True,
        help="Path to checkpoint file or directory.",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=128,
        help="Maximum number of new tokens to generate.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="Sampling temperature (0 = greedy).",
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=0,
        help="Top-k filtering (0 = disabled).",
    )
    parser.add_argument(
        "--top_p",
        type=float,
        default=1.0,
        help="Nucleus (top-p) filtering (1.0 = disabled).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device for inference (cpu / cuda / mps).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Single prompt (if omitted, enters REPL mode).",
    )
    parser.add_argument(
        "--eos_token_id",
        type=int,
        default=None,
        help="EOS token id to stop generation.",
    )
    parser.add_argument(
        "--no_cache",
        action="store_true",
        help="Disable KV-cache (slower, useful for debugging).",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start simple HTTP API server instead of REPL.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP API server.",
    )
    return parser.parse_args()


def tokenize_simple(text: str) -> torch.Tensor:
    """
    Naive char→id tokenizer for demo purposes.
    Replace with your real tokenizer.
    """
    ids = [ord(c) % 100000 for c in text]
    return torch.tensor([ids], dtype=torch.long)


def detokenize_simple(token_ids: torch.Tensor) -> str:
    """Inverse of tokenize_simple."""
    chars = []
    for tid in token_ids.view(-1).tolist():
        if 0 <= tid < 0x110000:
            try:
                chars.append(chr(tid))
            except (ValueError, OverflowError):
                chars.append("?")
        else:
            chars.append("?")
    return "".join(chars)


def run_single(gen: TextGenerator, prompt: str, args: argparse.Namespace) -> None:
    """Generate from a single prompt and print the result."""
    prompt_ids = tokenize_simple(prompt)
    greedy = args.temperature == 0

    print(">>> ", end="", flush=True)
    for tok in gen.generate_stream(
        prompt_ids,
        max_new_tokens=args.max_tokens,
        temperature=max(args.temperature, 1e-8),  # avoid /0
        top_k=args.top_k,
        top_p=args.top_p,
        greedy=greedy,
        eos_token_id=args.eos_token_id,
        use_cache=not args.no_cache,
    ):
        print(detokenize_simple(tok), end="", flush=True)
    print()


def repl(gen: TextGenerator, args: argparse.Namespace) -> None:
    """Interactive read-eval-print loop."""
    print("🔮 Inference REPL  (type 'quit' or Ctrl-D to exit)")
    print(f"   model  : {args.model_path}")
    print(f"   device : {args.device}")
    print(f"   temp={args.temperature}  top_k={args.top_k}  top_p={args.top_p}")
    print()

    while True:
        try:
            prompt = input("prompt> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if prompt.strip().lower() in ("quit", "exit"):
            break
        if not prompt.strip():
            continue
        run_single(gen, prompt, args)


def serve_http(gen: TextGenerator, args: argparse.Namespace) -> None:
    """Minimal HTTP JSON API for generation."""
    import json
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            prompt = body.get("prompt", "")
            max_tokens = body.get("max_tokens", args.max_tokens)
            temperature = body.get("temperature", args.temperature)
            top_k = body.get("top_k", args.top_k)
            top_p = body.get("top_p", args.top_p)

            prompt_ids = tokenize_simple(prompt)
            greedy = temperature == 0
            output = gen.generate(
                prompt_ids,
                max_new_tokens=max_tokens,
                temperature=max(temperature, 1e-8),
                top_k=top_k,
                top_p=top_p,
                greedy=greedy,
                use_cache=not args.no_cache,
            )
            text = detokenize_simple(output[0])
            resp = json.dumps({"text": text}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, fmt, *a):
            pass  # suppress default logging

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"🌐 Serving on http://0.0.0.0:{args.port}  (POST /)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


def main() -> None:
    args = parse_args()

    print(f"Loading model from {args.model_path} …")
    gen = TextGenerator.from_checkpoint(
        args.model_path,
        device=args.device,
    )
    print("Model loaded.\n")

    if args.serve:
        serve_http(gen, args)
    elif args.prompt:
        run_single(gen, args.prompt, args)
    else:
        repl(gen, args)


if __name__ == "__main__":
    main()
