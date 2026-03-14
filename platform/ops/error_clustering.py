"""
Multi-stage error clustering for the platform auto-heal engine.

WHY
---
Sans clustering, 20 erreurs "HTTP 429" identiques génèrent 20 epics TMA séparés.
Le clustering réduit ce bruit en regroupant les erreurs par cause racine avant
de décider si on doit agir.

WHAT
----
Regroupe les incidents en clusters homogènes via 3 étapes successives :

  Étape 1 — Strict   : même error_type ET même source → regroupement immédiat, 0 LLM
  Étape 2 — Regex    : même classe d'erreur extraite (HTTP_429, TimeoutError…) → 0 LLM
  Étape 3 — LLM      : pour les incidents restants, on demande au LLM de regrouper
                        par similarité sémantique (cause racine)

L'étape LLM est un filet de sécurité : elle ne se déclenche que si les étapes 1 et 2
n'ont pas tout regroupé, et elle ne consomme des tokens que pour les incidents "orphelins".

Exemple : 20 incidents → étape 1 : 15 regroupés (3 clusters) → étape 2 : 3 regroupés
(1 cluster) → étape 3 : 2 incidents restants → 1 cluster LLM = 5 clusters au total.

SOURCE
------
Porté et adapté de airweave-ai/error-monitoring-agent (MIT License)
https://github.com/airweave-ai/error-monitoring-agent/blob/main/backend/pipeline/clustering.py

ADAPTATIONS
-----------
- Suppression de LangChain → appels directs via platform LLMClient
- Input = dicts d'incidents platform (id, error_type, error_detail, source, severity)
  au lieu des RawError Pydantic du repo source
- Pas de ClusterSummary Pydantic : JSON brut parsé avec fallback
- generate_signature() en méthode séparée (appelée après cluster() si besoin)
"""
# Ref: feat-monitoring

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_error_class(message: str) -> str:
    """Extract a short error class from an error message."""
    if not message:
        return "unknown"
    m = re.search(r"HTTP\s+(\d{3})", message, re.I)
    if m:
        return f"HTTP_{m.group(1)}"
    m = re.match(r"([A-Za-z]+(?:Error|Exception|Timeout|Warning))", message)
    if m:
        return m.group(1)
    first_word = message.split()[0] if message.split() else "unknown"
    return first_word[:30]


def _incident_key_strict(inc: dict) -> str:
    return f"{inc.get('error_type', '?')}|{inc.get('source', '?')}"


def _incident_key_regex(inc: dict) -> str:
    msg = inc.get("error_detail", "") or inc.get("title", "")
    return _extract_error_class(msg)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ErrorClusterer:
    """
    Multi-stage error clusterer for platform incidents.

    Input:  list of incident dicts (from platform_incidents table)
    Output: list of ClusterGroup dicts with fields:
              - signature (str)         : natural-language cluster label
              - error_class (str)       : short error type
              - incident_ids (list[str]): ids of grouped incidents
              - severity (str)          : worst severity in cluster (P0…P3 / S1…S4)
              - count (int)
              - sample_messages (list[str])
              - modules (list[str])
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def cluster(self, incidents: list[dict]) -> list[dict]:
        """Cluster incidents and return groups."""
        if not incidents:
            return []

        if len(incidents) == 1:
            return [self._make_cluster([incidents[0]])]

        # Stage 1: strict
        strict_clusters, remaining = self._strict_cluster(incidents)
        logger.debug(
            "Clustering stage1: %d clusters, %d remaining",
            len(strict_clusters),
            len(remaining),
        )

        # Stage 2: regex
        if remaining:
            regex_clusters, remaining = self._regex_cluster(remaining)
        else:
            regex_clusters = []
        logger.debug(
            "Clustering stage2: %d clusters, %d remaining",
            len(regex_clusters),
            len(remaining),
        )

        # Stage 3: orphans → one cluster per incident.
        # Semantic grouping of remaining incidents is handled by the monitoring-ops
        # agent using its LLM loop (monitoring_cluster_incidents tool returns orphans).
        llm_clusters = [self._make_cluster([inc]) for inc in remaining]

        return strict_clusters + regex_clusters + llm_clusters

    # ------------------------------------------------------------------
    # Stage 1 — strict (error_type + source)
    # ------------------------------------------------------------------

    def _strict_cluster(self, incidents: list[dict]) -> tuple[list[dict], list[dict]]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for inc in incidents:
            groups[_incident_key_strict(inc)].append(inc)

        clusters, remaining = [], []
        for key, members in groups.items():
            if len(members) >= 2:
                clusters.append(self._make_cluster(members))
            else:
                remaining.extend(members)
        return clusters, remaining

    # ------------------------------------------------------------------
    # Stage 2 — regex (error class extraction)
    # ------------------------------------------------------------------

    def _regex_cluster(self, incidents: list[dict]) -> tuple[list[dict], list[dict]]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for inc in incidents:
            groups[_incident_key_regex(inc)].append(inc)

        clusters, remaining = [], []
        for key, members in groups.items():
            if len(members) >= 2:
                clusters.append(self._make_cluster(members))
            else:
                remaining.extend(members)
        return clusters, remaining

    def _fallback_signature(self, inc: dict) -> str:
        msg = inc.get("error_detail") or inc.get("title") or "Unknown error"
        etype = inc.get("error_type", "")
        if etype:
            return f"{etype}: {msg[:80]}"
        return msg[:100]

    # ------------------------------------------------------------------
    # Cluster builder
    # ------------------------------------------------------------------

    def _make_cluster(
        self, incidents: list[dict], signature: Optional[str] = None
    ) -> dict:
        if signature is None:
            signature = self._fallback_signature(incidents[0])

        severities = [inc.get("severity", "P3") for inc in incidents]
        # Worst severity: P0 < P1 < P2 < P3
        _sev_ord = {
            "P0": 0,
            "S1": 0,
            "P1": 1,
            "S2": 1,
            "P2": 2,
            "S3": 2,
            "P3": 3,
            "S4": 3,
        }
        worst = min(severities, key=lambda s: _sev_ord.get(s, 99))

        sample_msgs: list[str] = []
        seen_msgs: set[str] = set()
        for inc in incidents:
            msg = (inc.get("error_detail") or inc.get("title") or "")[:200]
            if msg and msg not in seen_msgs:
                sample_msgs.append(msg)
                seen_msgs.add(msg)
                if len(sample_msgs) >= 5:
                    break

        sources = list({inc.get("source", "auto") for inc in incidents})
        error_class = _incident_key_regex(incidents[0])

        return {
            "signature": signature,
            "error_class": error_class,
            "incident_ids": [inc["id"] for inc in incidents if "id" in inc],
            "severity": worst,
            "count": len(incidents),
            "sample_messages": sample_msgs,
            "sources": sources,
        }
