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
LLM_MODEL = "gemini-2.5-flash"  # 日报用 flash 够了，省 quota 给交互
LLM_MODEL_HEAVY = "claude-opus-4-6-thinking"  # Code Review 用重模型
CALENDAR_ID = "feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn"
LARK_TOKEN_FILE = f"{WORKSPACE}/data/lark-user-token.json"
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
             system: str = None) -> str:
    """调用 API 代理的 LLM（Anthropic Messages 格式）"""
    model = model or LLM_MODEL
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if system:
        body["system"] = system

    req = urllib.request.Request(
        f"{API_PROXY}/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
            # Anthropic Messages 格式
            content = data.get("content", [])
            texts = [c["text"] for c in content if c.get("type") == "text"]
            return "\n".join(texts)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode() if e.fp else ""
        log(f"⚠️ LLM 调用失败 ({e.code}): {body_err[:200]}")
        return f"[LLM 调用失败: HTTP {e.code}]"
    except Exception as e:
        log(f"⚠️ LLM 调用异常: {e}")
        return f"[LLM 调用失败: {e}]"


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
