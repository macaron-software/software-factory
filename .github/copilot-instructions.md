# Copilot Instructions for MACARON-SOFTWARE Monorepo

## Overview

This is a complex **multi-project monorepo** containing several distinct systems:

- **YOLONOW**: Event discovery platform (Rust backend + Next.js web + iOS/Android mobile)
- **_PSY**: Psychological analysis system (Python + Playwright)
- **_SOFTWARE_FACTORY**: RLM (Recursive Learning Machine) - Multi-agent orchestration system with adversarial code review
- **PIERRE**: User profiling engine
- **Fervenza**: Microservices framework
- Other specialized tools and experiments

## High-Level Architecture

### YOLONOW - Event Discovery Platform

**Tech Stack**: Rust (Axum) + Next.js + Swift/Kotlin

**Core Components**:
- **Backend** (`YOLONOW/backend`): Rust with PostGIS + H3 spatial grid for ultra-fast geolocation queries (5ms P95 vs 280ms baseline)
- **Frontend Web** (`YOLONOW/frontend/web`): Next.js 14 with TanStack Query, Leaflet maps, Zustand state
- **Frontend Mobile**: iOS (SwiftUI) + Android (Jetpack Compose)
- **Data**: PostgreSQL 15 + PostGIS + Redis caching

**Key Architectural Decision**: Uses Uber-style H3 spatial grid instead of PostGIS ST_DWithin for 56x query performance improvement. Events stored compressed in bytea, decompressed client-side.

### _SOFTWARE_FACTORY - RLM (Recursive Learning Machine)

This system orchestrates AI agents with a "Team of Rivals" adversarial approach:

**Core Philosophy**:
- **Multi-Agent Cascade**: Tasks flow through specialized agents (planning, execution, review)
- **Adversarial Code Review**: Swiss Cheese model with 4 layers (L0 fast checks → L1a code critic → L1b security → L2 architecture)
- **Zero-Skip Policy**: NEVER use `--skip-*` flags, `test.skip()`, `@ts-ignore`, or skip deploy checks. Fix root causes instead.
- **TDD First**: All changes start with tests

**Key Files**:
- `_SOFTWARE_FACTORY/CLAUDE.md`: Complete philosophy and patterns
- `_SOFTWARE_FACTORY/agents/`: Agent implementations
- `_SOFTWARE_FACTORY/core/`: Core RLM engine

**Important**: This factory is for project orchestration, not direct code changes to YOLONOW etc.

### _PSY - Psychological Analysis

**Tech Stack**: Python + Playwright E2E testing

**Critical Rule**: ALL interactions use the `liact` CLI for deployments.
- **FORBIDDEN**: Direct git commands, npx, manual SSH fixes
- **REQUIRED**: `liact env pipeline -m "message"` for any deployment
- Uses strict E2E testing gates before production deployment

## Build & Test Commands

### YOLONOW Backend (Rust)

```bash
# Development
cd YOLONOW/backend
cargo build
cargo run

# Tests
cargo test                    # All tests
cargo test test_name         # Single test
cargo test -- --nocapture   # With output

# Linting
cargo fmt --check            # Check formatting
cargo clippy                 # Linting

# Build release
cargo build --release
```

**Key Files**:
- `YOLONOW/Cargo.toml`: Workspace definition
- `YOLONOW/backend/Cargo.toml`: Backend deps
- `YOLONOW/backend/src/main.rs`: Entry point

### YOLONOW Frontend Web (Next.js)

```bash
cd YOLONOW/frontend/web

# Development
npm run dev                   # http://localhost:3000

# Tests
npm run test                 # Vitest suite
npm test -- --ui            # Interactive test UI

# Linting & type checking
npm run lint                 # ESLint
npm run type-check           # TypeScript check

# Build
npm run build
npm start                    # Production server
```

**Key Patterns**:
- `lib/hooks/`: Custom React hooks
- `lib/store.ts`: Zustand state management
- `components/`: Reusable components
- `app/`: Next.js app directory

### _PSY Project

```bash
cd _PSY

# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python -m _psy.main

# Tests
pytest tests/

# Deployment (ALWAYS use this, NEVER manual git)
liact env pipeline -m "feat: description"
liact test labs              # E2E test Labs API
liact test patient           # E2E test Patient API
```

## Key Conventions

### 1. Monorepo Organization

Each project is **self-contained** with its own:
- `.claude/` or `.opencode/` for project-specific instructions
- `CLAUDE.md` for detailed patterns
- `package.json` / `Cargo.toml` / `pyproject.toml`
- Tests directory

**Work in project subdirectories**, not root. Don't assume all scripts work from monorepo root.

### 2. Git & Deployment Strategy

- **_PSY & Factory**: Use `liact` CLI exclusively - NEVER direct git/push
- **YOLONOW**: Use normal git workflow with CI/CD in `YOLONOW/.github/workflows/`
- **Commit format**: `<type>(<scope>): <description>` per CONTRIBUTING.md

### 3. Code Quality Gates

**Mandatory before any PR/deployment**:
- **Rust**: `cargo fmt` + `cargo clippy` (zero warnings)
- **TypeScript/JavaScript**: `npm run lint` + `npm run type-check`
- **Python**: `ruff check` + `black --check`
- **Tests**: Must pass locally before pushing

