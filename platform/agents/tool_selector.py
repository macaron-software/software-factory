"""BM25-based tool selector for prompt-aware tool filtering.

WHY: MiniMax M2.5 picks wrong tools when schema set is large (>10-15 tools).
Role-based filtering (ROLE_TOOL_MAP) reduces ~128→15-25 per role, but that's
still too many for reliable tool calling.

APPROACH: Score each tool's relevance to the current user prompt using Okapi BM25
on tool name + description text, then keep only top K tools. This is fast (O(n),
no API calls), deterministic, and adds <1ms per round.

INSPIRATION: Agentica (github.com/wrtnlabs/agentica) @agentica/vector-selector
uses embedding-based vector search to pre-filter functions before LLM selection.
We adapt the idea with BM25 instead of embeddings — same effect, zero latency,
no external API dependency. See: packages/vector-selector/src/select.ts

Ref: Robertson & Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond"
"""

from __future__ import annotations

import math
import re
from collections import Counter

# BM25 parameters (standard Okapi defaults)
_K1 = 1.5  # term frequency saturation
_B = 0.75  # document length normalization

# Default cap on tools sent to LLM after BM25 scoring
DEFAULT_TOP_K = 10

# Minimum BM25 score to consider a tool relevant.
# Tools scoring below this are excluded even if top_k is not reached.
_MIN_SCORE = 0.1

