# Supabase Lite — Documentation (Living Status)

## Status: 🔄 NOT STARTED

**Current Milestone**: 1 — Project Scaffold  
**Last Updated**: —

---

## Milestone Progress

| # | Name | Status | Notes |
|---|------|--------|-------|
| 1 | Project Scaffold | ⏳ Pending | |
| 2 | Auth (register + login) | ⏳ Pending | |
| 3 | REST API (CRUD) | ⏳ Pending | |
| 4 | Realtime (WebSocket) | ⏳ Pending | |
| 5 | Storage | ⏳ Pending | |
| 6 | Dashboard SQL Editor | ⏳ Pending | |
| 7 | CI + E2E | ⏳ Pending | |

---

## How to Run

```bash
# Start full stack
docker compose up -d --build

# API: http://localhost:3000
# Dashboard: http://localhost:5173
# DB: postgres://localhost:5432/supabase_lite

# Tests
cd api && npm test
npx playwright test
```

---

## Decisions Made
- Fastify over Express: better TypeScript, faster
- pg direct over Prisma: lighter, full SQL control for RLS
- Vitest over Jest: faster, native ESM
- Local filesystem for Storage v1

## Known Issues / Blockers
— (none yet)

## Next Steps
1. Start Milestone 1: scaffold monorepo + Docker Compose
