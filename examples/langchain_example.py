#!/usr/bin/env python3
"""
MemGate × LangChain — Multi-User Knowledge Isolation Example
==============================================================

This example demonstrates how to use MemGate as a memory wrapper in
LangChain to enforce per-user knowledge isolation in multi-tenant AI
applications.

Scenario
--------
A shared AI assistant serves multiple users.  Each user has public and
private knowledge stored in MemGate's KnowledgeStore.  When the assistant
replies in a **group chat**, it must only reference public knowledge.
When replying in a **DM (direct message)**, it can use all of that user's
knowledge (public + private).

Key concepts
------------
1. **MemGateMemory** — A LangChain-compatible ``BaseMemory`` that loads
   context-appropriate knowledge items as conversation memory.
2. **MemGateOutputParser** — An output parser that reviews LLM responses
   for privacy violations before they reach the user.
3. **Multi-user flow** — Same assistant, different privacy boundaries
   depending on the channel.

Running
-------
This example runs entirely in **mock mode** (no API keys needed)::

    cd memgate/
    python3 examples/langchain_example.py

For real LLM usage, set ``OPENAI_API_KEY`` and uncomment the ChatOpenAI
sections.

Dependencies
------------
- ``memgate >= 0.3`` (this repo)
- ``langchain-core >= 0.1`` (optional — stubs provided for demo)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — allow running from examples/ without pip install
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from memgate.knowledge_store import KnowledgeStore, KnowledgeItem  # noqa: E402
from memgate.privacy_context import ChannelInfo, PrivacyContext  # noqa: E402
from memgate.privacy_review import PrivacyReviewer  # noqa: E402

# ---------------------------------------------------------------------------
# Try importing LangChain (gracefully degrade to stubs)
# ---------------------------------------------------------------------------
try:
    from langchain_core.output_parsers import BaseOutputParser
    from langchain_core.exceptions import OutputParserException

    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

    class BaseOutputParser:  # type: ignore[no-redef]
        """Stub for demo without langchain installed."""

        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class OutputParserException(Exception):  # type: ignore[no-redef]
        def __init__(self, msg="", *, observation=""):
            super().__init__(msg)
            self.observation = observation


# ═══════════════════════════════════════════════════════════════════════════
# 1) MemGateMemory — LangChain BaseMemory wrapper
# ═══════════════════════════════════════════════════════════════════════════


class MemGateMemory:
    """LangChain-compatible memory that loads context-filtered knowledge.

    In a real LangChain integration you would subclass ``BaseMemory``.
    Here we keep it simple to avoid hard dependency on langchain.

    Usage::

        memory = MemGateMemory(
            channel_id="group_123",
            channel_type="group",
            participants={"alice", "bob"},
        )

        # Get knowledge items visible in this context
        items = memory.load_memory_variables({})
        # → {"knowledge": "Alice knows Python (public)\\n..."}

        # Switch to DM — same user, more access
        memory.switch_context(channel_type="dm", participants={"alice"})
        items = memory.load_memory_variables({})
        # → includes Alice's private items too
    """

    memory_key: str = "knowledge"

    def __init__(
        self,
        *,
        channel_id: str = "default",
        channel_type: str = "dm",
        participants: set[str] | None = None,
        store: KnowledgeStore | None = None,
    ):
        self.channel_id = channel_id
        self.channel_type = channel_type
        self.participants = participants or set()
        self.store = store or KnowledgeStore()

    # -- LangChain interface ------------------------------------------------

    @property
    def memory_variables(self) -> list[str]:
        return [self.memory_key]

    def load_memory_variables(
        self, inputs: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """Return accessible knowledge as a formatted string."""
        channel = ChannelInfo(
            channel_id=self.channel_id,
            participants=self.participants,
            channel_type=self.channel_type,
        )
        ctx = PrivacyContext(channel, self.store)
        items = ctx.get_accessible_knowledge()

        if not items:
            return {self.memory_key: "(no knowledge available)"}

        lines = []
        for item in items:
            vis_tag = "🔓" if item.visibility == "public" else "🔒"
            lines.append(f"{vis_tag} [{item.category}] {item.content}")

        return {self.memory_key: "\n".join(lines)}

    def save_context(self, inputs: dict, outputs: dict) -> None:
        """No-op for now — MemGate knowledge is managed externally."""
        pass

    def clear(self) -> None:
        """No-op."""
        pass

    # -- Context switching --------------------------------------------------

    def switch_context(
        self,
        *,
        channel_id: str | None = None,
        channel_type: str | None = None,
        participants: set[str] | None = None,
    ) -> None:
        """Switch to a different channel / privacy context."""
        if channel_id is not None:
            self.channel_id = channel_id
        if channel_type is not None:
            self.channel_type = channel_type
        if participants is not None:
            self.participants = participants


# ═══════════════════════════════════════════════════════════════════════════
# 2) MemGateOutputParser — reviews LLM output
# ═══════════════════════════════════════════════════════════════════════════


class MemGateOutputParser(BaseOutputParser):
    """Output parser that blocks privacy violations.

    Wire this into a LangChain chain::

        chain = prompt | llm | MemGateOutputParser(
            participants={"alice", "bob"},
            channel_id="group_general",
        )
    """

    def __init__(
        self,
        *,
        participants: set[str] | None = None,
        channel_id: str = "default",
        reviewer: PrivacyReviewer | None = None,
    ):
        super().__init__()
        self.participants = participants or set()
        self.channel_id = channel_id
        self._reviewer = reviewer or PrivacyReviewer()

    def parse(self, text: str) -> str:
        result = self._reviewer.review(
            message=text,
            channel_id=self.channel_id,
            participants=self.participants,
            sender="assistant",
        )
        if result.passed:
            return text

        details = "; ".join(
            f"[{v.category}] {v.description}" for v in result.violations
        )
        raise OutputParserException(
            f"MemGate privacy violation: {details}",
            observation=(
                "Your response contained private information. "
                "Please regenerate without mentioning: "
                + ", ".join(v.category for v in result.violations)
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3) Demo — Multi-user scenario with mock data
# ═══════════════════════════════════════════════════════════════════════════


def setup_mock_knowledge(store: KnowledgeStore) -> None:
    """Populate the store with sample data for two users."""
    # ── Alice's knowledge ──
    alice_items = [
        ("I know Python and Rust", "skill", "public"),
        ("I have a meeting tomorrow at 3pm", "calendar", "private"),
        ("My phone number is 13812345678", "contact_private", "private"),
        ("I love hiking and photography #public", "preference", "public"),
    ]
    for content, category, visibility in alice_items:
        store.add(
            KnowledgeItem.from_dict(
                {
                    "user": "alice",
                    "content": content,
                    "category": category,
                    "visibility": visibility,
                    "source": "demo",
                }
            )
        )

    # ── Bob's knowledge ──
    bob_items = [
        ("I'm a frontend developer #public", "skill", "public"),
        ("My salary is $120,000", "finance", "private"),
        ("I enjoy playing chess #public", "preference", "public"),
        ("I have a dentist appointment next week", "calendar", "private"),
    ]
    for content, category, visibility in bob_items:
        store.add(
            KnowledgeItem.from_dict(
                {
                    "user": "bob",
                    "content": content,
                    "category": category,
                    "visibility": visibility,
                    "source": "demo",
                }
            )
        )


def main() -> None:
    import tempfile

    print("=" * 65)
    print("  MemGate × LangChain — Multi-User Knowledge Isolation Demo")
    print("=" * 65)

    # Set up a temporary knowledge store
    with tempfile.TemporaryDirectory() as tmpdir:
        store = KnowledgeStore(base_dir=Path(tmpdir))
        setup_mock_knowledge(store)

        memory = MemGateMemory(store=store)
        reviewer = PrivacyReviewer(store=store)
        parser = MemGateOutputParser(reviewer=reviewer)

        # ── Scenario 1: Alice's DM (private) ──
        print("\n╔══════════════════════════════════════════════════════╗")
        print("║  Scenario 1: Alice's DM — Full access               ║")
        print("╚══════════════════════════════════════════════════════╝")

        memory.switch_context(
            channel_id="dm_alice",
            channel_type="dm",
            participants={"alice"},
        )
        knowledge = memory.load_memory_variables({})
        print(f"\nAccessible knowledge:\n{knowledge['knowledge']}")

        # Output parser in DM mode — everything passes
        parser.participants = {"alice"}
        parser.channel_id = "dm_alice"
        try:
            out = parser.parse("Your meeting is tomorrow at 3pm.")
            print(f'\n✅ LLM output passed: "{out}"')
        except OutputParserException as e:
            print(f"\n🚫 Blocked: {e}")

        # ── Scenario 2: Group chat (Alice + Bob) ──
        print("\n╔══════════════════════════════════════════════════════╗")
        print("║  Scenario 2: Group chat — Public knowledge only      ║")
        print("╚══════════════════════════════════════════════════════╝")

        memory.switch_context(
            channel_id="group_team",
            channel_type="group",
            participants={"alice", "bob"},
        )
        knowledge = memory.load_memory_variables({})
        print(f"\nAccessible knowledge:\n{knowledge['knowledge']}")

        # Output parser in group mode — schedule info blocked
        parser.participants = {"alice", "bob"}
        parser.channel_id = "group_team"

        safe_msg = "Alice knows Python and Bob is a frontend developer."
        try:
            out = parser.parse(safe_msg)
            print(f'\n✅ Safe message passed: "{out}"')
        except OutputParserException as e:
            print(f"\n🚫 Blocked: {e}")

        unsafe_msg = "Alice has a meeting tomorrow at 3pm with the dentist."
        try:
            out = parser.parse(unsafe_msg)
            print(f'\n✅ Unsafe message passed: "{out}"')
        except OutputParserException as e:
            print(f"\n🚫 Blocked (expected): {e}")

        # ── Scenario 3: Bob's DM ──
        print("\n╔══════════════════════════════════════════════════════╗")
        print("║  Scenario 3: Bob's DM — His data only                ║")
        print("╚══════════════════════════════════════════════════════╝")

        memory.switch_context(
            channel_id="dm_bob",
            channel_type="dm",
            participants={"bob"},
        )
        knowledge = memory.load_memory_variables({})
        print(f"\nAccessible knowledge:\n{knowledge['knowledge']}")
        print("  (Note: Alice's items are NOT visible here)")

        # ── Summary ──
        print("\n" + "=" * 65)
        print("  Summary")
        print("=" * 65)
        print("""
  ┌─────────────┬──────────────────┬──────────────────┐
  │  Context    │  Knowledge       │  Output Filter   │
  ├─────────────┼──────────────────┼──────────────────┤
  │  Alice DM   │  All of Alice's  │  No filtering    │
  │  Group chat │  Public only     │  Blocks private  │
  │  Bob DM     │  All of Bob's    │  No filtering    │
  └─────────────┴──────────────────┴──────────────────┘

  In production, wire MemGateMemory into your LangChain chain's
  memory parameter, and MemGateOutputParser as the output parser.
""")

        # ── LangChain chain example (pseudo-code) ──
        print("  LangChain chain example (pseudo-code):")
        print("  ─────────────────────────────────────────")
        print("""
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate

    llm = ChatOpenAI(model="gpt-4o-mini")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant.\\n"
                   "Available knowledge:\\n{knowledge}"),
        ("human", "{input}"),
    ])

    memory = MemGateMemory(
        channel_id="group_123",
        channel_type="group",
        participants={"alice", "bob"},
    )

    parser = MemGateOutputParser(
        participants={"alice", "bob"},
        channel_id="group_123",
    )

    # Build the chain
    chain = prompt | llm | parser

    # Invoke with memory-injected knowledge
    knowledge = memory.load_memory_variables({})
    result = chain.invoke({
        "input": "Tell me about Alice",
        "knowledge": knowledge["knowledge"],
    })
""")


if __name__ == "__main__":
    main()