# --- Tokenizer -----------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z][a-z0-9]{1,}")


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alpha-numeric tokens (min 2 chars).

    Also splits snake_case and camelCase identifiers:
      'code_write' → ['code', 'write']
      'getProjectContext' → ['get', 'project', 'context']
    """
    # Expand snake_case
    text = text.replace("_", " ").replace("-", " ")
    # Expand camelCase
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return _TOKEN_RE.findall(text.lower())


# --- BM25 Index -----------------------------------------------------------


class ToolIndex:
    """Pre-computed BM25 index over tool schemas.

    Build once from the full schema list, then call :meth:`score` per prompt.
    Thread-safe after construction (read-only queries).
    """

    __slots__ = ("_docs", "_idf", "_avg_dl", "_names")

    def __init__(self, schemas: list[dict]) -> None:
        docs: dict[str, Counter] = {}
        for s in schemas:
            fn = s.get("function", {})
            name: str = fn.get("name", "")
            desc: str = fn.get("description", "")
            # Build document from name + description + parameter names
            parts = [name.replace("_", " "), desc]
            params = fn.get("parameters", {}).get("properties", {})
            if params:
                parts.extend(params.keys())
            text = " ".join(parts)
            docs[name] = Counter(_tokenize(text))

        # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        n = len(docs)
        df: Counter = Counter()
        for tokens in docs.values():
            for t in tokens:
                df[t] += 1
        self._idf = {
            t: math.log((n - freq + 0.5) / (freq + 0.5) + 1.0) for t, freq in df.items()
        }

        total_dl = sum(sum(d.values()) for d in docs.values())
        self._avg_dl = total_dl / max(n, 1)
        self._docs = docs
        self._names = list(docs.keys())

    def score(self, prompt: str) -> dict[str, float]:
        """Return {tool_name: BM25_score} for every indexed tool."""
        query_tokens = _tokenize(prompt)
        if not query_tokens:
            return {n: 0.0 for n in self._names}

        scores: dict[str, float] = {}
        for name, doc_tokens in self._docs.items():
            s = 0.0
            dl = sum(doc_tokens.values())
            for qt in query_tokens:
                tf = doc_tokens.get(qt, 0)
                if tf == 0:
                    continue
                idf = self._idf.get(qt, 0.0)
                numerator = tf * (_K1 + 1.0)
                denominator = tf + _K1 * (1.0 - _B + _B * dl / self._avg_dl)
                s += idf * numerator / denominator
            scores[name] = s
        return scores


# --- Tool affinity groups -------------------------------------------------
# Tools that belong to the same functional unit. When BM25 selects ANY member,
# all members of the group are included. This handles the limitation that BM25
# is keyword-based: "write a function" matches code_write but not code_read,
# yet code_read is always needed alongside code_write.

TOOL_GROUPS: list[set[str]] = [
    {"code_read", "code_write", "code_search", "code_edit", "list_files"},
    {"git_status", "git_log", "git_commit", "git_create_branch", "git_clone"},
    {"docker_deploy", "docker_status"},
    {"memory_search", "memory_store", "memory_retrieve", "memory_prune"},
    {"plan_create", "plan_update", "plan_get"},
    {"test", "android_test"},
    {"lsp_goto_definition", "lsp_find_references", "lsp_hover", "lsp_completions"},
    {"build", "lrm_build"},
    {"screenshot", "simulator_screenshot"},
    # Orchestration: CTO delegation tools must stay together
    {
        "create_project", "create_mission", "create_sub_mission",
        "compose_workflow", "launch_epic_run", "check_run_status",
        "resume_run", "create_sprint",
    },
]

# Reverse index: tool_name → group set
_TOOL_TO_GROUP: dict[str, set[str]] = {}
for _grp in TOOL_GROUPS:
    for _t in _grp:
        _TOOL_TO_GROUP[_t] = _grp


def _expand_groups(selected: set[str], available: set[str]) -> set[str]:
    """Expand selection to include all group members of selected tools."""
    expanded = set(selected)
    for name in list(selected):
        grp = _TOOL_TO_GROUP.get(name)
        if grp:
            expanded.update(grp & available)
    return expanded


# --- Selector (public API) ------------------------------------------------

# Module-level cached index (rebuilt when schema set changes)
_cached_index: ToolIndex | None = None
_cached_schema_count: int = 0


def _get_index(schemas: list[dict]) -> ToolIndex:
    """Return (possibly cached) BM25 index for the schema set."""
    global _cached_index, _cached_schema_count
    if _cached_index is not None and _cached_schema_count == len(schemas):
        return _cached_index
    _cached_index = ToolIndex(schemas)
    _cached_schema_count = len(schemas)
    return _cached_index


def select_tools(
    schemas: list[dict],
    prompt: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    always_include: set[str] | None = None,
    min_score: float = _MIN_SCORE,
) -> list[dict]:
    """Select top-K tools most relevant to *prompt* using BM25 scoring.

    Uses affinity groups to ensure functionally related tools stay together
    (e.g. selecting code_write automatically includes code_read, code_search).

    Parameters
    ----------
    schemas : list[dict]
        OpenAI-format tool schemas (already filtered by role-based ACL).
    prompt : str
        User's current message (or concatenation of recent messages).
    top_k : int
        Maximum number of tools to return. Defaults to 12.
    always_include : set[str] | None
        Tool names that must always be included (e.g. tools already called
        this session for continuity, or priority tools for nudge rounds).
    min_score : float
        Minimum BM25 score. Tools below this are excluded unless in
        *always_include*.

    Returns
    -------
    list[dict]
        Filtered + ranked subset of *schemas* (order preserved from original).
        If all scores are 0 (generic prompt with no tool keywords), returns
        *schemas* unchanged to avoid breaking tool calling entirely.
    """
    if len(schemas) <= top_k:
        return schemas  # already small enough

    always = always_include or set()
    available = {s.get("function", {}).get("name") for s in schemas}
    index = _get_index(schemas)
    scores = index.score(prompt)

    # If every score is 0, the prompt has no tool-relevant keywords.
    # Return all schemas rather than an empty set.
    if all(v < min_score for v in scores.values()):
        return schemas

    # Rank by score descending, pick strictly top_k best-scoring tools
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])

    selected: set[str] = set(always)
    for name, sc in ranked:
        if len(selected) >= top_k:
            break
        if sc >= min_score:
            selected.add(name)

    # If no tools scored above threshold (except always_include), return all
    if not any(scores.get(n, 0) >= min_score for n in selected - always):
        return schemas

    # Expand affinity groups (code_write → +code_read, code_search, etc.)
    selected = _expand_groups(selected, available)
    selected.update(always)

    # Post-expansion cap: if expansion pushed past hard limit,
    # keep highest-scoring tools (no re-expansion).
    hard_cap = top_k + 5
    if len(selected) > hard_cap:
        scored_list = sorted(
            ((n, scores.get(n, 0.0)) for n in selected if n not in always),
            key=lambda kv: -kv[1],
        )
        trimmed: set[str] = set(always)
        for name, _sc in scored_list:
            if len(trimmed) >= hard_cap:
                break
            trimmed.add(name)
        selected = trimmed

    # Return in original order (preserves schema ordering convention)
    return [s for s in schemas if s.get("function", {}).get("name") in selected]
