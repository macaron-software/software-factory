---
description: Python code in platform/ — FastAPI, async, PG-only
globs: platform/**/*.py
---

- `import platform` is FORBIDDEN (shadows stdlib). Use `from platform.X import Y`.
- All DB queries use parameterized placeholders (`?` or `%s`). Zero f-strings in SQL.
- No `test.skip`, `@ts-ignore`, `pass` stubs, `return {}`, or `TODO` placeholders.
- No `*_API_KEY=dummy` or hardcoded secrets. Use Infisical or env vars.
- Error handling must be explicit. No silent `except: pass`.
- PostgreSQL only. No SQLite in platform code. Use `get_db()` adapter.
- SSE only (`--ws none`). No WebSocket.
- No `--reload` flag in uvicorn commands.
- NodeStatus enum: PENDING, RUNNING, COMPLETED, VETOED, FAILED. No DONE.
- Async functions: always `await` every Promise/coroutine. No fire-and-forget.
