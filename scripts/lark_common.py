#!/usr/bin/env python3
"""Lark API 公共模块 — 集中管理 token 获取和 API 调用。

所有 Lark 脚本的公共函数，消除每个脚本重复实现 get_tenant_token / get_user_token / API 调用的问题。

用法:
    from lark_common import get_tenant_token, get_user_token, lark_api, send_message

    # 获取 token
    token = get_tenant_token()
    user_token = get_user_token()

    # API 调用
    result = lark_api("GET", "/im/v1/chats/oc_xxx", token=token)
    result = lark_api("POST", "/im/v1/messages?receive_id_type=chat_id",
                      body={"receive_id": chat_id, "msg_type": "text", "content": '{"text":"hi"}'},
                      token=token)

    # 便捷函数
    send_message(chat_id, "Hello!")
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─── 常量 ─────────────────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE / "data"

# Lark App 凭据
APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"

# API 基础 URL
BASE_URL = "https://open.larksuite.com/open-apis"

# Token 文件路径
USER_TOKEN_FILE = DATA_DIR / "lark-user-token.json"

# 已知 ID
CARL_OPEN_ID = "ou_35f664e694dd100adf97b867e68e1d3a"
BOT_OPEN_ID = "ou_88371dccab8541963f7f6a108990d7b3"
CARL_MAIN_CHAT = "oc_680d9c843e6a0ad501de9299a97f3a7e"

# 日历
DEFAULT_CALENDAR_ID = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"

# Wiki Spaces
LUNA_WIKI_SPACE = "7604126789916479197"
CARL_WIKI_SPACE = "7604150806383693538"

# ─── 内部缓存 ────────────────────────────────────────────────────────────────

_tenant_token_cache = {"token": None, "expires_at": 0}


# ─── Token 获取 ───────────────────────────────────────────────────────────────

def get_tenant_token(*, force_refresh: bool = False) -> str:
    """获取 tenant_access_token（应用级别 token）。

    自动缓存，有效期内不重复请求。Lark 返回的 token 有效期通常为 2 小时。

    Args:
        force_refresh: 强制刷新，忽略缓存。

    Returns:
        tenant_access_token 字符串。

    Raises:
        LarkAPIError: 获取失败。
    """
    now = time.time()
    if not force_refresh and _tenant_token_cache["token"] and now < _tenant_token_cache["expires_at"]:
        return _tenant_token_cache["token"]

    data = _http_json(
        "POST",
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        body={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    token = data.get("tenant_access_token")
    if not token:
        raise LarkAPIError(f"Failed to get tenant_access_token: {data}")

    expire = data.get("expire", 7200)
    _tenant_token_cache["token"] = token
    _tenant_token_cache["expires_at"] = now + expire - 300  # 提前 5 分钟过期

    return token


def get_user_token() -> str:
    """获取 user_access_token（用户级别 token，从本地文件读取）。

    Token 由 lark-token-refresh.py 定时刷新，这里只负责读取。

    Returns:
        user_access_token 字符串。

    Raises:
        FileNotFoundError: token 文件不存在。
        LarkAPIError: token 文件格式错误或已过期。
    """
    if not USER_TOKEN_FILE.exists():
        raise FileNotFoundError(f"User token file not found: {USER_TOKEN_FILE}")

    with open(USER_TOKEN_FILE) as f:
        data = json.load(f)

    token = data.get("access_token")
    if not token:
        raise LarkAPIError(f"No access_token in {USER_TOKEN_FILE}")

    # 检查是否过期（如果有 expires_at 字段）
    expires_at = data.get("expires_at")
    if expires_at and time.time() > expires_at:
        raise LarkAPIError(
            f"User token expired at {time.ctime(expires_at)}. "
            f"Run: python3 scripts/lark-token-refresh.py"
        )

    return token


def get_app_token() -> str:
    """获取 app_access_token（用于 OAuth 刷新等场景）。

    Returns:
        app_access_token 字符串。

    Raises:
        LarkAPIError: 获取失败。
    """
    data = _http_json(
        "POST",
        f"{BASE_URL}/auth/v3/app_access_token/internal",
        body={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    token = data.get("app_access_token")
    if not token:
        raise LarkAPIError(f"Failed to get app_access_token: {data}")
    return token


# ─── API 调用 ──────────────────────────────────────────────────────────────────

def lark_api(
    method: str,
    path: str,
    *,
    body: dict = None,
    token: str = None,
    token_type: str = "tenant",
    timeout: int = 15,
    raw: bool = False,
) -> dict:
    """通用 Lark API 调用。

    Args:
        method: HTTP 方法 (GET, POST, PUT, PATCH, DELETE)。
        path: API 路径（以 / 开头，如 "/im/v1/chats/oc_xxx"）。
              也可以传完整 URL。
        body: 请求体 dict（自动 JSON 序列化）。
        token: 直接传入 token。如果不传，自动根据 token_type 获取。
        token_type: "tenant"（默认）或 "user"。仅在 token=None 时生效。
        timeout: 超时秒数。
        raw: 如果 True，返回原始 response dict；否则检查 code 并返回 data 部分。

    Returns:
        API 响应 dict。raw=False 时返回 response["data"]（如果有），
        raw=True 时返回完整响应。

    Raises:
        LarkAPIError: API 返回非 0 code 或 HTTP 错误。
    """
    if token is None:
        token = get_user_token() if token_type == "user" else get_tenant_token()

    url = path if path.startswith("http") else f"{BASE_URL}{path}"

    resp = _http_json(method, url, body=body, token=token, timeout=timeout)

    if raw:
        return resp

    code = resp.get("code")
    if code is not None and code != 0:
        raise LarkAPIError(
            f"Lark API error: code={code} msg={resp.get('msg', 'unknown')}",
            code=code,
            response=resp,
        )

    return resp.get("data", resp)


# ─── 便捷函数 ──────────────────────────────────────────────────────────────────

def send_message(
    chat_id: str,
    text: str,
    *,
    msg_type: str = "text",
    token: str = None,
) -> dict:
    """向群聊发送消息。

    Args:
        chat_id: 群聊 ID（oc_xxx）。
        text: 消息内容。msg_type="text" 时为纯文本；
              msg_type="interactive" 时为卡片 JSON 字符串。
        msg_type: 消息类型（text / post / interactive）。
        token: 自定义 token，默认用 tenant_token。

    Returns:
        API 响应 data 部分。

    Raises:
        LarkAPIError: 发送失败。
    """
    if msg_type == "text":
        content = json.dumps({"text": text})
    else:
        content = text

    return lark_api(
        "POST",
        "/im/v1/messages?receive_id_type=chat_id",
        body={
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": content,
        },
        token=token or get_tenant_token(),
    )


def get_chat_info(chat_id: str, *, token: str = None) -> dict:
    """获取群聊信息。

    Returns:
        群聊信息 dict。
    """
    return lark_api("GET", f"/im/v1/chats/{chat_id}", token=token or get_tenant_token())


def get_chat_members(chat_id: str, *, token: str = None) -> list:
    """获取群聊所有成员（自动分页）。

    Returns:
        成员列表。
    """
    tk = token or get_tenant_token()
    members = []
    page_token = ""
    while True:
        url = f"/im/v1/chats/{chat_id}/members?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        data = lark_api("GET", url, token=tk)
        members.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
    return members


def get_bot_info(*, token: str = None) -> dict:
    """获取 bot 自身信息。

    Returns:
        Bot 信息 dict（包含 open_id 等）。
    """
    return lark_api("GET", "/bot/v3/info", token=token or get_tenant_token())


def get_calendar_events(
    start_date,
    end_date=None,
    *,
    calendar_id: str = None,
    token: str = None,
) -> list:
    """获取日历事件。

    Args:
        start_date: 开始日期（date 对象）。
        end_date: 结束日期（date 对象），默认同 start_date。
        calendar_id: 日历 ID，默认 Carl 的主日历。
        token: user_access_token，默认自动获取。

    Returns:
        事件列表。
    """
    from datetime import datetime, timezone, timedelta
    SGT = timezone(timedelta(hours=8))

    if end_date is None:
        end_date = start_date

    cal_id = calendar_id or DEFAULT_CALENDAR_ID
    tk = token or get_user_token()

    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=SGT)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=SGT) + timedelta(seconds=1)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    data = lark_api(
        "GET",
        f"/calendar/v4/calendars/{cal_id}/events?start_time={start_ts}&end_time={end_ts}&page_size=50",
        token=tk,
    )
    return data.get("items", [])


# ─── 异常类 ────────────────────────────────────────────────────────────────────

class LarkAPIError(Exception):
    """Lark API 调用错误。"""

    def __init__(self, message: str, *, code: int = None, response: dict = None):
        super().__init__(message)
        self.code = code
        self.response = response or {}


# ─── 内部 HTTP 工具 ─────────────────────────────────────────────────────────────

def _http_json(
    method: str,
    url: str,
    *,
    body: dict = None,
    token: str = None,
    timeout: int = 15,
) -> dict:
    """底层 HTTP JSON 请求（使用 urllib，无第三方依赖）。"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode() if body else None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            return json.loads(err_body)
        except json.JSONDecodeError:
            raise LarkAPIError(f"HTTP {e.code}: {err_body[:500]}", code=e.code)
    except urllib.error.URLError as e:
        raise LarkAPIError(f"URL error: {e.reason}")