### 4. Multi-Vendor LLM Strategy (_SOFTWARE_FACTORY only)

The factory uses different LLM providers for cognitive diversity:
- **Brain**: Claude Opus 4.5 (reasoning)
- **TDD Worker**: MiniMax M2.1 (fast, cheap)
- **Code Critic**: MiniMax M2.1 (same perspective as worker to find gaps)
- **Security Critic**: GLM-4.7-free (different provider = fresh perspective)
- **Architecture Critic**: Claude Opus 4.5

**Why**: "The same reasoning process that produced the answer cannot reliably evaluate it."

### 5. ZERO SKIP Policy (_SOFTWARE_FACTORY & _PSY)

**ABSOLUTELY FORBIDDEN:**
- `test.skip()`, `#[ignore]`, `@ts-ignore`
- `--skip-deploy`, `--skip-test`, `--skip-*` flags
- Manual hotfixes without Factory feedback loop
- SSH into production to fix manually

**When something fails**:
1. Analyze root cause
2. Create feedback task
3. Let the system fix via TDD
4. Retry deployment

### 6. Database Migrations (YOLONOW)

```bash
cd YOLONOW/backend

# Create migration
sqlx migrate add -r migration_name

# Run migrations
sqlx migrate run

# Revert
sqlx migrate revert
```

Use SQLx for compile-time checked queries. Always test migrations locally before pushing.

### 7. Environment Variables

**YOLONOW Backend** (`.env.example`):
```
DATABASE_URL=postgresql://user:pass@localhost/yolonow
REDIS_URL=redis://localhost:6379
PORT=8000
```

**_PSY** (`.env.example`):
```
LIACT_API_KEY=...
LIACT_ENV=staging|production
```

Never commit actual `.env` files. Use `.env.example` for template.

### 8. H3 Spatial Grid (YOLONOW specific)

Events use H3 Level 7 cells (~1.2km hexagons) instead of raw coordinates:
- Queries return matching `h3_cell` values, not ST_DWithin
- Client side decompresses and filters events
- Massive performance gain: 56x faster, 70% bandwidth reduction

**When working on location features**: Think in terms of H3 cells, not latitude/longitude calculations.

### 9. Pre-commit Hooks

Projects have pre-commit hooks for:
- Linting
- Type checking
- Unit tests (YOLONOW)

**YOLONOW** setup:
```bash
cd YOLONOW
./setup_pre_commit.sh
```

The hooks MUST pass before commits are allowed.

## Debugging & Development

### Local Development Setup

**YOLONOW full stack**:
```bash
# Terminal 1: Database & Cache
cd YOLONOW
docker-compose up -d postgres redis

# Terminal 2: Backend
cd YOLONOW/backend
cargo run

# Terminal 3: Frontend
cd YOLONOW/frontend/web
npm run dev

# Terminal 4: Migrations (if needed)
cd YOLONOW/backend
sqlx migrate run
```

### Troubleshooting

**Rust compilation issues**: Delete `target/` and `Cargo.lock` rebuild with `cargo clean && cargo build`

**Next.js build fails**: Clear `.next/` and reinstall: `rm -rf .next node_modules && npm install && npm run build`

**E2E tests timeout**: Increase timeout in `playwright.config.ts` or check if localhost services are running

**Database connection refused**: Verify Docker containers running: `docker ps | grep postgres`

## Project-Specific Notes

### YOLONOW

- **Frontend Web**: Uses Leaflet.js + OpenStreetMap (not Google Maps - free)
- **Caching Strategy**: Client-side H3 cell cache with 70% hit rate
- **API Format**: REST + GraphQL endpoints available
- **Testing**: Vitest for web, cargo test for Rust
- **CI/CD**: 4 separate workflows (backend, web, iOS, Android)

### _SOFTWARE_FACTORY

- **Execution**: Everything runs through agent cascade, NEVER manual
- **Feedback Loop**: When something fails, task is created automatically with error analysis
- **Self-Modification**: Factory can improve itself based on failure patterns
- **MCP Servers**: Playwright, custom LRM (Local Resource Manager)

### _PSY

- **Strict Gates**: E2E tests block production deployments
- **CLI-First**: Use `liact` for everything deployment-related
- **Test Matrix**: Labs API, Patient API, Unit tests must all pass

## MCP Servers Available

The monorepo has configured:
- **Playwright-MCP** (`.playwright-mcp/`): Browser automation, E2E test execution
- **Custom LRM**: Local resource management for _SOFTWARE_FACTORY

These are used by Claude/Copilot when appropriate and don't require explicit invocation.

## Additional Resources

- **YOLONOW**: `YOLONOW/ARCHITECTURE.md`, `YOLONOW/DEPLOYMENT.md`, `YOLONOW/CONTRIBUTING.md`
- **_SOFTWARE_FACTORY**: `_SOFTWARE_FACTORY/CLAUDE.md` (comprehensive)
- **_PSY**: `_PSY/CLAUDE.md` (strict deployment rules)

---

**Last Updated**: 2025-02-08
**Contact**: Refer to individual project docs for specific questions
