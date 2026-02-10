import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List
from .base import BaseProvider, ProviderContext


class LarkProvider(BaseProvider):
    """
    Provider implementation for Lark (Feishu).
    Fetches group privacy status and participants using Lark Open API.
    """

    KNOWN_BOT_ID = "ou_88371dccab8541963f7f6a108990d7b3"

    def __init__(self):
        self.config = self._load_config()
        self.token = None

    def _load_config(self) -> Dict[str, str]:
        """Load config from env vars or secrets file."""
        # Try to find secrets file relative to package or workspace
        workspace = (
            Path(__file__).resolve().parent.parent.parent.parent
        )  # memgate/memgate/providers/lark.py -> workspace
        secrets_file = workspace / "data/lark-secrets.json"

        config = {
            "app_id": os.getenv("LARK_APP_ID"),
            "app_secret": os.getenv("LARK_APP_SECRET"),
            "admin_open_id": os.getenv("LARK_ADMIN_OPEN_ID"),
        }

        if secrets_file.exists():
            try:
                with open(secrets_file, "r") as f:
                    file_config = json.load(f)
                    if file_config.get("app_id"):
                        config["app_id"] = file_config["app_id"]
                    if file_config.get("app_secret"):
                        config["app_secret"] = file_config["app_secret"]
                    if file_config.get("admin_open_id"):
                        config["admin_open_id"] = file_config["admin_open_id"]
            except Exception as e:
                print(f"Warning: Failed to load secrets file: {e}", file=sys.stderr)

        if not config["app_id"] or not config["app_secret"]:
            raise ValueError(
                "Missing LARK_APP_ID/SECRET. Set env vars or data/lark-secrets.json"
            )

        return config

    def _get_tenant_token(self) -> str:
        if self.token:
            return self.token

        req = urllib.request.Request(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps(
                {
                    "app_id": self.config["app_id"],
                    "app_secret": self.config["app_secret"],
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("code") != 0:
                raise RuntimeError(f"Failed to get tenant token: {resp}")
            self.token = resp.get("tenant_access_token")
            return self.token
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error getting token: {e}")

    def _get_bot_open_id(self, token: str) -> str:
        try:
            req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/bot/v3/info",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
            return resp.get("bot", {}).get("open_id", self.KNOWN_BOT_ID)
        except Exception:
            return self.KNOWN_BOT_ID

    def _get_chat_info(self, token: str, chat_id: str) -> Dict[str, Any]:
        """Get chat metadata including member_count."""
        url = f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("code") != 0:
                raise RuntimeError(f"Lark API Error (get_chat): {resp}")
            return resp.get("data", {})
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error getting chat info: {e}")

    def _get_group_members(self, token: str, chat_id: str) -> List[Dict[str, Any]]:
        """Fetch all members handling pagination."""
        members = []
        page_token = ""
        while True:
            url = f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}/members?page_size=100"
            if page_token:
                url += f"&page_token={page_token}"

            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            try:
                resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
                if resp.get("code") != 0:
                    print(f"API Error (get_members): {resp}", file=sys.stderr)
                    break

                items = resp["data"].get("items", [])
                members.extend(items)

                if not resp["data"].get("has_more"):
                    break
                page_token = resp["data"].get("page_token", "")
            except urllib.error.URLError as e:
                print(f"Network error fetching members: {e}", file=sys.stderr)
                break

        return members

    def fetch_context(self, chat_id: str) -> ProviderContext:
        token = self._get_tenant_token()
        bot_open_id = self._get_bot_open_id(token)
        admin_id = self.config.get("admin_open_id")

        # 1. Get Chat Info (for expected member count)
        chat_info = self._get_chat_info(token, chat_id)
        expected_count = int(chat_info.get("member_count", 0))

        # 2. Get Actual Members List
        members_data = self._get_group_members(token, chat_id)
        actual_count = len(members_data)

        # 3. Analyze Members
        participants = set()
        non_bot_humans = []

        for m in members_data:
            mid = m["member_id"]
            name = m.get("name", "")
            # Identify if it's the bot itself
            # Note: member_type 'bot' might catch other bots too, which we usually treat as participants unless it's us?
            # Existing script treated KNOWN_BOT_ID or member_type='bot' as "is_bot" and excluded from human_count.

            is_bot = (mid == bot_open_id) or (m.get("member_type") == "bot")
            is_admin = mid == admin_id

            if not is_bot:
                participants.add(mid)
                non_bot_humans.append({"id": mid, "name": name, "is_admin": is_admin})

        # 4. Determine Privacy
        # Private if: Only Admin (and Bot) OR Empty (Bot only)
        human_count = len(non_bot_humans)
        all_admin = all(h["is_admin"] for h in non_bot_humans)

        is_private = (human_count == 0) or (human_count == 1 and all_admin)

        if is_private:
            reason = "只有管理员和 Bot，视为私聊"
            channel_type = "dm"  # Functionally a DM with admin
        else:
            other_names = [h["name"] for h in non_bot_humans if not h["is_admin"]]
            reason = f"群内有其他成员: {', '.join(other_names)}"
            channel_type = "group"

        # 5. Paranoid Check (The Security Hardening)
        # If the chat API says there are more members than we can see,
        # it implies invisible members (external contacts/permissions issues).
        unsafe_reason = None
        if expected_count > actual_count:
            unsafe_reason = (
                f"Data Inconsistency Detected: Chat info claims {expected_count} members, "
                f"but API only returned {actual_count}. Potential hidden users. Marking UNSAFE."
            )

        return ProviderContext(
            chat_id=chat_id,
            is_private=is_private,
            participants=participants,
            channel_type=channel_type,
            reason=reason,
            unsafe_reason=unsafe_reason,
        )

    def is_safe(self, context: ProviderContext) -> bool:
        return context.unsafe_reason is None
