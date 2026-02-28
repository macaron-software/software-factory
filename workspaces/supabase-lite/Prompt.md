# Supabase Lite — Prompt (Agent Kickoff Contract)

## Goal
Build a self-hosted, open-source alternative to Supabase / Firebase from scratch.
The application must be **production-ready enough to demo end-to-end**, not merely scaffolded.

## What is Supabase Lite?
A backend-as-a-service platform exposing:
1. **REST API** — auto-generated CRUD from PostgreSQL tables (PostgREST-style)
2. **Realtime API** — WebSocket subscriptions to table changes via PostgreSQL NOTIFY
3. **Auth** — JWT + bcrypt login/register, OAuth2 skeleton (Google), Row-Level Security policies
4. **Storage** — S3-compatible file upload/download via local filesystem or MinIO adapter
5. **Dashboard** — React SPA to manage tables, users, storage, and API keys

## Technology Stack (hard constraints)
- **API server**: Node.js 20 + TypeScript + Fastify
- **Database**: PostgreSQL 16 (Docker Compose)
- **Auth**: JWT (jsonwebtoken), bcrypt, Passport.js OAuth skeleton
- **Realtime**: WebSocket (ws library) + `pg_notify`
- **Storage**: Fastify multipart + local `./uploads/` folder
- **Dashboard**: React 18 + Vite + Tailwind CSS
- **Tests**: Vitest (unit) + Playwright (E2E)
- **Build**: tsc, esbuild for API; Vite for dashboard
- **CI**: GitHub Actions (build + test + lint on push)
- **Linting**: ESLint + Prettier

## Non-Goals (out of scope for v1)
- Kubernetes / Helm (Docker Compose only)
- Multi-tenant SaaS billing
- Edge Functions / Deno runtime
- Full PostgREST feature parity (filtering, joins, etc. are v2)

## Hard Constraints
- Every feature must have passing unit tests before merge
- API must be typed end-to-end (no `any` except adapter boundaries)
- All secrets via `.env` — zero hardcoded credentials
- Docker Compose `up` must produce a working stack in < 60s
- `npm run lint && npm run build && npm run test` must pass before milestone close

## Deliverables
When done, the following must be true:
1. `docker compose up` starts API + DB + dashboard on localhost
2. `POST /auth/register` + `POST /auth/login` returns JWT
3. Authenticated `GET /rest/v1/todos` returns rows from `todos` table
4. WebSocket `/realtime/v1` pushes INSERT events to connected clients
5. `POST /storage/v1/objects/bucket/file.png` uploads a file
6. Dashboard SPA loads, shows tables list, allows running a SQL query
7. `npm run test` → all tests green
8. `npx playwright test` → E2E journey green

## Done When
- [ ] `docker compose up` → healthy stack
- [ ] Auth flow works (register → login → protected route)
- [ ] REST CRUD on `todos` table
- [ ] Realtime subscription fires on INSERT
- [ ] File upload and download via Storage API
- [ ] Dashboard: tables view + SQL editor
- [ ] CI pipeline green (GitHub Actions)
- [ ] `npm run test` → 0 failures
