"""
Multi-stage error clustering for the platform auto-heal engine.

Groups similar incidents into clusters to reduce alert noise.
Three-stage approach (ported from airweave-ai/error-monitoring-agent, MIT):
  1. Strict  — exact (error_type, source) match
  2. Regex   — error_type prefix / HTTP code / exception class
  3. LLM     — semantic similarity for remaining unclustered errors

The LLM stage uses the platform LLMClient (no external dependency).
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, Optional

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
        self._llm: Any = None  # lazy-loaded

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

        # Stage 3: LLM (only if ≥2 unclustered incidents)
        if len(remaining) >= 2:
            try:
                llm_clusters = await self._llm_cluster(remaining)
                logger.debug("Clustering stage3 (LLM): %d clusters", len(llm_clusters))
            except Exception as exc:
                logger.warning(
                    "LLM clustering failed (%s) — fallback to single clusters", exc
                )
                llm_clusters = [self._make_cluster([inc]) for inc in remaining]
        elif remaining:
            llm_clusters = [self._make_cluster([inc]) for inc in remaining]
        else:
            llm_clusters = []

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

    # ------------------------------------------------------------------
    # Stage 3 — LLM semantic clustering
    # ------------------------------------------------------------------

    async def _llm_cluster(self, incidents: list[dict]) -> list[dict]:
        llm = await self._get_llm()
        if llm is None:
            return [self._make_cluster([inc]) for inc in incidents]

        from ..llm.client import LLMMessage

        summaries = []
        for i, inc in enumerate(incidents[:20]):  # cap at 20 for context
            msg = inc.get("error_detail") or inc.get("title") or "unknown"
            summaries.append(f"{i}: [{inc.get('error_type', '?')}] {msg[:120]}")

        prompt = (
            "You are grouping error incidents by root cause.\n"
            "Given these incidents (index: description), output a JSON object with key 'groups':\n"
            "a list of lists of indices that belong together.\n"
            "Each index must appear exactly once. Similar errors (same root cause) go in the same group.\n"
            'Example: {"groups": [[0,2,5],[1,3],[4]]}\n\n'
            "Incidents:\n" + "\n".join(summaries)
        )
        response = await llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,
            max_tokens=512,
        )
        try:
            raw = response.content.strip()
            # strip ```json fences if present
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            groups_indices: list[list[int]] = data.get("groups", [])
        except Exception as exc:
            logger.warning("LLM cluster JSON parse failed (%s)", exc)
            return [self._make_cluster([inc]) for inc in incidents]

        # Validate indices
        seen: set[int] = set()
        result = []
        for group in groups_indices:
            valid = [i for i in group if 0 <= i < len(incidents) and i not in seen]
            if valid:
                seen.update(valid)
                result.append(self._make_cluster([incidents[i] for i in valid]))

        # Any index not covered → solo cluster
        for i, inc in enumerate(incidents):
            if i not in seen:
                result.append(self._make_cluster([inc]))

        return result

    # ------------------------------------------------------------------
    # Signature generation
    # ------------------------------------------------------------------

    async def generate_signature(self, incidents: list[dict]) -> str:
        """Generate a natural-language signature for a cluster using the LLM."""
        llm = await self._get_llm()
        if llm is None:
            return self._fallback_signature(incidents[0])

        from ..llm.client import LLMMessage

        msgs = [
            (inc.get("error_detail") or inc.get("title") or "unknown")[:120]
            for inc in incidents[:5]
        ]
        prompt = (
            "Create a short natural-language signature (50–120 chars) for this group of errors.\n"
            "Focus on the root cause, not specific variable data.\n"
            "Examples: 'Rate limiting (HTTP 429) during file downloads', "
            "'DB connection timeouts in sync worker'\n\n"
            "Errors:\n" + "\n".join(f"- {m}" for m in msgs) + "\n\nSignature:"
        )
        response = await llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,
            max_tokens=128,
        )
        sig = response.content.strip().strip('"').strip("'")
        return sig[:150] if sig else self._fallback_signature(incidents[0])

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

    # ------------------------------------------------------------------
    # LLM lazy loader
    # ------------------------------------------------------------------

    async def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        try:
            from ..llm.client import LLMClient, get_llm_client

            try:
                self._llm = get_llm_client()
            except Exception:
                self._llm = LLMClient()
        except Exception as exc:
            logger.warning("Could not load LLMClient for clustering: %s", exc)
            self._llm = None
        return self._llm
