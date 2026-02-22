"""Prompt Injection Guard — detection, scoring, and blocking.

Provides real-time scoring of inputs for prompt injection risk.
Integrated at the executor level before any LLM call.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Risk thresholds ──
SCORE_WARN = 3    # Log warning
SCORE_BLOCK = 7   # Block the input entirely
SCORE_MAX = 10


@dataclass
class InjectionScore:
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    blocked: bool = False

    @property
    def risk_level(self) -> str:
        if self.score >= SCORE_BLOCK:
            return "CRITICAL"
        if self.score >= SCORE_WARN:
            return "WARNING"
        return "OK"


# ── Scoring rules: (pattern, score, reason) ──
_SCORING_RULES: list[tuple[re.Pattern, int, str]] = [
    # System prompt override attempts (+4 each, immediately dangerous)
    (re.compile(r'(?:^|\n)\s*(?:SYSTEM|ASSISTANT)\s*:', re.I), 4,
     "System/Assistant role override"),
    (re.compile(r'<\|(?:im_start|im_end|system)\|>', re.I), 5,
     "LLM token boundary injection"),
    (re.compile(r'\[/?(?:INST|SYS)\]', re.I), 4,
     "Instruction boundary marker"),

    # Instruction override (+3 each)
    (re.compile(r'ignore\s+(?:all\s+)?(?:previous|prior|above|your)\s+(?:instructions?|prompts?|rules?)', re.I), 4,
     "Ignore-instructions directive"),
    (re.compile(r'disregard\s+(?:all\s+)?(?:previous|prior|your)', re.I), 3,
     "Disregard-previous directive"),
    (re.compile(r'forget\s+(?:everything|all|your)', re.I), 3,
     "Forget-everything directive"),

    # Role hijacking (+3)
    (re.compile(r'(?:you\s+are\s+now|act\s+as|pretend\s+(?:to\s+be|you\s+are))\s+(?:a\s+)?(?:different|new|unrestricted|evil|hacker)', re.I), 4,
     "Role hijacking attempt"),
    (re.compile(r'\b(?:DAN|do\s+anything\s+now|jailbreak|DEVELOPER\s+MODE)\b', re.I), 5,
     "Jailbreak keyword"),

    # Data exfiltration attempts (+2)
    (re.compile(r'(?:output|print|show|reveal|display)\s+(?:the\s+)?(?:system\s+prompt|api\s+key|secret|password|credentials?)', re.I), 3,
     "Data exfiltration request"),
    (re.compile(r'(?:what\s+(?:are|is)\s+your\s+(?:instructions?|system\s+prompt|rules?))', re.I), 2,
     "System prompt probing"),

    # Encoded payloads (+2)
    (re.compile(r'(?:base64|atob|btoa)\s*\(', re.I), 2,
     "Encoded payload execution"),

    # Cross-agent injection (+2)
    (re.compile(r'(?:tell|instruct|order|command)\s+(?:the\s+)?(?:next|other)\s+agent', re.I), 2,
     "Cross-agent instruction injection"),

    # Repetitive/flooding (mild, +1)
    (re.compile(r'(.{10,}?)\1{5,}', re.S), 1,
     "Repetitive content flooding"),
]


class PromptInjectionGuard:
    """Scores and optionally blocks prompt injection attempts."""

    def __init__(self):
        # Track per-source injection attempts for adaptive blocking
        self._attempt_counts: dict[str, int] = defaultdict(int)
        self._last_reset = time.time()

    def score(self, text: str, source: str = "unknown") -> InjectionScore:
        """Score text for prompt injection risk. Higher = more dangerous."""
        if not text:
            return InjectionScore()

        result = InjectionScore()

        for pattern, points, reason in _SCORING_RULES:
            matches = pattern.findall(text)
            if matches:
                result.score += points
                result.reasons.append(f"{reason} (+{points})")

        # Cap at max
        result.score = min(result.score, SCORE_MAX)

        # Adaptive: repeated attempts from same source increase score
        if result.score >= SCORE_WARN:
            self._attempt_counts[source] += 1
            if self._attempt_counts[source] >= 3:
                result.score = min(result.score + 2, SCORE_MAX)
                result.reasons.append(f"Repeated attempts from {source} (+2)")

        result.blocked = result.score >= SCORE_BLOCK

        # Log
        if result.score >= SCORE_BLOCK:
            logger.warning(
                "PROMPT_INJECTION BLOCKED source=%s score=%d reasons=%s",
                source, result.score, result.reasons
            )
        elif result.score >= SCORE_WARN:
            logger.warning(
                "PROMPT_INJECTION WARNING source=%s score=%d reasons=%s",
                source, result.score, result.reasons
            )

        return result

    def check_and_sanitize(self, text: str, source: str = "user") -> tuple[str, InjectionScore]:
        """Score input and return sanitized version if safe, or block message if dangerous.

        Returns: (output_text, score)
        If score.blocked is True, output_text is a safe error message (not the original).
        """
        from .sanitize import sanitize_user_input

        result = self.score(text, source)

        if result.blocked:
            return (
                f"[Input blocked: prompt injection detected (score {result.score}/{SCORE_MAX})]",
                result,
            )

        # Apply sanitization for warning-level inputs
        if result.score >= SCORE_WARN:
            text = sanitize_user_input(text, source)

        return text, result

    def reset_counters(self):
        """Reset adaptive counters (call periodically)."""
        self._attempt_counts.clear()
        self._last_reset = time.time()


# Singleton
_guard: Optional[PromptInjectionGuard] = None


def get_prompt_guard() -> PromptInjectionGuard:
    global _guard
    if _guard is None:
        _guard = PromptInjectionGuard()
    return _guard
