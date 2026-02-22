---
name: technical-writing
description: >
  Guides the agent through producing clear, structured technical documentation including
  API docs, README files, Architecture Decision Records, changelogs, user guides, and
  inline code documentation. Use this skill when writing or reviewing any form of
  technical documentation.
metadata:
  category: documentation
  triggers:
    - "when user asks to write documentation"
    - "when creating or updating a README"
    - "when documenting an API"
    - "when writing an ADR"
    - "when maintaining a changelog"
    - "when writing inline code documentation"
---

# Technical Writing

This skill enables the agent to produce clear, structured, and useful technical
documentation across all common formats — API docs, READMEs, ADRs, changelogs,
and inline code documentation.

## Use this skill when

- Writing or updating README files
- Documenting REST APIs (OpenAPI/Swagger)
- Creating Architecture Decision Records
- Maintaining changelogs (Keep a Changelog format)
- Writing user guides or tutorials
- Reviewing documentation for clarity and completeness
- Writing inline code documentation (JSDoc, docstrings)

## Do not use this skill when

- Writing code (use development skills)
- Doing project management (use project-management)
- Reviewing architecture (use architecture-review)

## Instructions

### README Template

```markdown
# Project Name

One-paragraph description of what this project does and why it exists.

## Features

- Feature 1 with brief description
- Feature 2 with brief description
- Feature 3 with brief description

## Quick Start

### Prerequisites

- Node.js 20+
- PostgreSQL 16+
- Redis 7+

### Installation

` ``bash
git clone https://github.com/org/project.git
cd project
npm install
cp .env.example .env  # Edit with your values
npm run dev
` ``

### Running Tests

` ``bash
npm test           # Unit tests
npm run test:e2e   # E2E tests
npm run test:ci    # Full CI suite
` ``

## Architecture

Brief overview of the architecture. Link to ADRs for detailed decisions.

` ``
src/
├── domain/        # Business logic
├── application/   # Use cases
├── infrastructure/# External integrations
└── presentation/  # API layer
` ``

## API Documentation

API docs are available at `/api/docs` when running the server.
See [API Reference](./docs/api.md) for details.

## Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` | No |
| `PORT` | Server port | `3000` | No |
| `LOG_LEVEL` | Logging level | `info` | No |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

[MIT](./LICENSE)
```

### API Documentation (OpenAPI)

```yaml
openapi: 3.0.3
info:
  title: Project API
  version: 1.0.0
  description: |
    Brief description of the API.

    ## Authentication
    All endpoints require a Bearer token in the Authorization header.

paths:
  /api/users:
    post:
      summary: Create a new user
      tags: [Users]
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [email, name]
              properties:
                email:
                  type: string
                  format: email
                  example: user@example.com
                name:
                  type: string
                  example: John Doe
      responses:
        '201':
          description: User created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
        '400':
          description: Validation error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '409':
          description: Email already exists

components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
          format: uuid
        email:
          type: string
        name:
          type: string
        createdAt:
          type: string
          format: date-time
    Error:
      type: object
      properties:
        error:
          type: object
          properties:
            code:
              type: string
            message:
              type: string
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

### Changelog (Keep a Changelog)

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- User registration with email verification (#123)

### Changed
- Updated dashboard layout for better mobile experience (#456)

### Fixed
- Fixed race condition in concurrent order processing (#789)

## [1.2.0] - 2024-01-15

### Added
- Dark mode support
- Export to CSV feature

### Deprecated
- Legacy API v1 endpoints (will be removed in v2.0.0)

### Security
- Updated dependencies to patch CVE-2024-XXXXX
```

### ADR Format

```markdown
# ADR-001: Use PostgreSQL as Primary Database

## Status
Accepted (2024-01-15)

## Context
We need a primary database for our application that handles:
- Complex relational queries
- ACID transactions
- Full-text search
- JSON document storage for flexible schemas

## Decision
We will use PostgreSQL 16 as our primary database.

## Consequences

### Positive
- Excellent support for complex queries and joins
- JSONB support for semi-structured data
- Strong community and ecosystem
- Free and open source

### Negative
- Horizontal scaling is more complex than NoSQL alternatives
- Requires more operational expertise than managed NoSQL services

### Risks
- If we need extreme write throughput, may need to add a message queue
  Mitigation: Design with eventual consistency where possible

## Alternatives Considered

### MongoDB
- Pros: Flexible schema, easy horizontal scaling
- Cons: Weaker consistency guarantees, less suitable for relational data
- Rejected: Our data model is primarily relational

### DynamoDB
- Pros: Fully managed, auto-scaling
- Cons: Vendor lock-in, limited query flexibility
- Rejected: Too restrictive for our query patterns
```

### Inline Code Documentation

#### TypeScript/JSDoc

```typescript
/**
 * Calculates the discount amount for an order based on the pricing tier.
 *
 * @param amount - The order total in cents (must be positive)
 * @param tier - The customer's pricing tier
 * @returns The discounted amount in cents
 * @throws {Error} If amount is negative
 *
 * @example
 * ```ts
 * calculateDiscount(15000, 'premium'); // Returns 12750 (15% off)
 * calculateDiscount(5000, 'standard'); // Returns 5000 (no discount under $100)
 * ```
 */
export function calculateDiscount(amount: number, tier: DiscountTier): number {
  if (amount < 0) throw new Error('Amount must be positive');
  // ...
}
```

#### Python Docstrings

```python
def calculate_discount(amount: int, tier: str) -> int:
    """Calculate the discount amount for an order.

    Applies the discount rate based on the customer's pricing tier.
    Orders under $100 receive no discount regardless of tier.

    Args:
        amount: The order total in cents. Must be positive.
        tier: The customer pricing tier ('standard', 'premium', 'enterprise').

    Returns:
        The discounted amount in cents.

    Raises:
        ValueError: If amount is negative.

    Examples:
        >>> calculate_discount(15000, 'premium')
        12750
        >>> calculate_discount(5000, 'standard')
        5000
    """
```

### Writing Guidelines

1. **Be concise** — Use the shortest sentence that conveys the meaning
2. **Use active voice** — "The function returns" not "A value is returned by"
3. **Use present tense** — "Sends the request" not "Will send the request"
4. **Use second person** — "You can configure..." not "One can configure..."
5. **Define acronyms** — First use: "Content Security Policy (CSP)", then "CSP"
6. **Include examples** — Every API endpoint, function, and config option
7. **Keep it current** — Outdated docs are worse than no docs

### Documentation Review Checklist

```
- [ ] All public APIs are documented
- [ ] Examples compile and run correctly
- [ ] Links are not broken
- [ ] Screenshots are current
- [ ] Version numbers are accurate
- [ ] Installation instructions work from scratch
- [ ] Environment variables are all listed
- [ ] Error cases are documented
```

## Output Format

Use the appropriate template for the document type requested.

## Anti-patterns

- **NEVER** write documentation that restates the code — explain WHY, not WHAT
- **NEVER** leave placeholder text ("TODO: write this")
- **NEVER** document internal implementation details in public API docs
- **NEVER** use jargon without defining it
- **NEVER** write a README without installation instructions
- **NEVER** skip the examples section — examples are the most-read part
- **NEVER** document behavior that doesn't match the code
- **NEVER** use screenshots without alt text
