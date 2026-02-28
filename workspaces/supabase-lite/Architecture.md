# Supabase Lite — Architecture

## Principles
1. **Typed end-to-end** — TypeScript strict mode, no implicit `any`
2. **Single source of truth** — PostgreSQL is authoritative; API reflects DB schema
3. **Stateless API** — JWT auth, no server-side sessions
4. **Event-driven Realtime** — pg_notify → WebSocket fan-out
5. **Deterministic IDs** — UUIDs v4 from `crypto.randomUUID()`
6. **Isolated storage** — files stored in `./uploads/<bucket>/<uuid>.<ext>`
7. **12-factor config** — all config via environment variables

## Directory Structure
```
supabase-lite/
├── api/                    # Fastify API server
│   ├── src/
│   │   ├── index.ts        # Entry point — registers all plugins
│   │   ├── db.ts           # PostgreSQL pool (pg library)
│   │   ├── auth/           # JWT + bcrypt + OAuth skeleton
│   │   │   ├── routes.ts
│   │   │   └── middleware.ts
│   │   ├── rest/           # Auto CRUD from DB tables
│   │   │   └── routes.ts
│   │   ├── realtime/       # WebSocket + pg_notify
│   │   │   └── server.ts
│   │   ├── storage/        # File upload/download
│   │   │   └── routes.ts
│   │   └── types.ts        # Shared types
│   ├── package.json
│   ├── tsconfig.json
│   └── vitest.config.ts
├── db/
│   ├── init.sql            # Schema + seed data
│   └── rls.sql             # Row-Level Security policies
├── dashboard/              # React SPA
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Tables.tsx
│   │   │   ├── SqlEditor.tsx
│   │   │   ├── Auth.tsx
│   │   │   └── Storage.tsx
│   │   └── api/client.ts   # Typed API client
│   ├── package.json
│   └── vite.config.ts
├── tests/
│   └── e2e/
│       └── journey.spec.ts  # Playwright E2E
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml
```

## Data Model (DB)
```sql
-- Core tables (created in db/init.sql)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT DEFAULT 'user',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  key TEXT UNIQUE NOT NULL,
  name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Example app table (seed for demo)
CREATE TABLE todos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  text TEXT NOT NULL,
  done BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

## API Routes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | — | Create user, return JWT |
| POST | /auth/login | — | Login, return JWT |
| GET | /rest/v1/:table | JWT | List rows (limit/offset) |
| POST | /rest/v1/:table | JWT | Insert row |
| PATCH | /rest/v1/:table/:id | JWT | Update row |
| DELETE | /rest/v1/:table/:id | JWT | Delete row |
| GET | /realtime/v1 | JWT | WebSocket upgrade |
| POST | /storage/v1/objects/:bucket/* | JWT | Upload file |
| GET | /storage/v1/objects/:bucket/* | JWT | Download file |
| GET | /health | — | Health check |

## Realtime Architecture
```
Client ──WS──▶ RealtimeServer
                 ↓ subscribes on connect
               pg LISTEN channel_<table>
                 ↑
             PostgreSQL trigger → NOTIFY channel_<table>, row_json
```

## Auth Architecture
```
Register: email+password → bcrypt hash → INSERT users → sign JWT (HS256, 24h)
Login: email+password → SELECT users → bcrypt compare → sign JWT
Protected routes: Authorization: Bearer <jwt> → verify → req.user
```

## Invariants (must never change)
- JWT secret from `JWT_SECRET` env var only
- File paths: `uploads/<bucket>/<uuid>-<originalname>` (no traversal)
- REST API: only exposes tables in `public` schema
- RLS: enabled on all user tables; agents must not bypass
