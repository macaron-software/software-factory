# Macaron Agent Platform — Copilot Instructions

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (from the parent _SOFTWARE_FACTORY/ directory)
python -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none

# IMPORTANT: Do NOT use --reload (conflicts with stdlib `platform` module name)
# IMPORTANT: --ws none is required (SSE is used instead of WebSockets)
# The DB is auto-created at startup in platform/data/platform.db
```

Required env vars:
```bash
AZURE_OPENAI_API_KEY      # Azure OpenAI (primary LLM)
AZURE_OPENAI_ENDPOINT     # e.g. https://castudioiatestopenai.openai.azure.com/
# Optional fallback providers:
MINIMAX_API_KEY           # MiniMax M2.5
GLM_API_KEY               # Zhipu GLM-4.7
```

## Architecture

**FastAPI + HTMX + SSE** — no frontend build step, no WebSocket. The server renders Jinja2 templates, and HTMX handles dynamic updates via HTML-over-the-wire.

### Core Layers

```
Web (routes.py, templates/)        ← HTMX endpoints, Jinja2 HTML
Sessions (runner.py)               ← User→Agent bridge, SSE events
Agents (executor.py, rlm.py)      ← Tool-calling loop, RLM deep search
Orchestrator (engine.py)           ← Pattern execution (8 agentic patterns)
A2A (bus.py, protocol.py)         ← Inter-agent messaging with veto hierarchy
LLM (client.py)                    ← Multi-provider with automatic fallback
Memory (manager.py, project_files.py) ← 4-layer memory + auto-loaded project files
DB (migrations.py, schema.sql)     ← SQLite + FTS5, WAL mode
```

### Agent Execution Flow

The tool-calling engine in `agents/executor.py` runs a loop (max 10 rounds):
1. Build system prompt (agent persona + skills + project memory + context)
2. Call LLM with OpenAI-compatible tool schemas
3. If LLM returns `tool_calls` → execute tools → feed results back → repeat
4. If LLM returns text → done

Tools: `code_read`, `code_search`, `code_write`, `code_edit`, `git_status`, `git_log`, `git_diff`, `memory_search`, `memory_store`, `list_files`, `deep_search` (triggers RLM)

### RLM (Recursive Language Model)

`agents/rlm.py` implements arXiv:2512.24601 — iterative WRITE-EXECUTE-OBSERVE-DECIDE loop:
- **Orchestrator LLM** generates 1-3 exploration queries per iteration
- **Sub-agents** execute queries in parallel (grep, file read, structure) — deterministic, no LLM
- Findings accumulated (max 8K chars, recent prioritized), up to 10 iterations
- Triggered when the chat agent calls the `deep_search` tool

### LLM Client

`llm/client.py` — multi-provider with automatic fallback chain: `azure → azure-ai → minimax → nvidia → local`.

Key method: `LLMClient.chat(messages, provider, model, temperature, max_tokens, system_prompt, tools) → LLMResponse`

Provider-specific quirks:
- Azure OpenAI uses `max_completion_tokens` (not `max_tokens`)
- MiniMax returns `<think>` blocks that get stripped automatically
- The client is a singleton: `get_llm_client()`

### Project Memory

`memory/project_files.py` auto-loads instruction files from each project's directory (in priority order): `CLAUDE.md`, `.github/copilot-instructions.md`, `SPECS.md`, `VISION.md`, `README.md`, `.cursorrules`, `CONVENTIONS.md`. Max 3K chars/file, 8K total. Injected into every LLM system prompt.

## Key Conventions

### Data layer: Dataclass + Store singletons

All domain objects are Python `@dataclass` (not Pydantic internally). Each module exposes a store singleton:

```python
from ..agents.store import get_agent_store    # → AgentStore (CRUD for AgentDef)
from ..projects.manager import get_project_store  # → ProjectStore (CRUD for Project)
from ..sessions.store import get_session_store    # → SessionStore
from ..patterns.store import get_pattern_store    # → PatternStore
from ..memory.manager import get_memory_manager   # → MemoryManager (4-layer)
from ..llm.client import get_llm_client          # → LLMClient singleton
```

Stores use raw `sqlite3` via `get_db()` from `db.migrations`. Row-to-dataclass conversion is done by `_row_to_*()` helper functions.

### Templates: Jinja2 + HTMX

All templates extend `base.html` which provides two blocks:
- `{% block topbar_actions %}` — right side of the top bar
- `{% block content %}` — main area

HTMX patterns used throughout:
- `hx-get`/`hx-post` for async loads
- `hx-target` + `hx-swap="innerHTML"` or `"beforeend"` for partial updates
- `hx-trigger="load, every 30s"` for polling sections (git status, tasks)
- `hx-indicator` for loading states

Markdown rendering: the Jinja2 environment has a `markdown` filter (`{{ content | markdown | safe }}`), backed by the `markdown` library with `fenced_code`, `tables`, `nl2br` extensions.

### CSS: Dark purple theme with CSS variables

All colors/spacing defined as CSS variables in `:root` in `main.css`:
- `--bg-primary: #0f0a1a`, `--bg-secondary: #1a1128`, `--bg-tertiary: #251a35`
- `--purple: #a855f7`, `--purple-light: #c084fc`, `--accent: #f78166`
- `--sidebar-width: 56px`, `--radius: 10px`
- Font stack: `--font-mono: 'JetBrains Mono', monospace`

### View modes

All list pages use a unified `.item-grid[data-view-grid]` + `.item-card` structure with 4 switchable modes: `card`, `card-simple`, `list`, `list-compact`. The switcher partial is in `partials/view_switcher.html`.

### Import style

Always use relative imports within the package:
```python
from ..db.migrations import get_db
from ..agents.store import get_agent_store
from ..llm.client import LLMMessage, get_llm_client
```

Use `from __future__ import annotations` at the top of files that use forward references.

### Module naming

The package is called `platform` which shadows Python's stdlib `platform` module. This means:
- **Never** `import platform` at the top level in any file within this package
- **Never** use `--reload` with uvicorn (it re-imports and hits the naming conflict)
- Always run from the parent directory: `python -m uvicorn platform.server:app`

### Tool schema cache

`executor.py` caches tool schemas in a global `_TOOL_SCHEMAS`. If you add/modify tools, the cache is only refreshed on server restart (or by setting `_TOOL_SCHEMAS = None`).
