---
name: e2e-api-testing
description: >
  Guides the agent through end-to-end API testing using direct HTTP calls (fetch/curl).
  Use this skill when testing REST API endpoints for correctness, auth, validation,
  error handling, and edge cases. Covers all standard HTTP methods, status codes,
  and common API testing patterns.
metadata:
  category: testing
  triggers:
    - "when user asks to test an API endpoint"
    - "when user wants to verify API responses"
    - "when testing authentication or authorization guards"
    - "when validating request/response schemas"
    - "when user asks to test error handling on APIs"
---

# E2E API Testing

This skill enables the agent to write comprehensive API endpoint tests using direct HTTP
calls. Tests verify status codes, response bodies, headers, auth guards, validation,
pagination, and error formats.

## Use this skill when

- Testing REST API endpoints (CRUD operations)
- Verifying authentication and authorization guards
- Validating request/response schemas
- Testing error handling and edge cases
- Checking pagination, filtering, sorting
- Rate limiting verification

## Do not use this skill when

- Testing browser UI interactions (use e2e-browser-testing)
- Testing internal function logic (use tdd-mastery)
- Testing GraphQL (adapt patterns but different tooling)

## Instructions

### Test Structure

Each API test follows this pattern:

```typescript
import { describe, it, expect, beforeAll, afterAll } from "vitest";

const BASE_URL = process.env.API_URL || "http://localhost:3000/api";

describe("POST /api/users", () => {
  let authToken: string;

  beforeAll(async () => {
    // Setup: get auth token
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@test.com", password: "test123" }),
    });
    const data = await res.json();
    authToken = data.token;
  });

  it("should create a user and return 201", async () => {
    const res = await fetch(`${BASE_URL}/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        email: "new@test.com",
        name: "Test User",
        role: "member",
      }),
    });

    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body).toMatchObject({
      id: expect.any(String),
      email: "new@test.com",
      name: "Test User",
      role: "member",
      createdAt: expect.any(String),
    });
  });

  it("should return 400 for missing required fields", async () => {
    const res = await fetch(`${BASE_URL}/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ name: "No Email" }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBeDefined();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("should return 401 without auth token", async () => {
    const res = await fetch(`${BASE_URL}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "test@test.com", name: "Test" }),
    });

    expect(res.status).toBe(401);
  });

  it("should return 409 for duplicate email", async () => {
    const res = await fetch(`${BASE_URL}/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ email: "admin@test.com", name: "Duplicate" }),
    });

    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.error.code).toBe("DUPLICATE_ENTRY");
  });
});
```

### Status Code Reference

Always test these status codes for each endpoint:

| Code | Meaning           | When to test                              |
| ---- | ----------------- | ----------------------------------------- |
| 200  | OK                | Successful GET, PUT, PATCH                |
| 201  | Created           | Successful POST that creates a resource   |
| 204  | No Content        | Successful DELETE                         |
| 400  | Bad Request       | Invalid body, missing fields, wrong types |
| 401  | Unauthorized      | Missing or invalid auth token             |
| 403  | Forbidden         | Valid token but insufficient permissions  |
| 404  | Not Found         | Resource doesn't exist                    |
| 409  | Conflict          | Duplicate entry, version conflict         |
| 422  | Unprocessable     | Valid JSON but business rule violation    |
| 429  | Too Many Requests | Rate limit exceeded                       |
| 500  | Server Error      | Should never happen — test for absence    |

### Auth Guard Testing Pattern

```typescript
describe("Authorization guards", () => {
  it("rejects unauthenticated requests", async () => {
    const res = await fetch(`${BASE_URL}/admin/users`);
    expect(res.status).toBe(401);
  });

  it("rejects non-admin users", async () => {
    const res = await fetch(`${BASE_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${memberToken}` },
    });
    expect(res.status).toBe(403);
  });

  it("accepts admin users", async () => {
    const res = await fetch(`${BASE_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status).toBe(200);
  });

  it("rejects expired tokens", async () => {
    const res = await fetch(`${BASE_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${expiredToken}` },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("TOKEN_EXPIRED");
  });
});
```

### Pagination Testing

```typescript
describe("GET /api/items (pagination)", () => {
  it("returns paginated results with metadata", async () => {
    const res = await fetch(`${BASE_URL}/items?page=1&limit=10`);
    const body = await res.json();

    expect(body.data).toHaveLength(10);
    expect(body.meta).toMatchObject({
      page: 1,
      limit: 10,
      total: expect.any(Number),
      totalPages: expect.any(Number),
    });
  });

  it("returns empty array for page beyond results", async () => {
    const res = await fetch(`${BASE_URL}/items?page=9999&limit=10`);
    const body = await res.json();

    expect(body.data).toHaveLength(0);
    expect(res.status).toBe(200);
  });

  it("defaults to page 1 and limit 20", async () => {
    const res = await fetch(`${BASE_URL}/items`);
    const body = await res.json();

    expect(body.meta.page).toBe(1);
    expect(body.meta.limit).toBe(20);
  });
});
```

### Error Response Format

All API errors should follow a consistent format. Validate it:

```typescript
interface ApiError {
  error: {
    code: string; // Machine-readable: 'VALIDATION_ERROR', 'NOT_FOUND'
    message: string; // Human-readable description
    details?: Array<{
      // Field-level errors for validation
      field: string;
      message: string;
    }>;
  };
}
```

## Output Format

For each endpoint tested, produce:

```
## Endpoint: [METHOD] /api/path
✅ Happy path — [status code] [description]
✅ Validation — [status code] [missing/invalid field]
✅ Auth — 401 without token
✅ Auth — 403 insufficient role
✅ Edge case — [description]
❌ FAILED — [description of failure]
```

## Anti-patterns

- **NEVER** hardcode auth tokens in test files — use setup/fixtures
- **NEVER** depend on test execution order — each test must be independent
- **NEVER** skip testing error responses — they're as important as success
- **NEVER** ignore response headers (Content-Type, Cache-Control, CORS)
- **NEVER** test only the happy path — test at minimum: success, validation, auth, not-found
- **NEVER** use `any` type assertions for response bodies — validate the actual shape
- **NEVER** forget cleanup — delete created resources in afterAll/afterEach
- **NEVER** test against production data — use dedicated test databases/fixtures
