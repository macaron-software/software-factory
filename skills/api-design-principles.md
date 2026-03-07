---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/api-design-principles
# WHY: SF architecture agents need concrete REST/API design patterns to enforce
#      consistent, developer-friendly APIs across all projects.
name: api-design-principles
version: "1.0.0"
description: >
  REST and API design principles for intuitive, scalable, maintainable APIs.
  Use when designing new APIs, reviewing API specs, establishing team standards,
  or refactoring existing endpoints for better consistency.
metadata:
  category: development
  triggers:
    - "when designing REST API endpoints"
    - "when reviewing API specifications"
    - "when user mentions endpoint design, HTTP methods, or status codes"
    - "when establishing API versioning strategy"
    - "when designing pagination, filtering, or error responses"
    - "when reviewing API for consistency or developer experience"
# EVAL CASES
eval_cases:
  - id: resource-naming
    prompt: |
      Review this API design:
      POST /createUser
      GET /getUserById?id=42
      PUT /updateUserData
      DELETE /deleteUser?id=42
    should_trigger: true
    checks:
      - "regex:noun|resource|path.*param|/users|REST.*convention|verb.*in.*URL|action.*URL"
      - "regex:POST.*/users|GET.*/users/|DELETE.*/users/"
      - "length_min:80"
    expectations:
      - "identifies verb-in-URL anti-pattern (createUser, getUserById, etc.)"
      - "recommends noun-based resource paths: POST /users, GET /users/{id}, DELETE /users/{id}"
      - "explains RESTful resource naming conventions"
    tags: [naming, resources, rest]

  - id: error-response-design
    prompt: |
      Our API returns different error formats:
      {"error": "not found"} — from one endpoint
      {"message": "User not found", "code": 404} — from another
      {"success": false, "msg": "validation failed"} — from a third
    should_trigger: true
    checks:
      - "regex:consistent|standar|RFC.*7807|problem.*detail|error.*format|schema|contract"
      - "regex:type|title|status|detail|instance|field"
      - "length_min:80"
    expectations:
      - "flags inconsistent error formats as a DX problem"
      - "recommends a consistent error schema (RFC 7807 Problem Details or equivalent)"
      - "suggests centralized error handling middleware"
    tags: [errors, consistency, dx]

  - id: pagination-design
    prompt: |
      Design a pagination strategy for GET /api/orders which could return
      millions of records. Currently it returns all records with no limit.
    should_trigger: true
    checks:
      - "regex:cursor|offset|limit|page|next.*token|total|link.*header|X-Total"
      - "regex:cursor.*based|offset.*based|performance|index|large.*dataset"
      - "length_min:80"
    expectations:
      - "recommends cursor-based pagination for large datasets (better performance)"
      - "explains cursor vs offset trade-offs"
      - "provides concrete response format with pagination metadata"
    tags: [pagination, performance, large-data]
---

# API Design Principles

Build **intuitive, consistent, developer-friendly** APIs that scale and stand the test of time.

## Core Principles

### 1. Resources, Not Actions

Use **nouns** for endpoints. HTTP verbs express the action.

```
✗ POST /createUser       → ✓ POST /users
✗ GET /getUserById?id=1  → ✓ GET /users/1
✗ DELETE /deleteUser     → ✓ DELETE /users/1
```

Hierarchy for nested resources:
```
GET /users/1/orders       — orders for user 1
GET /users/1/orders/42    — specific order
```

### 2. HTTP Method Semantics

| Method | Semantics | Idempotent | Body |
|--------|-----------|------------|------|
| GET | Read | ✓ | No |
| POST | Create | ✗ | Yes |
| PUT | Replace | ✓ | Yes |
| PATCH | Partial update | ✗ | Yes |
| DELETE | Remove | ✓ | No |

### 3. Consistent HTTP Status Codes

| Code | When to use |
|------|-------------|
| 200 | OK (read, update) |
| 201 | Created (POST) |
| 204 | No content (DELETE) |
| 400 | Bad request (validation) |
| 401 | Unauthenticated |
| 403 | Forbidden (authorized but no permission) |
| 404 | Not found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable entity (semantic validation) |
| 429 | Rate limited |
| 500 | Server error |

### 4. Error Response Format (RFC 7807)

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation Error",
  "status": 400,
  "detail": "Email address is not valid",
  "instance": "/users/register",
  "errors": [
    {"field": "email", "code": "invalid_format", "message": "Must be a valid email"}
  ]
}
```

Use the **same schema everywhere**. Inconsistent errors are a DX anti-pattern.

### 5. Pagination

**Cursor-based** (preferred for large datasets):
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true
  }
}
```

**Offset-based** (acceptable for small/bounded collections):
```json
{
  "data": [...],
  "pagination": {"page": 1, "per_page": 20, "total": 4321}
}
```

Never return unbounded collections. Always paginate.

### 6. Versioning Strategy

- URL versioning: `/v1/users` — explicit, easy to cache
- Header versioning: `Accept: application/vnd.api.v1+json` — cleaner URLs
- Choose one and be consistent

### 7. Filtering & Sorting

```
GET /orders?status=pending&sort=-created_at&limit=20
GET /users?created_after=2024-01-01&role=admin
```

Use query params for filtering/sorting. Avoid filter DSLs in URLs.

### 8. API Design Checklist

- [ ] All endpoints use noun-based resource paths
- [ ] HTTP methods match semantics (no GET with side effects)
- [ ] Consistent error format across all endpoints
- [ ] Pagination on all list endpoints
- [ ] Rate limiting headers (`X-RateLimit-Remaining`)
- [ ] Versioning strategy documented
- [ ] Auth required on all non-public endpoints
- [ ] `created_at`/`updated_at` on all resources
