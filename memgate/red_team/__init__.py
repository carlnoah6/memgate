"""
MemGate Red Team — LLM 红蓝对抗测试框架

用于测试 MemGate 隐私保护能力的攻防模拟系统。
支持 mock 模式（CI 测试）和真实 LLM 对抗。

三个角色：
- 红队 (AttackerAgent): 生成社工攻击 prompt
- 蓝队 (DefenderAgent): 生成回复 + MemGate 审查
- 裁判 (Evaluator): 独立评估泄露情况

八种攻击策略：
1. authority_impersonation — 冒充权威角色
2. context_manipulation — 上下文操控
3. emotional_appeal — 情感诱导
4. indirect_extraction — 间接推理
5. multi_turn — 多轮渐进
6. role_play — 角色扮演
7. language_switch — 语言切换
8. prompt_injection — Prompt 注入
"""

from .attacker import AttackerAgent
from .defender import DefenderAgent
from .evaluator import Evaluator
from .arena import Arena
from .strategies import STRATEGIES, AttackStrategy
from .report import ReportGenerator

__all__ = [
    "AttackerAgent",
    "DefenderAgent",
    "Evaluator",
    "Arena",
    "STRATEGIES",
    "AttackStrategy",
    "ReportGenerator",
]
