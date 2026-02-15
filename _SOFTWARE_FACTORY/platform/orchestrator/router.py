"""
Intent Router - Classifies user input and selects the right orchestration pattern.
====================================================================================
Uses a fast LLM (GPT-4o) to classify intent, then maps to pattern + agent roles.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..models import OrchestrationPattern

logger = logging.getLogger(__name__)


# ── Static routing rules ──────────────────────────────────────────────

INTENT_PATTERNS: dict[str, dict] = {
    "develop_feature": {
        "pattern": OrchestrationPattern.HIERARCHICAL,
        "roles": ["lead_dev", "dev", "dev", "testeur"],
        "keywords": ["développe", "implémente", "crée", "feature", "endpoint", "api", "composant"],
    },
    "code_review": {
        "pattern": OrchestrationPattern.SEQUENTIAL,
        "roles": ["dev", "lead_dev", "securite"],
        "keywords": ["review", "revue", "vérifie", "audit code"],
    },
    "security_audit": {
        "pattern": OrchestrationPattern.SEQUENTIAL,
        "roles": ["dev", "securite", "lead_dev"],
        "keywords": ["sécurité", "security", "vulnérabilité", "owasp", "pentest"],
    },
    "sprint_planning": {
        "pattern": OrchestrationPattern.HIERARCHICAL,
        "roles": ["chef_projet", "metier", "lead_dev", "dev"],
        "keywords": ["sprint", "planning", "backlog", "priorisation", "roadmap"],
    },
    "architecture_debate": {
        "pattern": OrchestrationPattern.NETWORK,
        "roles": ["architecte", "lead_dev", "devops", "securite"],
        "keywords": ["architecture", "débat", "design", "pattern", "choix technique", "rest vs", "grpc"],
    },
    "deploy": {
        "pattern": OrchestrationPattern.SEQUENTIAL,
        "roles": ["devops", "testeur", "securite", "devops"],
        "keywords": ["deploy", "déploie", "mise en prod", "release", "livraison"],
    },
    "bug_fix": {
        "pattern": OrchestrationPattern.LOOP,
        "roles": ["dev", "testeur"],
        "keywords": ["bug", "corrige", "fix", "erreur", "crash", "régression"],
    },
    "spec_writing": {
        "pattern": OrchestrationPattern.SEQUENTIAL,
        "roles": ["metier", "chef_projet", "lead_dev"],
        "keywords": ["spécification", "spec", "cahier des charges", "user story", "exigence"],
    },
    "testing": {
        "pattern": OrchestrationPattern.PARALLEL,
        "roles": ["testeur", "testeur", "dev"],
        "keywords": ["test", "e2e", "unit test", "smoke", "qa", "qualité"],
    },
    "brainstorm": {
        "pattern": OrchestrationPattern.AGGREGATOR,
        "roles": ["metier", "lead_dev", "ux_designer", "dev"],
        "keywords": ["brainstorm", "idées", "innovation", "proposition", "explore"],
    },
    "incident": {
        "pattern": OrchestrationPattern.HIERARCHICAL,
        "roles": ["devops", "lead_dev", "dev", "securite"],
        "keywords": ["incident", "down", "outage", "panne", "alerte", "monitoring"],
    },
}


class IntentRouter:
    """Routes user input to the appropriate orchestration pattern."""

    def __init__(self, llm_provider: Any = None):
        self.llm = llm_provider

    def classify_static(self, user_input: str) -> Optional[dict]:
        """Keyword-based classification (fast, no LLM)."""
        input_lower = user_input.lower()
        best_match = None
        best_score = 0

        for intent_name, config in INTENT_PATTERNS.items():
            score = sum(1 for kw in config["keywords"] if kw in input_lower)
            if score > best_score:
                best_score = score
                best_match = {
                    "intent": intent_name,
                    "pattern": config["pattern"],
                    "roles": config["roles"],
                    "confidence": min(score / 3.0, 1.0),
                }

        return best_match

    async def classify(self, user_input: str) -> dict:
        """
        Classify intent using LLM (with static fallback).
        Returns: {"intent": str, "pattern": Pattern, "roles": [str], "confidence": float}
        """
        # Try static first
        static = self.classify_static(user_input)

        if not self.llm:
            return static or self._default()

        if static and static["confidence"] >= 0.8:
            return static

        # Use LLM for ambiguous cases
        try:
            intents_list = "\n".join(f"- {k}: {v['keywords'][:3]}" for k, v in INTENT_PATTERNS.items())
            prompt = (
                f"Classify this user request into ONE of these intents:\n{intents_list}\n\n"
                f"User request: {user_input}\n\n"
                f"Respond with ONLY the intent name."
            )

            response = await self.llm.query(
                prompt=prompt,
                model="gpt-5.1",
                temperature=0.1,
                max_tokens=50,
            )

            intent_name = response.strip().lower().replace(" ", "_")
            if intent_name in INTENT_PATTERNS:
                config = INTENT_PATTERNS[intent_name]
                return {
                    "intent": intent_name,
                    "pattern": config["pattern"],
                    "roles": config["roles"],
                    "confidence": 0.9,
                }
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")

        return static or self._default()

    def _default(self) -> dict:
        return {
            "intent": "general",
            "pattern": OrchestrationPattern.HIERARCHICAL,
            "roles": ["lead_dev", "dev"],
            "confidence": 0.3,
        }

    def override(self, pattern: OrchestrationPattern, roles: list[str]) -> dict:
        """Manual override (user forces a specific pattern)."""
        return {
            "intent": "manual",
            "pattern": pattern,
            "roles": roles,
            "confidence": 1.0,
        }