# ─── CLI 入口（测试用）────────────────────────────────────────────────────────

def _cli_test():
    """命令行快速测试 token 获取。"""
    import argparse
    parser = argparse.ArgumentParser(description="Lark Common Module — test token retrieval")
    parser.add_argument("--tenant", action="store_true", help="Test tenant token")
    parser.add_argument("--user", action="store_true", help="Test user token")
    parser.add_argument("--app", action="store_true", help="Test app token")
    parser.add_argument("--bot", action="store_true", help="Test bot info")
    parser.add_argument("--all", action="store_true", help="Test all tokens")
    args = parser.parse_args()

    if not any([args.tenant, args.user, args.app, args.bot, args.all]):
        args.all = True

    results = {}

    if args.tenant or args.all:
        try:
            token = get_tenant_token()
            results["tenant_token"] = {"ok": True, "token_prefix": token[:20] + "..."}
            print(f"✅ tenant_token: {token[:20]}...")
        except Exception as e:
            results["tenant_token"] = {"ok": False, "error": str(e)}
            print(f"❌ tenant_token: {e}")

    if args.user or args.all:
        try:
            token = get_user_token()
            results["user_token"] = {"ok": True, "token_prefix": token[:20] + "..."}
            print(f"✅ user_token: {token[:20]}...")
        except Exception as e:
            results["user_token"] = {"ok": False, "error": str(e)}
            print(f"❌ user_token: {e}")

    if args.app or args.all:
        try:
            token = get_app_token()
            results["app_token"] = {"ok": True, "token_prefix": token[:20] + "..."}
            print(f"✅ app_token: {token[:20]}...")
        except Exception as e:
            results["app_token"] = {"ok": False, "error": str(e)}
            print(f"❌ app_token: {e}")

    if args.bot or args.all:
        try:
            info = get_bot_info()
            bot = info.get("bot", info)
            bot_id = bot.get("open_id", "?")
            results["bot_info"] = {"ok": True, "open_id": bot_id}
            print(f"✅ bot_info: open_id={bot_id}")
        except Exception as e:
            results["bot_info"] = {"ok": False, "error": str(e)}
            print(f"❌ bot_info: {e}")

    # Summary
    ok_count = sum(1 for v in results.values() if v["ok"])
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Results: {ok_count}/{total} passed")

    return 0 if ok_count == total else 1


if __name__ == "__main__":
    sys.exit(_cli_test())
