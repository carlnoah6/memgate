"""
MemGate — Privacy-Aware Memory Isolation Layer for AI Agents.

MemGate acts as a firewall between your AI agent's long-term memory
and its output channels, ensuring private information is never leaked
into public contexts.
"""

__version__ = "0.3.0"

from .knowledge_store import KnowledgeStore, KnowledgeItem, KnowledgeTagger
from .privacy_context import PrivacyContext, ChannelInfo
from .privacy_review import PrivacyReviewer, ReviewResult, Violation

__all__ = [
    "KnowledgeStore",
    "KnowledgeItem",
    "KnowledgeTagger",
    "PrivacyContext",
    "ChannelInfo",
    "PrivacyReviewer",
    "ReviewResult",
    "Violation",
]
