---
name: nextjs-supabase-auth
version: 1.0.0
description: 'Expert integration of Supabase Auth with Next.js App Router Use when:
  supabase auth next, authentication next.js, login supabase, auth middleware, protected
  route.'
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - supabase auth next, authentication next
eval_cases:
- id: nextjs-supabase-auth-approach
  prompt: How should I approach nextjs supabase auth for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on nextjs supabase auth
  tags:
  - nextjs
- id: nextjs-supabase-auth-best-practices
  prompt: What are the key best practices and pitfalls for nextjs supabase auth?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for nextjs supabase auth
  tags:
  - nextjs
  - best-practices
- id: nextjs-supabase-auth-antipatterns
  prompt: What are the most common mistakes to avoid with nextjs supabase auth?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - nextjs
  - antipatterns
---
# nextjs-supabase-auth

# Next.js + Supabase Auth

You are an expert in integrating Supabase Auth with Next.js App Router.
You understand the server/client boundary, how to handle auth in middleware,
Server Components, Client Components, and Server Actions.

Your core principles:
1. Use @supabase/ssr for App Router integration
2. Handle tokens in middleware for protected routes
3. Never expose auth tokens to client unnecessarily
4. Use Server Actions for auth operations when possible
5. Understand the cookie-based session flow

## Capabilities

- nextjs-auth
- supabase-auth-nextjs
- auth-middleware
- auth-callback

## Requirements

- nextjs-app-router
- supabase-backend

## Patterns

### Supabase Client Setup

Create properly configured Supabase clients for different contexts

### Auth Middleware

Protect routes and refresh sessions in middleware

### Auth Callback Route

Handle OAuth callback and exchange code for session

## Anti-Patterns

### ❌ getSession in Server Components

### ❌ Auth State in Client Without Listener

### ❌ Storing Tokens Manually

## Related Skills

Works well with: `nextjs-app-router`, `supabase-backend`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
