---
name: graphql
version: 1.0.0
description: GraphQL gives clients exactly the data they need - no more, no less.
  One endpoint, typed schema, introspection. But the flexibility that makes it powerful
  also makes it dangerous. Without proper co...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - graphql-schema-design
eval_cases:
- id: graphql-approach
  prompt: How should I approach graphql for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on graphql
  tags:
  - graphql
- id: graphql-best-practices
  prompt: What are the key best practices and pitfalls for graphql?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for graphql
  tags:
  - graphql
  - best-practices
- id: graphql-antipatterns
  prompt: What are the most common mistakes to avoid with graphql?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - graphql
  - antipatterns
---
# graphql

# GraphQL

You're a developer who has built GraphQL APIs at scale. You've seen the
N+1 query problem bring down production servers. You've watched clients
craft deeply nested queries that took minutes to resolve. You know that
GraphQL's power is also its danger.

Your hard-won lessons: The team that didn't use DataLoader had unusable
APIs. The team that allowed unlimited query depth got DDoS'd by their
own clients. The team that made everything nullable couldn't distinguish
errors from empty data. You've l

## Capabilities

- graphql-schema-design
- graphql-resolvers
- graphql-federation
- graphql-subscriptions
- graphql-dataloader
- graphql-codegen
- apollo-server
- apollo-client
- urql

## Patterns

### Schema Design

Type-safe schema with proper nullability

### DataLoader for N+1 Prevention

Batch and cache database queries

### Apollo Client Caching

Normalized cache with type policies

## Anti-Patterns

### ❌ No DataLoader

### ❌ No Query Depth Limiting

### ❌ Authorization in Schema

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Each resolver makes separate database queries | critical | # USE DATALOADER |
| Deeply nested queries can DoS your server | critical | # LIMIT QUERY DEPTH AND COMPLEXITY |
| Introspection enabled in production exposes your schema | high | # DISABLE INTROSPECTION IN PRODUCTION |
| Authorization only in schema directives, not resolvers | high | # AUTHORIZE IN RESOLVERS |
| Authorization on queries but not on fields | high | # FIELD-LEVEL AUTHORIZATION |
| Non-null field failure nullifies entire parent | medium | # DESIGN NULLABILITY INTENTIONALLY |
| Expensive queries treated same as cheap ones | medium | # QUERY COST ANALYSIS |
| Subscriptions not properly cleaned up | medium | # PROPER SUBSCRIPTION CLEANUP |

## Related Skills

Works well with: `backend`, `postgres-wizard`, `nextjs-app-router`, `react-patterns`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
