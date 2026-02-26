"""LLM Client — unified async interface for all providers.

All providers use OpenAI-compatible chat/completions API:
- Azure AI Foundry GPT-5.2 (swedencentral) — leaders, control, architecture
- NVIDIA/Kimi K2 (integrate.api.nvidia.com) — fast production workers
- MiniMax M2.5 (api.minimaxi.chat) — fallback, thinking model
- Claude CLI / Copilot CLI — offline headless (slow, 10-12s)

Streaming supported via SSE (text/event-stream).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Provider configs — OpenAI-compatible endpoints
_PROVIDERS = {
    "demo": {
        "name": "Demo (mock responses)",
        "base_url": "http://localhost",
        "key_env": "__DEMO__",
        "models": ["demo"],
        "default": "demo",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
    "azure-ai": {
        "name": "Azure AI Foundry (GPT-5.2)",
        "base_url": os.environ.get(
            "AZURE_AI_ENDPOINT", "https://swedencentral.api.cognitive.microsoft.com"
        ).rstrip("/"),
        "key_env": "AZURE_AI_API_KEY",
        "models": ["gpt-5.2"],
        "default": "gpt-5.2",
        "auth_header": "api-key",
        "auth_prefix": "",
        "azure_api_version": "2024-10-21",
        "azure_deployment_map": {"gpt-5.2": "gpt-52"},
        "max_tokens_param": {"gpt-5.2": "max_completion_tokens"},
    },
    "azure-openai": {
        "name": "Azure OpenAI (GPT-5-mini)",
        "base_url": os.environ.get(
            "AZURE_OPENAI_ENDPOINT", "https://ascii-ui-openai.openai.azure.com"
        ).rstrip("/"),
        "key_env": "AZURE_OPENAI_API_KEY",
        "models": ["gpt-5-mini"],
        "default": "gpt-5-mini",
        "auth_header": "api-key",
        "auth_prefix": "",
        "azure_api_version": "2025-01-01-preview",
        "azure_deployment_map": {"gpt-5-mini": "gpt-5-mini"},
        "max_tokens_param": {"gpt-5-mini": "max_completion_tokens"},
    },
    "nvidia": {
        "name": "NVIDIA (Kimi K2)",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "models": ["moonshotai/kimi-k2-instruct"],
        "default": "moonshotai/kimi-k2-instruct",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimaxi.chat/v1",
        "key_env": "MINIMAX_API_KEY",
        "models": ["MiniMax-M2.5", "MiniMax-M2.1"],
        "default": "MiniMax-M2.5",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
}

# Fallback order driven by PLATFORM_LLM_PROVIDER (local=minimax first, azure=azure-openai first)
# Auto-detect Azure when AZURE_OPENAI_API_KEY is present and no explicit provider set
_primary = os.environ.get("PLATFORM_LLM_PROVIDER") or (
    "azure-openai" if os.environ.get("AZURE_OPENAI_API_KEY") else "minimax"
)
_is_azure = os.environ.get("AZURE_DEPLOY", "") or os.environ.get("AZURE_OPENAI_API_KEY", "")
if _primary == "demo":
    _FALLBACK_CHAIN = ["demo"]
elif _is_azure:
    # Azure prod: use primary provider, fallback to others (excluding demo)
    _FALLBACK_CHAIN = [_primary] + [
        p for p in ["minimax", "azure-openai", "azure-ai", "openai"] if p != _primary
    ]
else:
    _FALLBACK_CHAIN = [_primary] + [
        p for p in ["minimax", "azure-openai", "azure-ai", "openai"] if p != _primary
    ]


class _RateLimiter:
    """Sliding window rate limiter with async queuing.

    Azure OpenAI gpt-5-mini: 100 req/60s, 100K tokens/60s.
    With ~12K tokens per agent call, we hit the token limit at ~8 req/min.
    Target: 6 req/60s to stay safely under token limit.
    """

    def __init__(self, max_requests: int = 6, window_seconds: float = 60.0):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self, timeout: float = 120.0):
        """Wait until a request slot is available. Raises TimeoutError after timeout."""
        deadline = time.monotonic() + timeout
        while True:
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self._window
                self._timestamps = [t for t in self._timestamps if t > cutoff]
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                # Calculate wait time until oldest request exits the window
                wait = self._timestamps[0] - cutoff
            if time.monotonic() + wait > deadline:
                raise TimeoutError(
                    f"Rate limiter: waited {timeout}s, still at capacity ({self._max} req/{self._window}s)"
                )
            await asyncio.sleep(min(wait + 0.1, 5.0))

    @property
    def usage(self) -> str:
        now = time.monotonic()
        cutoff = now - self._window
        active = sum(1 for t in self._timestamps if t > cutoff)
        return f"{active}/{self._max}"


# Global rate limiter (shared across all agents in this process)
_rate_limiter = _RateLimiter(
    max_requests=int(os.environ.get("LLM_RATE_LIMIT_RPM", "15")),
    window_seconds=60.0,
)


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None  # for role=tool responses
    tool_calls: list[dict] | None = None  # for assistant tool_calls


@dataclass
class LLMToolCall:
    id: str
    function_name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    finish_reason: str = "stop"
    tool_calls: list[LLMToolCall] = field(default_factory=list)


@dataclass
class LLMStreamChunk:
    delta: str
    done: bool = False
    model: str = ""
    finish_reason: str = ""


# Cost estimation: $/1M tokens (input, output) per model
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.2": (2.50, 10.00),
    "gpt-5-mini": (0.40, 1.60),
    "kimi-k2": (0.60, 2.40),
    "m1": (0.50, 2.00),
    "m2.5": (0.50, 2.00),
    "demo": (0.00, 0.00),
}
_DEFAULT_PRICING = (1.00, 4.00)  # fallback for unknown models

_USAGE_DB_PATH = Path(__file__).parent.parent.parent / "data" / "platform.db"


class LLMClient:
    """Async LLM client with multi-provider support, fallback, and circuit breaker."""

    # Circuit breaker: opens after FAIL_THRESHOLD errors in WINDOW seconds
    CB_FAIL_THRESHOLD = 5
    CB_WINDOW = 60  # seconds
    CB_OPEN_DURATION = 120  # seconds — how long circuit stays open

    def __init__(self):
        self._http: httpx.AsyncClient | None = None
        self._stats = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "errors": 0}
        self._usage_table_ready = False
        # Cooldown: provider → timestamp when it becomes available again
        self._provider_cooldown: dict[str, float] = {}
        # Circuit breaker: provider → list of failure timestamps
        self._cb_failures: dict[str, list[float]] = {}
        self._cb_open_until: dict[str, float] = {}
        # Context for observability tracing (set by caller before chat())
        self._trace_context: dict = {}  # agent_id, session_id, mission_id

    def _cb_record_failure(self, provider: str):
        """Record a failure for circuit breaker evaluation."""
        now = time.monotonic()
        fails = self._cb_failures.setdefault(provider, [])
        fails.append(now)
        # Trim old failures outside window
        cutoff = now - self.CB_WINDOW
        self._cb_failures[provider] = [t for t in fails if t > cutoff]
        if len(self._cb_failures[provider]) >= self.CB_FAIL_THRESHOLD:
            self._cb_open_until[provider] = now + self.CB_OPEN_DURATION
            self._cb_failures[provider] = []
            logger.error(
                "Circuit breaker OPEN for %s (%d failures in %ds) — blocked for %ds",
                provider,
                self.CB_FAIL_THRESHOLD,
                self.CB_WINDOW,
                self.CB_OPEN_DURATION,
            )

    def _cb_record_success(self, provider: str):
        """Reset failures on success (half-open → closed)."""
        self._cb_failures.pop(provider, None)
        self._cb_open_until.pop(provider, None)

    def _cb_is_open(self, provider: str) -> bool:
        """Check if circuit breaker is open for provider."""
        until = self._cb_open_until.get(provider, 0)
        if until > time.monotonic():
            return True
        if until > 0:
            # Half-open: allow one probe request
            self._cb_open_until.pop(provider, None)
        return False

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=300.0)
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def _get_provider_config(self, provider: str) -> dict:
        return _PROVIDERS.get(provider, _PROVIDERS.get("minimax", {}))

    def _get_api_key(self, pcfg: dict) -> str:
        env = pcfg.get("key_env", "")
        if not env:
            return "no-key"
        if env == "__DEMO__":
            return "demo-key"
        key = os.environ.get(env, "")
        if key:
            return key
        # Fallback: read from ~/.config/factory/<name>.key
        key_file = pcfg.get("key_file") or ""
        if not key_file:
            # Derive from env var name: NVIDIA_API_KEY → nvidia.key
            name = env.replace("_API_KEY", "").replace("_", "-").lower()
            key_file = os.path.expanduser(f"~/.config/factory/{name}.key")
        try:
            return Path(key_file).read_text().strip()
        except (OSError, FileNotFoundError):
            return ""

    def _demo_response(self, messages: list[LLMMessage]) -> LLMResponse:
        """Return a contextual mock response for demo mode.

        Generates role-aware, phase-aware, idea-aware responses so the demo
        feels realistic even without an LLM API key.
        """
        import hashlib

        last = messages[-1].content if messages else ""
        system = next((m.content for m in messages if m.role == "system"), "")
        lower = last.lower()
        sys_lower = system.lower()

        # Extract the user's idea from conversation context
        idea = ""
        for m in messages:
            if m.role == "user" and len(m.content) > 20:
                idea = m.content[:200]
                break
        idea_short = idea[:80] if idea else "the proposed solution"

        # Detect agent role from system prompt
        role = "analyst"
        if any(k in sys_lower for k in ["product manager", "product owner", "po "]):
            role = "pm"
        elif any(k in sys_lower for k in ["business analyst", "analyste métier"]):
            role = "ba"
        elif any(k in sys_lower for k in ["architect", "solution architect", "tech lead"]):
            role = "architect"
        elif any(k in sys_lower for k in ["ux", "designer", "ergonome"]):
            role = "ux"
        elif any(k in sys_lower for k in ["security", "sécurité", "pentest", "sast"]):
            role = "security"
        elif any(k in sys_lower for k in ["qa", "test", "quality"]):
            role = "qa"
        elif any(k in sys_lower for k in ["devops", "sre", "deploy"]):
            role = "devops"
        elif any(k in sys_lower for k in ["developer", "backend", "frontend", "dev "]):
            role = "dev"

        # Detect phase from message content
        phase = "analysis"
        if any(k in lower for k in ["brief", "présent", "introduce", "describe your"]):
            phase = "brief"
        elif any(k in lower for k in ["débat", "debate", "challenge", "round 2", "contre"]):
            phase = "debate"
        elif any(k in lower for k in ["synthèse", "synthesis", "conclusion", "final"]):
            phase = "synthesis"
        elif any(k in lower for k in ["risk", "risque"]):
            phase = "risks"

        # Use hash for deterministic variety
        h = int(hashlib.md5(f"{role}{phase}{idea[:30]}".encode()).hexdigest()[:8], 16)

        # Role + phase response matrix
        responses = {
            ("pm", "brief"): [
                f"I've framed this as a product opportunity. For \"{idea_short}\", the target market segments are B2B enterprise and B2C power users. Key differentiators: real-time capabilities, integration ecosystem, and mobile-first approach. I recommend starting with an MVP focused on the core value proposition — we can validate with 5 early adopter interviews before committing to the full roadmap.",
                f"Product brief prepared. \"{idea_short}\" addresses a clear market gap. I've identified 3 key personas and mapped their journeys. The competitive landscape shows 2 direct competitors but neither offers the integration depth we're targeting. Suggested go-to-market: freemium model with enterprise upsell.",
            ],
            ("pm", "synthesis"): [
                f"Synthesizing all expert input on \"{idea_short}\": the team converges on a modular architecture with 3 core modules for MVP. Key decisions: API-first approach (architect), progressive disclosure UX (designer), OAuth2 + RBAC from day 1 (security). Estimated MVP scope: 6 sprints. Risk mitigation: spike on the real-time sync component in sprint 1. I'll create the epic with 8 features and acceptance criteria.",
                f"Final synthesis: the team recommends proceeding with \"{idea_short}\" as a strategic initiative. Architecture: event-driven microservices. UX: mobile-responsive SPA with offline support. Security: zero-trust with encrypted data at rest. I'm structuring this into 1 epic, 5 features, and 23 user stories with WSJF prioritization.",
            ],
            ("ba", "analysis"): [
                f"Business analysis for \"{idea_short}\": I've mapped 4 business processes that this solution would optimize. Current pain points: manual workflows (est. 15h/week wasted), data silos between departments, and no real-time visibility. Expected ROI: 40% efficiency gain in the first quarter post-launch. Key stakeholders identified: operations team, finance, and end-users.",
                f"Functional analysis complete. For \"{idea_short}\", I've identified 12 functional requirements and 6 non-functional requirements. The main business rules center around data validation, workflow automation, and reporting. I recommend a phased rollout: Phase 1 (core CRUD + auth), Phase 2 (automation + integrations), Phase 3 (analytics + optimization).",
            ],
            ("architect", "analysis"): [
                f"Architecture proposal for \"{idea_short}\": I recommend a clean architecture with 3 layers — API gateway, business logic services, and data persistence. Tech stack: FastAPI for the backend (async, high performance), PostgreSQL for relational data, Redis for caching and real-time features. The system should handle 1000 concurrent users with <200ms p95 latency. Key risk: the real-time component needs WebSocket or SSE — I suggest SSE for simplicity.",
                f"Technical analysis for \"{idea_short}\": the domain decomposes into 4 bounded contexts. I propose a modular monolith initially (not microservices — too early) with clear module boundaries that allow future extraction. Database: PostgreSQL with JSONB for flexible schemas. API: REST with OpenAPI spec, versioned. Infrastructure: Docker + nginx, scalable to K8s when traffic justifies it.",
            ],
            ("architect", "debate"): [
                f"I challenge the monolith approach for \"{idea_short}\". Given the real-time requirements, we need event-driven communication from the start. However, I agree with the modular structure — let's use an internal event bus (in-process) that can be swapped for Kafka/NATS later. This gives us the best of both: simplicity now, scalability later. The database choice is solid but I'd add a read replica strategy for analytics queries.",
                f"Regarding the tech stack for \"{idea_short}\": the core proposal is sound but I see a concern with the caching strategy. Redis is good for sessions and hot data, but for the search functionality we should consider Elasticsearch or Meilisearch. Also, the API versioning strategy needs to be decided now — URL-based (/v1/) is simpler but header-based is cleaner. I recommend URL-based for the MVP.",
            ],
            ("ux", "analysis"): [
                f"UX analysis for \"{idea_short}\": the primary user flow has 7 steps — I can reduce it to 4 with smart defaults and progressive disclosure. Key design principles: minimal cognitive load, mobile-first responsive, accessibility AA compliant. I've sketched 3 key screens: dashboard (overview), detail view (contextual actions), and settings (progressive complexity). The onboarding should take <2 minutes with a guided wizard.",
                f"Design review for \"{idea_short}\": from a user perspective, the critical path is onboarding → first value moment. Target: user gets value within 3 minutes of signup. I recommend: 1) Social login (no form friction), 2) Interactive tutorial overlaid on real data, 3) Pre-populated templates. Color palette: professional blue/gray with accent green for CTAs. Typography: Inter for readability across devices.",
            ],
            ("security", "analysis"): [
                f"Security assessment for \"{idea_short}\": OWASP Top 10 review complete. Key requirements: 1) Authentication — OAuth2 + PKCE for SPA, JWT with short TTL (15min) + refresh tokens, 2) Authorization — RBAC with 4 roles minimum, 3) Data protection — AES-256 at rest, TLS 1.3 in transit, 4) Input validation — parameterized queries, CSP headers, rate limiting (100 req/min/user). No PII should be logged. Recommend SOC 2 compliance roadmap from sprint 1.",
                f"Threat model for \"{idea_short}\": identified 5 attack surfaces — API endpoints, file uploads, authentication flow, third-party integrations, and admin panel. Mitigation plan: WAF rules, input sanitization middleware, SAST in CI pipeline (bandit + semgrep), dependency scanning (Dependabot), and penetration testing at MVP completion. Secret management: environment variables with vault rotation. GDPR considerations: data minimization, right to erasure, consent tracking.",
            ],
            ("security", "debate"): [
                f"I have concerns about the proposed auth flow for \"{idea_short}\". JWT with 15min TTL is good, but the refresh token storage needs attention — HttpOnly cookies, not localStorage. Also, the RBAC model should support attribute-based access control (ABAC) for multi-tenant scenarios. I strongly recommend adding rate limiting on ALL endpoints, not just auth. The proposed CSP policy is too permissive — tighten 'script-src' to 'self' only.",
            ],
        }

        # Fallback per role (for phases not explicitly mapped)
        role_fallbacks = {
            "pm": f"From a product perspective, \"{idea_short}\" aligns with our strategic objectives. I've evaluated the market fit, identified key risks, and drafted acceptance criteria for the core features. Next step: stakeholder validation and WSJF scoring to prioritize against the current backlog.",
            "ba": f"I've completed the functional analysis for \"{idea_short}\". The business process mapping reveals 3 optimization opportunities. I've documented the requirements in user story format with acceptance criteria. Key assumption to validate: the integration with existing systems is feasible within the proposed timeline.",
            "architect": f"Technical assessment for \"{idea_short}\": the proposed architecture is sound for the expected scale. I recommend starting with a modular design that supports future decomposition. Key technical risks are manageable with proper spikes in sprint 1. Performance targets: <200ms API response, >99.5% uptime.",
            "ux": f"UX review for \"{idea_short}\": the user journey can be optimized to reduce friction by 60%. I recommend a progressive disclosure pattern with smart defaults. The mobile experience should be treated as primary, not responsive-adapted. Key metric to track: time-to-first-value (<3 minutes target).",
            "security": f"Security review for \"{idea_short}\": no critical blockers identified. The standard security stack (OAuth2, RBAC, CSP, rate limiting) covers the main threat vectors. I recommend adding SAST to the CI pipeline from day 1 and scheduling a penetration test before the first public release.",
            "qa": f"Quality plan for \"{idea_short}\": I recommend a testing pyramid — 70% unit tests, 20% integration tests, 10% E2E tests. Target coverage: 80% minimum for business logic. Non-functional testing: load test (1000 concurrent users), accessibility audit (WCAG AA), and cross-browser validation (Chrome, Firefox, Safari).",
            "devops": f"Infrastructure plan for \"{idea_short}\": Docker containers orchestrated with docker-compose for dev/staging, Kubernetes for production. CI/CD: GitHub Actions with build → test → SAST → deploy pipeline. Monitoring: Prometheus + Grafana with alerting on error rate >1% and p95 latency >500ms. Blue-green deployment for zero-downtime releases.",
            "dev": f"Implementation plan for \"{idea_short}\": I'll structure the codebase with clean architecture — controllers, services, repositories. TDD approach for core business logic. API-first development with OpenAPI spec. Estimated effort for MVP: 4-6 sprints depending on integration complexity. I'll start with the data model and API contracts.",
            "analyst": f"Analysis for \"{idea_short}\": I've reviewed the requirements and identified key success criteria. The proposed approach is feasible with the current team and tech stack. Main risks: scope creep and third-party API dependencies. I recommend time-boxing the discovery phase and committing to a fixed MVP scope.",
        }

        key = (role, phase)
        if key in responses:
            options = responses[key]
            content = options[h % len(options)]
        else:
            content = role_fallbacks.get(role, role_fallbacks["analyst"])

        return LLMResponse(
            content=content,
            model="demo",
            provider="demo",
            tokens_in=len(last) // 4,
            tokens_out=len(content) // 4,
            duration_ms=50 + (h % 200),
            finish_reason="stop",
        )

    def _build_url(self, pcfg: dict, model: str) -> str:
        base = pcfg["base_url"].rstrip("/")
        if pcfg.get("azure_api_version") and base:
            # Azure uses deployment-based URLs; map model name → deployment name
            dep_map = pcfg.get("azure_deployment_map", {})
            deployment = dep_map.get(model, model)
            return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={pcfg['azure_api_version']}"
        return f"{base}/chat/completions"

    def _build_headers(self, pcfg: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        key = self._get_api_key(pcfg)
        if pcfg.get("auth_header") and key:
            headers[pcfg["auth_header"]] = f"{pcfg.get('auth_prefix', '')}{key}"
        return headers

    async def chat(
        self,
        messages: list[LLMMessage],
        provider: str = "minimax",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request. Falls back to next provider on failure."""
        # ── Cache lookup (deterministic dedup) ──
        from .cache import get_cache
        _llm_cache = get_cache()
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        cache_model = model or provider
        cached = _llm_cache.get(cache_model, msg_dicts, temperature, tools)
        if cached:
            logger.info("LLM cache HIT (%s, saved %d tokens)", cache_model, cached["tokens_in"] + cached["tokens_out"])
            return LLMResponse(
                content=cached["content"],
                tokens_in=cached["tokens_in"],
                tokens_out=cached["tokens_out"],
                model=cache_model,
                provider="cache",
            )

        if _is_azure:
            provider = "azure-openai"
        providers_to_try = [provider] + [p for p in _FALLBACK_CHAIN if p != provider]

        for prov in providers_to_try:
            # Skip unknown providers
            if prov not in _PROVIDERS:
                logger.warning("LLM %s skipped (unknown provider)", prov)
                continue

            # Skip providers in cooldown (rate-limited recently)
            now = time.monotonic()
            cooldown_until = self._provider_cooldown.get(prov, 0)
            if cooldown_until > now:
                remaining = int(cooldown_until - now)
                logger.warning(
                    "LLM %s in cooldown (%ds left), skipping → fallback", prov, remaining
                )
                continue

            # Skip providers with open circuit breaker
            if self._cb_is_open(prov):
                logger.warning("LLM %s circuit breaker OPEN, skipping → fallback", prov)
                continue

            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not key or key == "no-key":
                if prov != "demo":
                    logger.warning("LLM %s skipped (no API key)", prov)
                    continue

            # Demo mode: return mock response without HTTP call
            if prov == "demo":
                return self._demo_response(messages)

            use_model = (
                model
                if (prov == provider and model and model in pcfg.get("models", []))
                else pcfg["default"]
            )

            # Rate limiter: queue until a slot is available
            try:
                await _rate_limiter.acquire(timeout=180.0)
            except TimeoutError:
                logger.error(
                    "LLM rate limiter timeout (180s) — queue full (%s)", _rate_limiter.usage
                )
                continue

            logger.warning("LLM trying %s/%s ... [rate: %s]", prov, use_model, _rate_limiter.usage)
            last_exc = None
            max_attempts = 3  # Retry within provider, then fall back to next
            for attempt in range(max_attempts):
                try:
                    result = await self._do_chat(
                        pcfg,
                        prov,
                        use_model,
                        messages,
                        temperature,
                        max_tokens,
                        system_prompt,
                        tools,
                    )
                    self._stats["calls"] += 1
                    self._stats["tokens_in"] += result.tokens_in
                    self._stats["tokens_out"] += result.tokens_out
                    logger.warning(
                        "LLM %s/%s OK (%d in, %d out tokens)",
                        prov,
                        use_model,
                        result.tokens_in,
                        result.tokens_out,
                    )
                    self._cb_record_success(prov)
                    # Trace for observability
                    self._trace(result, messages)
                    await self._persist_usage(prov, use_model, result.tokens_in, result.tokens_out)
                    # Cache the response for future dedup
                    try:
                        _llm_cache.put(cache_model, msg_dicts, temperature, result.content, result.tokens_in, result.tokens_out, tools)
                    except Exception:
                        pass
                    return result
                except Exception as exc:
                    last_exc = exc
                    err_str = repr(exc)
                    is_rate_limit = "429" in err_str or "RateLimitReached" in err_str
                    is_transient = (
                        "ReadError" in err_str
                        or "ConnectError" in err_str
                        or "RemoteProtocolError" in err_str
                    )
                    if attempt < max_attempts - 1 and (is_transient or is_rate_limit):
                        import random

                        # Exponential backoff with jitter: 10s, 20s, 40s, 80s
                        base = (2**attempt) * (10 if is_rate_limit else 3)
                        jitter = random.uniform(0, base * 0.3)
                        delay = min(base + jitter, 90)
                        logger.warning(
                            "LLM %s/%s %s (attempt %d/%d): %s — retrying in %ds",
                            prov,
                            use_model,
                            "rate-limited" if is_rate_limit else "transient",
                            attempt + 1,
                            max_attempts,
                            err_str[:120],
                            int(delay),
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(
                        "LLM %s/%s failed after %d attempts: %s",
                        prov,
                        use_model,
                        attempt + 1,
                        err_str[:200],
                    )
                    self._stats["errors"] += 1
                    self._cb_record_failure(prov)
                    await self._persist_usage(prov, use_model, 0, 0, error=True)
                    if is_rate_limit:
                        self._provider_cooldown[prov] = time.monotonic() + 90
                        logger.warning(
                            "LLM %s → cooldown 90s (rate limited), falling back to next provider",
                            prov,
                        )
                continue

        raise RuntimeError(f"All LLM providers failed for {provider}/{model}")

    async def _do_chat(
        self,
        pcfg: dict,
        provider: str,
        model: str,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)

        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            # Accept both LLMMessage objects and plain dicts
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                tool_call_id = m.get("tool_call_id")
                tool_calls = m.get("tool_calls")
            else:
                role = m.role
                content = m.content or ""
                name = m.name
                tool_call_id = m.tool_call_id
                tool_calls = m.tool_calls
            d = {"role": role, "content": content}
            # MiniMax rejects system messages after position 0
            if d["role"] == "system" and provider == "minimax" and msgs:
                d["role"] = "user"
                d["content"] = f"[System instruction]: {d['content']}"
            if name:
                d["name"] = name
            if tool_call_id:
                d["tool_call_id"] = tool_call_id
            if tool_calls:
                d["tool_calls"] = tool_calls
                d.pop("content", None)  # assistant tool_call msgs may have no content
            msgs.append(d)

        body = {
            "model": model,
            "messages": msgs,
        }
        # GPT-5-mini only supports temperature=1 (default)
        if not (model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex")):
            body["temperature"] = temperature
        # MiniMax uses <think> blocks that consume tokens — boost limit
        # GPT-5-mini is a reasoning model — needs extra tokens for internal reasoning
        effective_max = max_tokens
        if provider == "minimax":
            effective_max = max(max_tokens, 16000)
        elif model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex"):
            effective_max = max(max_tokens, 8000)
        # Some models (gpt-5.2) use max_completion_tokens instead of max_tokens
        mt_param = pcfg.get("max_tokens_param", {}).get(model, "max_tokens")
        body[mt_param] = effective_max

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        t0 = time.monotonic()

        # Retry loop for 429 rate limits (3 attempts with exponential backoff)
        import random

        for attempt in range(3):
            resp = await http.post(url, json=body, headers=headers)
            if resp.status_code != 429:
                break
            retry_after = int(resp.headers.get("Retry-After", (2**attempt) * 10))
            retry_after = max(retry_after, 10)
            retry_after = min(retry_after + random.randint(0, 5), 90)
            logger.warning(
                "LLM %s/%s rate-limited (429), retry in %ds (attempt %d/3) [rate: %s]",
                provider,
                model,
                retry_after,
                attempt + 1,
                _rate_limiter.usage,
            )
            await asyncio.sleep(retry_after)

        elapsed = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or [{}]
        choice = choices[0] if choices else {}
        msg = choice.get("message", {})
        content = msg.get("content", "") or ""
        # Strip <think> blocks from MiniMax
        if "<think>" in content and "</think>" in content:
            idx = content.index("</think>") + len("</think>")
            after_think = content[idx:].strip()
            if after_think:
                content = after_think
            else:
                # finish_reason=length: think block consumed all tokens
                # Extract useful reasoning from think block as fallback
                think_start = content.index("<think>") + len("<think>")
                think_end = content.index("</think>")
                content = content[think_start:think_end].strip()
        elif "<think>" in content and "</think>" not in content:
            # Incomplete think block (truncated by max_tokens)
            think_start = content.index("<think>") + len("<think>")
            content = content[think_start:].strip()

        # Parse tool calls from response
        parsed_tool_calls = []
        raw_tool_calls = msg.get("tool_calls") or []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            parsed_tool_calls.append(
                LLMToolCall(
                    id=tc.get("id", ""),
                    function_name=fn.get("name", ""),
                    arguments=args,
                )
            )

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=provider,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            duration_ms=elapsed,
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=parsed_tool_calls,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        provider: str = "minimax",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream chat completion response with provider fallback."""
        if _is_azure:
            provider = "azure-openai"
        providers_to_try = [provider] + [p for p in _FALLBACK_CHAIN if p != provider]

        for prov in providers_to_try:
            if prov not in _PROVIDERS:
                continue
            now = time.monotonic()
            cooldown_until = self._provider_cooldown.get(prov, 0)
            if cooldown_until > now:
                continue
            if self._cb_is_open(prov):
                continue
            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not key or key == "no-key":
                if prov != "demo":
                    continue

            # Demo mode: yield mock response as stream
            if prov == "demo":
                resp = self._demo_response(messages)
                words = resp.content.split()
                for i, word in enumerate(words):
                    yield LLMStreamChunk(delta=(" " if i else "") + word, done=False, model="demo")
                    await asyncio.sleep(0.02)
                yield LLMStreamChunk(delta="", done=True, model="demo", finish_reason="stop")
                return
            use_model = (
                model
                if (prov == provider and model and model in pcfg.get("models", []))
                else pcfg["default"]
            )

            # Rate limiter: queue until a slot is available
            try:
                await _rate_limiter.acquire(timeout=180.0)
            except TimeoutError:
                logger.error("LLM stream rate limiter timeout (%s)", _rate_limiter.usage)
                continue

            max_attempts = 4
            for attempt in range(max_attempts):
                try:
                    async for chunk in self._do_stream(
                        pcfg, prov, use_model, messages, temperature, max_tokens, system_prompt
                    ):
                        yield chunk
                    self._cb_record_success(prov)
                    return
                except Exception as exc:
                    err_str = repr(exc)
                    is_rate_limit = "429" in err_str or "RateLimitReached" in err_str
                    is_transient = (
                        "ReadError" in err_str
                        or "ConnectError" in err_str
                        or "RemoteProtocolError" in err_str
                        or "ServerDisconnected" in err_str
                    )
                    if attempt < max_attempts - 1 and (is_rate_limit or is_transient):
                        import random

                        delay = min((2**attempt) * 10 + random.uniform(0, 5), 90)
                        logger.warning(
                            "LLM stream %s/%s %s (attempt %d/%d) — retrying in %ds",
                            prov,
                            use_model,
                            "rate-limited" if is_rate_limit else "transient error",
                            attempt + 1,
                            max_attempts,
                            int(delay),
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(
                        "LLM stream %s/%s failed: %s — trying next", prov, use_model, err_str[:200]
                    )
                    self._cb_record_failure(prov)
                    if is_rate_limit:
                        self._provider_cooldown[prov] = time.monotonic() + 30
                    break

        raise RuntimeError(f"All LLM providers failed for streaming {provider}/{model}")

    async def _do_stream(
        self,
        pcfg: dict,
        provider: str,
        model: str,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        system_prompt: str,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Single-provider streaming attempt."""
        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)
        logger.warning("LLM stream trying %s/%s ...", provider, model)

        msgs = []
        sys_content = system_prompt or ""
        for m in messages:
            d = {"role": m.role, "content": m.content or ""}
            if m.name:
                d["name"] = m.name
            if provider == "minimax":
                # MiniMax rejects system role in streaming
                if d["role"] == "system":
                    if not msgs:
                        sys_content = (
                            (sys_content + "\n\n" + d["content"]).strip()
                            if sys_content
                            else d["content"]
                        )
                    else:
                        d["role"] = "user"
                        d["content"] = f"[System instruction]: {d['content']}"
                        msgs.append(d)
                    continue
                # MiniMax rejects tool messages — skip tool results and assistant tool_call messages
                if d["role"] == "tool":
                    continue
                if d["role"] == "assistant" and getattr(m, "tool_calls", None):
                    continue
            else:
                if m.tool_call_id:
                    d["tool_call_id"] = m.tool_call_id
                if m.tool_calls:
                    d["tool_calls"] = m.tool_calls
                    d.pop("content", None)
            msgs.append(d)
        # Inject system prompt
        if sys_content:
            if provider == "minimax":
                for i, m in enumerate(msgs):
                    if m["role"] == "user":
                        msgs[i]["content"] = (
                            f"[System instructions]:\n{sys_content}\n\n[User message]:\n{m['content']}"
                        )
                        break
                else:
                    msgs.insert(0, {"role": "user", "content": sys_content})
            else:
                msgs.insert(0, {"role": "system", "content": sys_content})

        effective_max = max_tokens
        if provider == "minimax":
            effective_max = max(max_tokens, 16000)
        elif model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex"):
            effective_max = max(max_tokens, 8000)

        mt_param = pcfg.get("max_tokens_param", {}).get(model, "max_tokens")
        body = {
            "model": model,
            "messages": msgs,
            mt_param: effective_max,
            "stream": True,
        }
        # GPT-5-mini only supports temperature=1 (default)
        if not (model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex")):
            body["temperature"] = temperature

        # Use a separate client for streaming to avoid blocking the shared client
        stream_http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        )
        try:
            async with stream_http.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    raise RuntimeError(f"HTTP {resp.status_code}: {text[:200]}")
                logger.warning("LLM stream %s/%s connected", provider, model)
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        yield LLMStreamChunk(delta="", done=True, model=model)
                        return
                    try:
                        data = json.loads(payload)
                        choices = data.get("choices") or [{}]
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        finish = choices[0].get("finish_reason")
                        if content:
                            yield LLMStreamChunk(delta=content, model=model)
                        if finish:
                            yield LLMStreamChunk(
                                delta="", done=True, model=model, finish_reason=finish
                            )
                            return  # MiniMax doesn't send [DONE], exit on finish_reason
                    except json.JSONDecodeError:
                        continue
        finally:
            await stream_http.aclose()

    def set_trace_context(self, agent_id: str = "", session_id: str = "", mission_id: str = ""):
        """Set context for observability tracing on subsequent calls."""
        self._trace_context = {
            "agent_id": agent_id,
            "session_id": session_id,
            "mission_id": mission_id,
        }

    def _trace(self, result: LLMResponse, messages: list[LLMMessage]):
        """Record LLM call in observability store."""
        try:
            from .observability import get_tracer

            ctx = self._trace_context
            input_preview = ""
            if messages:
                last = messages[-1]
                input_preview = (
                    last.content if isinstance(last, LLMMessage) else last.get("content", "")
                )[:200]
            get_tracer().trace_call(
                provider=result.provider,
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                duration_ms=result.duration_ms,
                agent_id=ctx.get("agent_id", ""),
                session_id=ctx.get("session_id", ""),
                mission_id=ctx.get("mission_id", ""),
                input_preview=input_preview,
                output_preview=result.content[:200] if result.content else "",
            )
        except Exception as exc:
            logger.debug("Trace recording failed: %s", exc)

    def available_providers(self) -> list[dict]:
        """List providers with availability status."""
        result = []
        for pid, pcfg in _PROVIDERS.items():
            key = self._get_api_key(pcfg)
            has_key = bool(key and key != "no-key") or not pcfg.get("key_env")
            result.append(
                {
                    "id": pid,
                    "name": pcfg["name"],
                    "models": pcfg["models"],
                    "default": pcfg["default"],
                    "enabled": has_key,
                    "has_key": has_key,
                }
            )
        return result

    # ── LLM usage persistence ──────────────────────────────────────

    def _ensure_usage_table(self):
        """Create llm_usage table if it doesn't exist (called once lazily)."""
        if self._usage_table_ready:
            return
        _USAGE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_USAGE_DB_PATH))
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS llm_usage (
                id TEXT PRIMARY KEY,
                ts TEXT,
                provider TEXT,
                model TEXT,
                tokens_in INT,
                tokens_out INT,
                cost_estimate REAL,
                agent_id TEXT,
                mission_id TEXT,
                phase TEXT,
                error INT DEFAULT 0
            )""")
            conn.commit()
        finally:
            conn.close()
        self._usage_table_ready = True

    def _estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost in USD based on per-model pricing."""
        price_in, price_out = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
        return (tokens_in * price_in + tokens_out * price_out) / 1_000_000

    async def _persist_usage(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        error: bool = False,
    ):
        """Insert a usage row into the llm_usage SQLite table (non-blocking)."""
        try:
            ctx = self._trace_context
            row = (
                uuid.uuid4().hex,
                datetime.now(timezone.utc).isoformat(),
                provider,
                model,
                tokens_in,
                tokens_out,
                self._estimate_cost(model, tokens_in, tokens_out),
                ctx.get("agent_id", ""),
                ctx.get("mission_id", ""),
                ctx.get("phase", ""),
                1 if error else 0,
            )

            def _insert():
                self._ensure_usage_table()
                conn = sqlite3.connect(str(_USAGE_DB_PATH))
                try:
                    conn.execute(
                        "INSERT INTO llm_usage (id,ts,provider,model,tokens_in,tokens_out,"
                        "cost_estimate,agent_id,mission_id,phase,error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        row,
                    )
                    conn.commit()
                finally:
                    conn.close()

            await asyncio.to_thread(_insert)
        except Exception as exc:
            logger.debug("Usage persistence failed: %s", exc)

    async def aggregate_usage(self, days: int = 7) -> dict:
        """Return cost/day, cost/phase, cost/agent breakdowns for the last N days."""

        def _query():
            self._ensure_usage_table()
            conn = sqlite3.connect(str(_USAGE_DB_PATH))
            try:
                cutoff = f"datetime('now', '-{days} days')"
                by_day = conn.execute(
                    f"SELECT date(ts) AS day, SUM(cost_estimate), SUM(tokens_in), SUM(tokens_out), COUNT(*)"
                    f" FROM llm_usage WHERE ts >= {cutoff} GROUP BY day ORDER BY day"
                ).fetchall()
                by_phase = conn.execute(
                    f"SELECT phase, SUM(cost_estimate), COUNT(*)"
                    f" FROM llm_usage WHERE ts >= {cutoff} GROUP BY phase ORDER BY SUM(cost_estimate) DESC"
                ).fetchall()
                by_agent = conn.execute(
                    f"SELECT agent_id, SUM(cost_estimate), SUM(tokens_in), SUM(tokens_out), COUNT(*)"
                    f" FROM llm_usage WHERE ts >= {cutoff} GROUP BY agent_id ORDER BY SUM(cost_estimate) DESC"
                ).fetchall()
                totals = conn.execute(
                    f"SELECT SUM(cost_estimate), SUM(tokens_in), SUM(tokens_out), COUNT(*), SUM(error)"
                    f" FROM llm_usage WHERE ts >= {cutoff}"
                ).fetchone()
                return {
                    "days": days,
                    "total": {
                        "cost": totals[0] or 0,
                        "tokens_in": totals[1] or 0,
                        "tokens_out": totals[2] or 0,
                        "calls": totals[3] or 0,
                        "errors": totals[4] or 0,
                    },
                    "by_day": [
                        {
                            "day": r[0],
                            "cost": r[1],
                            "tokens_in": r[2],
                            "tokens_out": r[3],
                            "calls": r[4],
                        }
                        for r in by_day
                    ],
                    "by_phase": [
                        {"phase": r[0] or "(none)", "cost": r[1], "calls": r[2]} for r in by_phase
                    ],
                    "by_agent": [
                        {
                            "agent_id": r[0] or "(none)",
                            "cost": r[1],
                            "tokens_in": r[2],
                            "tokens_out": r[3],
                            "calls": r[4],
                        }
                        for r in by_agent
                    ],
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    @property
    def stats(self) -> dict:
        s = dict(self._stats)
        s["rate_limiter"] = _rate_limiter.usage
        return s


# Singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
