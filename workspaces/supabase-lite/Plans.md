# Supabase Lite — Plans (Milestones)

## Rules (agents MUST follow)
- Complete milestones **in order** — no skipping
- After each milestone: run `npm run lint && npm run build && npm run test`
- If validation fails: **fix immediately** before moving to next milestone
- Update `Documentation.md` at the end of each milestone
- Max 3 consecutive test failures → stop and report blockers

---

## Milestone 1 — Project Scaffold
**Goal**: Runnable monorepo with Docker Compose, empty API and Dashboard.

Tasks:
- [ ] `docker-compose.yml` with `postgres:16`, `api` service, `dashboard` service
- [ ] `api/package.json` + `tsconfig.json` + `vitest.config.ts`
- [ ] `api/src/index.ts` — Fastify server, `/health` returns `{status:"ok"}`
- [ ] `api/src/db.ts` — pg Pool connected to Postgres env vars
- [ ] `db/init.sql` — users, api_keys, todos tables
- [ ] `dashboard/package.json` + `vite.config.ts`
- [ ] `dashboard/src/App.tsx` — minimal React app, shows "Supabase Lite"
- [ ] `.env.example` — all required vars documented
- [ ] `README.md` — setup in < 5 commands

Validation:
```bash
docker compose up -d --build
curl http://localhost:3000/health   # → {"status":"ok"}
npm run lint && npm run build
```

---

## Milestone 2 — Auth (register + login + JWT)
**Goal**: Working authentication layer.

Tasks:
- [ ] `api/src/auth/routes.ts` — POST /auth/register, POST /auth/login
- [ ] bcrypt password hashing (cost=12)
- [ ] JWT signing (HS256) with 24h expiry
- [ ] `api/src/auth/middleware.ts` — `authenticate` Fastify plugin
- [ ] Unit tests: register happy path, login happy path, wrong password, duplicate email
- [ ] Dashboard `Auth.tsx` — login form, stores JWT in localStorage

Validation:
```bash
npm run test -- auth
curl -X POST http://localhost:3000/auth/register -d '{"email":"test@ex.com","password":"secret123"}'
curl -X POST http://localhost:3000/auth/login -d '{"email":"test@ex.com","password":"secret123"}'
# Both return {token: "..."}
```

---

## Milestone 3 — REST API (CRUD over PostgreSQL)
**Goal**: Auto-generated CRUD for public schema tables.

Tasks:
- [ ] `api/src/rest/routes.ts` — GET/POST/PATCH/DELETE /rest/v1/:table
- [ ] Query builder: limit (default 100), offset, order (asc/desc), eq filter
- [ ] JWT auth enforced on all REST routes
- [ ] Input validation: table must exist in pg_catalog, no SQL injection
- [ ] Unit tests: list todos, insert todo, update todo, delete todo, 401 on missing JWT
- [ ] Dashboard `Tables.tsx` — table selector, rows grid, basic insert form

Validation:
```bash
npm run test -- rest
TOKEN=$(curl -s -X POST .../auth/login ... | jq -r .token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/rest/v1/todos
```

---

## Milestone 4 — Realtime (WebSocket + pg_notify)
**Goal**: Live table change subscriptions.

Tasks:
- [ ] PostgreSQL trigger function on todos INSERT → NOTIFY
- [ ] `api/src/realtime/server.ts` — WebSocket server, authenticate via JWT param
- [ ] Subscribe message: `{"type":"subscribe","table":"todos"}`
- [ ] Broadcast INSERT/UPDATE/DELETE payloads to subscribed clients
- [ ] Unit test: mock pg NOTIFY → client receives event
- [ ] Dashboard: live todos list with WebSocket feed

Validation:
```bash
npm run test -- realtime
# Open two browser tabs: insert a todo in one → other updates immediately
```

---

## Milestone 5 — Storage (file upload/download)
**Goal**: S3-compatible file storage via local filesystem.

Tasks:
- [ ] `api/src/storage/routes.ts` — POST /storage/v1/objects/:bucket/*
- [ ] Multipart upload, save to `./uploads/<bucket>/<uuid>-<name>`
- [ ] GET /storage/v1/objects/:bucket/* — stream file download
- [ ] Bucket auto-create on first upload
- [ ] Security: path traversal prevention, mime type validation
- [ ] Unit tests: upload PNG, download PNG, 404 on missing file
- [ ] Dashboard `Storage.tsx` — bucket list, file upload widget, file list

Validation:
```bash
npm run test -- storage
curl -X POST -F "file=@test.png" -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/storage/v1/objects/avatars/test.png
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/storage/v1/objects/avatars/test.png -o downloaded.png
```

---

## Milestone 6 — Dashboard SQL Editor + API Keys
**Goal**: Admin tooling in the dashboard.

Tasks:
- [ ] Dashboard `SqlEditor.tsx` — textarea, run button, results table
- [ ] API endpoint: POST /admin/query (admin role only) — executes SQL, returns rows
- [ ] API Keys CRUD: POST/GET/DELETE /auth/keys
- [ ] Dashboard: API keys management page
- [ ] Unit tests: query endpoint auth check, key generation

Validation:
```bash
npm run test -- admin
# Dashboard: login as admin, run "SELECT * FROM todos", see results
```

---

## Milestone 7 — CI + E2E Tests
**Goal**: GitHub Actions green, Playwright E2E passing.

Tasks:
- [ ] `.github/workflows/ci.yml` — lint + build + test on push/PR
- [ ] `tests/e2e/journey.spec.ts` — full user journey:
  1. Register → login → get JWT
  2. Create a todo via REST
  3. Subscribe to realtime → insert todo → receive event
  4. Upload a file → download it
  5. Dashboard loads, SQL editor executes query
- [ ] Fix any CI failures

Validation:
```bash
npm run lint && npm run build && npm run test
npx playwright test  # all green
```

---

## Decision Log
| Date | Decision | Reason |
|------|----------|--------|
| — | Fastify over Express | Better TypeScript support, faster |
| — | pg over Prisma | Lighter, direct SQL control for RLS |
| — | Vitest over Jest | Faster, native ESM |
| — | Local filesystem for storage | No cloud deps for v1 |
