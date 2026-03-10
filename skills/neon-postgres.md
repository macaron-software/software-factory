---
name: neon-postgres
version: 1.0.0
description: 'Expert patterns for Neon serverless Postgres, branching, connection
  pooling, and Prisma/Drizzle integration Use when: neon database, serverless postgres,
  database branching, neon postgres, postgres...'
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - neon database, serverless postgres, database branching, neon postgres, postgres
eval_cases:
- id: neon-postgres-approach
  prompt: How should I approach neon postgres for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on neon postgres
  tags:
  - neon
- id: neon-postgres-best-practices
  prompt: What are the key best practices and pitfalls for neon postgres?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for neon postgres
  tags:
  - neon
  - best-practices
- id: neon-postgres-antipatterns
  prompt: What are the most common mistakes to avoid with neon postgres?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - neon
  - antipatterns
---
# neon-postgres

# Neon Postgres

## Patterns

### Prisma with Neon Connection

Configure Prisma for Neon with connection pooling.

Use two connection strings:
- DATABASE_URL: Pooled connection for Prisma Client
- DIRECT_URL: Direct connection for Prisma Migrate

The pooled connection uses PgBouncer for up to 10K connections.
Direct connection required for migrations (DDL operations).


### Drizzle with Neon Serverless Driver

Use Drizzle ORM with Neon's serverless HTTP driver for
edge/serverless environments.

Two driver options:
- neon-http: Single queries over HTTP (fastest for one-off queries)
- neon-serverless: WebSocket for transactions and sessions


### Connection Pooling with PgBouncer

Neon provides built-in connection pooling via PgBouncer.

Key limits:
- Up to 10,000 concurrent connections to pooler
- Connections still consume underlying Postgres connections
- 7 connections reserved for Neon superuser

Use pooled endpoint for application, direct for migrations.


## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | high | See docs |
| Issue | high | See docs |
| Issue | high | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | low | See docs |
| Issue | medium | See docs |
| Issue | high | See docs |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
