from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Set, Optional


@dataclass
class ProviderContext:
    chat_id: str
    is_private: bool
    participants: Set[str]
    channel_type: str  # "dm" or "group"
    reason: str
    unsafe_reason: Optional[str] = (
        None  # If set, the context is considered unsafe due to integrity checks
    )


class BaseProvider(ABC):
    """
    Abstract base class for context providers.
    Providers are responsible for fetching channel metadata and participants
    from external platforms (e.g., Lark, Slack, Discord).
    """

    @abstractmethod
    def fetch_context(self, chat_id: str) -> ProviderContext:
        """
        Fetch context information for a given chat_id.

        Args:
            chat_id: The unique identifier for the chat/channel.

        Returns:
            ProviderContext object containing privacy status and participants.

        Raises:
            ValueError: If chat_id is invalid or context cannot be determined.
            RuntimeError: If API calls fail.
        """
        pass

    @abstractmethod
    def is_safe(self, context: ProviderContext) -> bool:
        """
        Check if the context is safe to operate in.
        This includes checking for data consistency (Paranoid Check).
        """
        pass
