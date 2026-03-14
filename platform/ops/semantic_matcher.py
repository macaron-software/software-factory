"""
Semantic matching for error mutes.

WHY
---
Les mutes exacts (string égalité) ont un problème : l'opérateur mute
"HTTP 429 rate limiting in downloads" mais la prochaine erreur dit
"HTTP 429 rate limiting in uploads" → non supprimée malgré la même cause racine.

Ce module gère le matching exact des mutes. Le matching sémantique (LLM) est
délégué à l'agent monitoring-ops qui utilise son propre loop LLM via les outils
de monitoring (monitoring_should_alert). Cela évite tout appel LLM direct depuis
les fonctions ops/ et garde la logique dans le système agents + patterns.

WHAT
----
SemanticMatcher.check_mute_match() :
  1. Vérifie l'exact match (fast path, pas de LLM)
  2. Vérifie les mutes partiels (préfixe/substring) pour les variantes courantes
  3. Retourne (is_muted, reason)

SOURCE
------
Porté et adapté de airweave-ai/error-monitoring-agent (MIT License)
https://github.com/airweave-ai/error-monitoring-agent/blob/main/backend/pipeline/semantic_matcher.py

ADAPTATIONS
-----------
- Suppression de LangChain → était déjà supprimé (appels directs LLMClient)
- LLM semantic matching supprimé : délégué à monitoring-ops agent (tool loop)
- find_matching_ticket() supprimé (dépendait d'Airweave + Linear)
- check_mute_match() est maintenant synchrone (pas de LLM)
"""
# Ref: feat-memory

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SemanticMatcher:
    """
    Exact + partial matching for error mutes.

    LLM-based semantic matching (same root cause, different wording) is handled
    by the monitoring-ops agent using its natural LLM loop — not here.
    """

    def check_mute_match(
        self,
        signature: str,
        active_mutes: dict[str, dict],
    ) -> tuple[bool, Optional[str]]:
        """
        Check whether this error matches any active mute (exact or substring).

        Returns:
            (is_muted, suppression_reason)
        """
        if not active_mutes:
            return False, None

        # 1. Exact match
        if signature in active_mutes:
            info = active_mutes[signature]
            return True, info.get("reason") or "Exact signature muted"

        # 2. Substring match (handles minor wording variants)
        sig_lower = signature.lower()
        for muted_sig, info in active_mutes.items():
            muted_lower = muted_sig.lower()
            # Match if muted pattern appears in signature or vice versa (>20 chars to avoid false positives)
            if len(muted_lower) > 20 and (
                muted_lower in sig_lower or sig_lower in muted_lower
            ):
                reason = (
                    info.get("reason") or f"Matches muted pattern: {muted_sig[:60]}"
                )
                return True, reason

        return False, None


# Singleton
_matcher: Optional[SemanticMatcher] = None


def get_semantic_matcher() -> SemanticMatcher:
    global _matcher
    if _matcher is None:
        _matcher = SemanticMatcher()
    return _matcher
