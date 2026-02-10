#!/usr/bin/env python3
"""
MemGate × OpenAI SDK — Context-Filtered Chat Completion
=========================================================

This example demonstrates how to use MemGate with the OpenAI Python SDK
(or any OpenAI-compatible API) to filter knowledge context before it
reaches the LLM and review responses before they reach the user.

Architecture
------------
::

    ┌─────────────────────────────────────────────────────────┐
    │                   Your Application                      │
    │                                                         │
    │   User query ──→ MemGate Context Filter ──→ LLM call   │
    │                  (inject safe knowledge)                │
    │                                                         │
    │   LLM reply  ──→ MemGate Output Review ──→ User        │
    │                  (block private leaks)                  │
    └─────────────────────────────────────────────────────────┘

Two layers of protection:

1. **Pre-call** — ``PrivacyContext`` filters the knowledge that gets
   injected into the system prompt, so the LLM never *sees* private data
   in group contexts.
2. **Post-call** — ``PrivacyReviewer`` scans the LLM's response for any
   accidental privacy leaks (e.g., hallucinated schedule info).

Running
-------
This example runs in **mock mode** (no API key needed)::

    cd memgate/
    python3 examples/openai_example.py

To test with a real LLM, set ``OPENAI_API_KEY`` and change
``USE_MOCK_LLM = False`` below.

Dependencies
------------
- ``memgate >= 0.3`` (this repo)
- ``openai >= 1.0`` (optional — mock provided for demo)
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from memgate.knowledge_store import KnowledgeStore, KnowledgeItem  # noqa: E402
from memgate.privacy_context import ChannelInfo, PrivacyContext  # noqa: E402
from memgate.privacy_review import PrivacyReviewer, ReviewResult  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
USE_MOCK_LLM = True  # Set to False to use real OpenAI API
MAX_RETRIES = 2


# ═══════════════════════════════════════════════════════════════════════════
# Mock LLM (for demo without API key)
# ═══════════════════════════════════════════════════════════════════════════


class MockLLM:
    """Simulates OpenAI chat completions for demo purposes."""

    RESPONSES = {
        "default": "I'm happy to help! What would you like to know?",
        "alice_skills": "Based on what I know, Alice is proficient in Python and Rust. She also enjoys hiking and photography.",
        "alice_schedule": "Alice has a meeting tomorrow at 3pm. She also has a dentist appointment next week.",
        "bob_finance": "Bob's salary is $120,000 per year and he has investments in index funds.",
        "safe_alice": "Alice is a skilled developer who knows Python and Rust. She enjoys hiking in her free time.",
    }

    def chat_complete(self, messages: list[dict], **kwargs) -> str:
        """Mock chat completion — picks response based on last user message."""
        last_user = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user = m["content"].lower()
                break

        if "schedule" in last_user or "meeting" in last_user or "日程" in last_user:
            return self.RESPONSES["alice_schedule"]
        if "salary" in last_user or "finance" in last_user or "薪水" in last_user:
            return self.RESPONSES["bob_finance"]
        if "alice" in last_user and "skill" in last_user:
            return self.RESPONSES["alice_skills"]
        if "alice" in last_user:
            return self.RESPONSES["safe_alice"]
        return self.RESPONSES["default"]


# ═══════════════════════════════════════════════════════════════════════════
# PrivacyChatClient — the main integration class
# ═══════════════════════════════════════════════════════════════════════════


class PrivacyChatClient:
    """OpenAI chat client with MemGate privacy enforcement.

    This class wraps the OpenAI SDK (or mock) and provides:
    - Context-filtered knowledge injection
    - Post-response privacy review
    - Auto-retry on violation

    Example::

        client = PrivacyChatClient(
            channel_id="group_team",
            channel_type="group",
            participants={"alice", "bob"},
        )

        reply = client.chat("Tell me about Alice's skills")
        # → Only uses public knowledge, blocks private info
    """

    def __init__(
        self,
        *,
        channel_id: str = "default",
        channel_type: str = "dm",
        participants: set[str] | None = None,
        store: KnowledgeStore | None = None,
        reviewer: PrivacyReviewer | None = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        max_retries: int = MAX_RETRIES,
    ):
        self.channel_id = channel_id
        self.channel_type = channel_type
        self.participants = participants or set()
        self.store = store or KnowledgeStore()
        self.reviewer = reviewer or PrivacyReviewer(store=self.store)
        self.model = model
        self.max_retries = max_retries

        # LLM backend
        if USE_MOCK_LLM:
            self._llm = MockLLM()
        else:
            import openai

            self._client = openai.OpenAI(api_key=api_key)

    def _get_privacy_context(self) -> PrivacyContext:
        """Build a PrivacyContext for the current channel."""
        channel = ChannelInfo(
            channel_id=self.channel_id,
            participants=self.participants,
            channel_type=self.channel_type,
        )
        return PrivacyContext(channel, self.store)

    def _build_system_prompt(self, ctx: PrivacyContext) -> str:
        """Build a system prompt with context-filtered knowledge."""
        # Get only the knowledge items visible in this context
        items = ctx.get_accessible_knowledge()

        knowledge_block = ""
        if items:
            lines = []
            for item in items:
                lines.append(f"- [{item.user}] {item.content} ({item.category})")
            knowledge_block = (
                "\n\nAvailable knowledge about participants:\n" + "\n".join(lines)
            )

        # Get privacy context summary
        privacy_note = ctx.get_context_summary()

        return textwrap.dedent(f"""\
            You are a helpful assistant. {privacy_note}
            {knowledge_block}

            IMPORTANT: In group chats, never reveal private information such as
            schedules, financial details, family info, or contact details.
            Only reference the knowledge items listed above.""")

    def _call_llm(self, messages: list[dict]) -> str:
        """Call the LLM (mock or real)."""
        if USE_MOCK_LLM:
            return self._llm.chat_complete(messages)
        else:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content

    def _review_response(self, text: str) -> ReviewResult:
        """Review a response through MemGate."""
        return self.reviewer.review(
            message=text,
            channel_id=self.channel_id,
            participants=self.participants,
            sender="assistant",
        )

    def chat(self, user_message: str) -> dict:
        """Send a message and get a privacy-reviewed response.

        Returns::

            {
                "reply": "...",          # The (safe) response text
                "passed": True/False,    # Whether the original passed review
                "attempts": 1,           # Number of LLM calls made
                "context_mode": "group", # Privacy context type
                "knowledge_count": 4,    # Number of knowledge items injected
            }
        """
        ctx = self._get_privacy_context()
        system_prompt = self._build_system_prompt(ctx)
        knowledge_items = ctx.get_accessible_knowledge()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(1, self.max_retries + 2):
            reply = self._call_llm(messages)
            result = self._review_response(reply)

            if result.passed:
                return {
                    "reply": reply,
                    "passed": True,
                    "attempts": attempt,
                    "context_mode": self.channel_type,
                    "knowledge_count": len(knowledge_items),
                }

            # Violation detected — retry with correction
            categories = [v.category for v in result.violations]
            print(
                f"  ⚠️  Attempt {attempt}: violation in {categories}, retrying...",
                file=sys.stderr,
            )

            messages.append({"role": "assistant", "content": reply})
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Your response contained private information "
                        f"({', '.join(categories)}) that must not be shared. "
                        f"Please regenerate without any private details."
                    ),
                }
            )

        # All retries exhausted — return fallback
        return {
            "reply": "I'm sorry, I can't share that information in this context.",
            "passed": False,
            "attempts": self.max_retries + 1,
            "context_mode": self.channel_type,
            "knowledge_count": len(knowledge_items),
        }

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
# Demo
# ═══════════════════════════════════════════════════════════════════════════


def setup_mock_knowledge(store: KnowledgeStore) -> None:
    """Create sample knowledge for demo."""
    items = [
        # Alice — public
        {
            "user": "alice",
            "content": "I know Python and Rust",
            "category": "skill",
            "visibility": "public",
            "source": "demo",
        },
        {
            "user": "alice",
            "content": "I love hiking and photography",
            "category": "preference",
            "visibility": "public",
            "source": "demo",
        },
        # Alice — private
        {
            "user": "alice",
            "content": "Meeting tomorrow at 3pm with Dr. Smith",
            "category": "calendar",
            "visibility": "private",
            "source": "demo",
        },
        {
            "user": "alice",
            "content": "Phone: 13812345678",
            "category": "contact_private",
            "visibility": "private",
            "source": "demo",
        },
        # Bob — public
        {
            "user": "bob",
            "content": "Frontend developer, expert in React",
            "category": "skill",
            "visibility": "public",
            "source": "demo",
        },
        {
            "user": "bob",
            "content": "Enjoys chess and cooking",
            "category": "preference",
            "visibility": "public",
            "source": "demo",
        },
        # Bob — private
        {
            "user": "bob",
            "content": "Salary: $120,000/year",
            "category": "finance",
            "visibility": "private",
            "source": "demo",
        },
        {
            "user": "bob",
            "content": "Dentist appointment next Tuesday",
            "category": "calendar",
            "visibility": "private",
            "source": "demo",
        },
    ]

    for item_data in items:
        store.add(KnowledgeItem.from_dict(item_data))


def demo_scenario(client: PrivacyChatClient, label: str, query: str) -> None:
    """Run a single demo scenario and print results."""
    result = client.chat(query)
    status = "✅ PASSED" if result["passed"] else "🚫 BLOCKED"
    print(f'\n  Query:    "{query}"')
    print(f'  Reply:    "{result["reply"]}"')
    print(
        f"  Status:   {status} (attempts: {result['attempts']}, "
        f"knowledge: {result['knowledge_count']} items)"
    )


def main() -> None:
    import tempfile

    print("=" * 65)
    print("  MemGate × OpenAI SDK — Context-Filtered Chat Demo")
    print("=" * 65)
    print(f"  Mode: {'Mock LLM' if USE_MOCK_LLM else 'Real OpenAI API'}")

    with tempfile.TemporaryDirectory() as tmpdir:
        store = KnowledgeStore(base_dir=Path(tmpdir))
        setup_mock_knowledge(store)
        reviewer = PrivacyReviewer(store=store)

        client = PrivacyChatClient(store=store, reviewer=reviewer)

        # ── Test 1: Group chat ──
        print("\n┌─────────────────────────────────────────────────────┐")
        print("│  Context: Group Chat (alice + bob)                  │")
        print("└─────────────────────────────────────────────────────┘")
        client.switch_context(
            channel_id="group_team",
            channel_type="group",
            participants={"alice", "bob"},
        )

        demo_scenario(client, "Safe", "Tell me about Alice's skills")
        demo_scenario(client, "Leak attempt", "What's Alice's schedule?")
        demo_scenario(client, "Finance", "Tell me about Bob's salary")

        # ── Test 2: Alice's DM ──
        print("\n┌─────────────────────────────────────────────────────┐")
        print("│  Context: Alice's DM (private)                      │")
        print("└─────────────────────────────────────────────────────┘")
        client.switch_context(
            channel_id="dm_alice",
            channel_type="dm",
            participants={"alice"},
        )

        demo_scenario(client, "Schedule", "What's my schedule?")
        demo_scenario(client, "Skills", "What are my skills?")

        # ── Test 3: Dynamic context switch ──
        print("\n┌─────────────────────────────────────────────────────┐")
        print("│  Context: Dynamic switch (DM → Group → DM)          │")
        print("└─────────────────────────────────────────────────────┘")

        # Show how the same query behaves differently
        query = "Tell me about Alice's schedule"

        print("\n  [DM mode]")
        client.switch_context(
            channel_type="dm", participants={"alice"}, channel_id="dm_alice"
        )
        result = client.chat(query)
        print(f"  → {result['reply']}")

        print("\n  [Group mode]")
        client.switch_context(
            channel_type="group", participants={"alice", "bob"}, channel_id="group_team"
        )
        result = client.chat(query)
        print(f"  → {result['reply']}")

        print("\n  [Back to DM]")
        client.switch_context(
            channel_type="dm", participants={"alice"}, channel_id="dm_alice"
        )
        result = client.chat(query)
        print(f"  → {result['reply']}")

        # ── Architecture diagram ──
        print("\n" + "=" * 65)
        print("  How it works:")
        print("=" * 65)
        print("""
    ┌──────────┐     ┌─────────────────┐     ┌──────────┐
    │  User    │────→│  MemGate Layer  │────→│  OpenAI  │
    │  Query   │     │                 │     │  API     │
    └──────────┘     │  1. Filter      │     └────┬─────┘
                     │     knowledge   │          │
                     │     by context  │          │
                     │                 │     ┌────▼─────┐
                     │  2. Review      │←────│  LLM     │
                     │     LLM output  │     │  Reply   │
                     │     for leaks   │     └──────────┘
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │  Safe response  │
                     │  to user        │
                     └─────────────────┘

    In production, replace MockLLM with:
        import openai
        client = openai.OpenAI(api_key="sk-...")
""")


if __name__ == "__main__":
    main()
