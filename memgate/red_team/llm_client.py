"""
LLM Client — Unified LLM API Interface

Supports OpenAI (GPT-4) and Anthropic (Claude) formats.
"""

import requests
from typing import List, Dict


class LLMClient:
    """
    Unified LLM client.

    Args:
        api_base: API base URL
        api_key: API key
        provider: "openai" or "anthropic" (defaults to auto-detection; falls back to openai if detection fails)
    """

    def __init__(self, api_base: str, api_key: str, provider: str = "auto"):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key

        if provider == "auto":
            if (
                "anthropic" in api_base
                or "claude" in api_base
                or "antigravity" in api_base
            ):
                self.provider = "anthropic"
            else:
                self.provider = "openai"
        else:
            self.provider = provider.lower()

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-opus-20240229",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Call the LLM to generate a response."""
        if self.provider == "anthropic":
            return self._call_anthropic(messages, model, temperature, max_tokens)
        else:
            return self._call_openai(messages, model, temperature, max_tokens)

    def _call_openai(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # OpenAI style payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[Error calling OpenAI API: {str(e)}]"

    def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        # Anthropic Messages API path usually ends in /messages
        # If base url ends in /v1, we might need to adjust, but standard is /v1/messages
        if self.api_base.endswith("/v1"):
            url = f"{self.api_base}/messages"
        elif self.api_base.endswith("/api"):  # For antigravity proxy
            url = f"{self.api_base}/anthropic-messages"  # Try specific endpoint or just messages?
            # Let's assume standard /messages for now, user can adjust base_url
            url = f"{self.api_base}/messages"
        else:
            url = f"{self.api_base}/messages"

        # Convert messages to Anthropic format
        # System prompt is separate
        system_msg = ""
        anthropic_messages = []

        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                anthropic_messages.append({"role": m["role"], "content": m["content"]})

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_msg:
            payload["system"] = system_msg

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)

            # Handle proxy-specific errors or try to fallback?
            # If 404, maybe it's not /messages?
            if resp.status_code == 404:
                # Fallback for some proxies that map root to messages
                if self.api_base.endswith("/messages"):
                    # Already tried, maybe just post to base?
                    pass

            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
        except Exception as e:
            return f"[Error calling Anthropic API: {str(e)}]"
