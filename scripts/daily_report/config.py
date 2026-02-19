import sys
import os
import json
import subprocess
import datetime
import urllib.request
import urllib.error

# ─── 配置 ───────────────────────────────────────────────────────────
WORKSPACE = "/home/ubuntu/.openclaw/workspace"
API_PROXY = "http://localhost:8180"
API_KEY = "REDACTED_LUNA_KEY"
ADMIN_KEY = "sk-admin-luna2026"
LLM_MODEL = "claude-opus-4-6-thinking"  # 日报使用与 Luna 主模型一致
LLM_MODEL_HEAVY = "claude-opus-4-6-thinking"  # 重任务
LLM_MODEL_FAST = "deepseek-chat"  # Code Review 使用快速模型
CALENDAR_ID = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
LARK_TOKEN_FILE = f"{WORKSPACE}/data/lark-user-token.json"
LARK_APP_ID = "cli_a90c3a6163785ed2"
LARK_REDIRECT_URI = "https://anz-luna.grolar-wage.ts.net/feishu/card_action"
LARK_OAUTH_SCOPES = "auth:user.id:read+calendar:calendar+docx:document+drive:drive+wiki:wiki"

def get_lark_auth_url():
    """生成 Lark OAuth 授权链接"""
    return (f"https://open.larksuite.com/open-apis/authen/v1/index?"
            f"app_id={LARK_APP_ID}&"
            f"redirect_uri={LARK_REDIRECT_URI}&"
            f"scope={LARK_OAUTH_SCOPES}")
SESSION_DIR = "/home/ubuntu/.openclaw/agents/main/sessions"
SGT = datetime.timezone(datetime.timedelta(hours=8))

# 扫描目录
SCAN_DIRS = [
    WORKSPACE,
    "/home/ubuntu/api-proxy",
]
# 代码文件后缀（用于扫描变更）
CODE_EXTS = {".py", ".sh", ".js", ".ts", ".json", ".toml", ".yaml", ".yml"}
# 可审查的代码后缀（LLM Code Review 只审查这些）
REVIEWABLE_EXTS = {".py", ".sh", ".js", ".ts"}
# 排除目录
EXCLUDE_DIRS = {"venv", ".venv", "node_modules", "__pycache__", ".git",
                "download", "patches", "tests", ".openclaw"}
# 排除路径前缀（第三方 / 大型项目子模块）
EXCLUDE_PREFIXES = [
    "balatro_rl/engine/",      # 第三方游戏引擎
    "memgate/",                # 独立项目
    "projects/",               # 子项目
    "evaluation/benchmarks/",  # benchmark 数据
    "skills/",                 # 插件代码
]
# 最大审查文件数（避免 LLM 调用爆炸）
# 注意：此变量可能会在运行时被 main 函数修改（如 --fast 模式）
MAX_REVIEW_FILES = 30


# ════════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════════

def log(msg: str):
    """带时间戳的日志"""
    now = datetime.datetime.now(SGT).strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def call_llm(prompt: str, max_tokens: int = 4096, model: str = None,
             system: str = None, timeout: int = 60) -> str:
    """调用 API 代理的 LLM（OpenAI Chat Completions 格式）

    Args:
        prompt: 用户提示词
        max_tokens: 最大生成 token 数
        model: 模型名称，默认使用 LLM_MODEL
        system: 系统提示词
        timeout: 请求超时秒数（默认 60 秒）
    """
    model = model or LLM_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    req = urllib.request.Request(
        f"{API_PROXY}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )

    # 使用更短的超时防止长时间挂起
    actual_timeout = min(timeout, 180)  # 最多 180 秒（日报分析需要更长时间）

    for attempt in range(2):  # 最多重试 1 次
        try:
            with urllib.request.urlopen(req, timeout=actual_timeout) as resp:
                data = json.loads(resp.read())
                # OpenAI Chat Completions 格式
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    # 优先使用 content，如果为空则使用 reasoning_content (kimi-k2.5)
                    content = message.get("content", "")
                    if not content:
                        content = message.get("reasoning_content", "")
                    return content
                return ""
        except urllib.error.HTTPError as e:
            body_err = e.read().decode() if e.fp else ""
            log(f"⚠️ LLM 调用失败 ({e.code}): {body_err[:200]}")
            return f"[LLM 调用失败: HTTP {e.code}]"
        except (urllib.error.URLError, Exception) as e:
            is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
            if is_timeout and attempt == 0:
                log(f"⚠️ LLM 调用超时，重试中... ({actual_timeout}s)")
                import time
                time.sleep(2)
                # Rebuild request for retry
                req = urllib.request.Request(
                    f"{API_PROXY}/v1/chat/completions",
                    data=json.dumps(body).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}",
                    },
                    method="POST",
                )
                continue
            if is_timeout:
                log(f"⚠️ LLM 调用超时 ({actual_timeout}s)，重试后仍失败")
                return f"[LLM 调用超时: 超过 {actual_timeout} 秒未响应]"
            log(f"⚠️ LLM 调用异常: {e}")
            return f"[LLM 调用失败: {e}]"
    return "[LLM 调用失败: 未知错误]"


def run_cmd(cmd: str, timeout: int = 30) -> str:
    """执行 shell 命令，返回 stdout"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[命令超时]"
    except Exception as e:
        return f"[命令失败: {e}]"


def read_file(path: str, max_lines: int = 500) -> str:
    """安全读取文件"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[:max_lines]
            return "".join(lines)
    except Exception as e:
        return f"[读取失败: {e}]"
