# Decisions — Software Factory

## ADOPTED
- **HTMX over SPA**: SSE + Jinja2, no React/Vue bundling
- **PostgreSQL only**: SQLite deprecated, advisory locks per mission
- **Feather SVG**: no emoji, no FontAwesome
- **JWT+bcrypt auth**: 15min access, 7d refresh, rate 5/min/IP
- **Infisical vault**: .env = bootstrap only
- **Thompson Sampling**: skill selection (Beta α/β per skill)
- **Darwin GA**: team fitness evolution nightly

## REJECTED
- `--reload` flag: debug only, banned in prod
- WebSocket: SSE only (`--ws none`)
- Mock data: LIVE PG only
- `test.skip` / silent fallback: always fix root cause

## REVERSED
- SQLite → PG (2024-03): `data/platform.db` now stale
- Backup crypto key hardcoded in firmware: UART/JTAG needed
