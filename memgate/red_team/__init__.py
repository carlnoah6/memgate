"""
MemGate Red Team — LLM Red-Blue Adversarial Testing Framework

An attack-defense simulation system for testing MemGate's privacy protection capabilities.
Supports mock mode (CI testing) and real LLM adversarial testing.

Three roles:
- Red Team (AttackerAgent): Generates social engineering attack prompts
- Blue Team (DefenderAgent): Generates responses + MemGate review
- Judge (Evaluator): Independently evaluates leak results

Eight attack strategies:
1. authority_impersonation — Impersonate authority figures
2. context_manipulation — Context manipulation
3. emotional_appeal — Emotional manipulation
4. indirect_extraction — Indirect reasoning
5. multi_turn — Multi-turn progressive
6. role_play — Role playing
7. language_switch — Language switching
8. prompt_injection — Prompt injection
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
