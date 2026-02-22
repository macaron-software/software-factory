---
name: architecture-review
description: >
  Guides the agent through reviewing software architecture for clean design, SOLID
  principles, domain-driven design patterns, and scalability. Use this skill when
  assessing system structure, evaluating architectural decisions, or creating
  Architecture Decision Records (ADRs).
metadata:
  category: development
  triggers:
    - "when user asks to review architecture"
    - "when assessing code structure and organization"
    - "when user mentions SOLID, DDD, or clean architecture"
    - "when evaluating scalability of a system"
    - "when creating Architecture Decision Records"
---

# Architecture Review

This skill enables the agent to review software architecture for clean design principles,
evaluate trade-offs, and document decisions using Architecture Decision Records.

## Use this skill when

- Reviewing overall system architecture
- Evaluating module/package structure
- Checking SOLID principle adherence
- Assessing scalability and performance architecture
- Creating or reviewing ADRs
- Evaluating design patterns usage

## Do not use this skill when

- Reviewing individual code quality (use code-review-excellence)
- Doing security-specific review (use security-audit)
- Implementing features (use development skills)

## Instructions

### Clean Architecture Assessment

Evaluate layer separation:

```
┌─────────────────────────────────────────┐
│           Presentation Layer            │  Controllers, Views, CLI
│    (depends on Application layer)       │
├─────────────────────────────────────────┤
│           Application Layer             │  Use Cases, DTOs, Services
│    (depends on Domain layer)            │
├─────────────────────────────────────────┤
│             Domain Layer                │  Entities, Value Objects, Interfaces
│    (depends on NOTHING external)        │
├─────────────────────────────────────────┤
│         Infrastructure Layer            │  DB, APIs, File System, Queue
│    (implements Domain interfaces)       │
└─────────────────────────────────────────┘
```

**Dependency Rule**: Dependencies point INWARD only. Domain never imports from Infrastructure.

```typescript
// ❌ WRONG: Domain depends on infrastructure
// domain/user.ts
import { PrismaClient } from '@prisma/client'; // Infrastructure leak!

// ✅ CORRECT: Domain defines interface, infrastructure implements
// domain/user-repository.ts
export interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
}

// infrastructure/prisma-user-repository.ts
import { PrismaClient } from '@prisma/client';
import { UserRepository } from '../domain/user-repository';

export class PrismaUserRepository implements UserRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<User | null> {
    return this.prisma.user.findUnique({ where: { id } });
  }

  async save(user: User): Promise<void> {
    await this.prisma.user.upsert({ where: { id: user.id }, create: user, update: user });
  }
}
```

### SOLID Principles Checklist

#### S — Single Responsibility

```typescript
// ❌ VIOLATION: Class does too many things
class UserService {
  createUser() { }
  sendWelcomeEmail() { }
  generateReport() { }
  validateCreditCard() { }
}

// ✅ CORRECT: Each class has one reason to change
class UserService { createUser() { } }
class EmailService { sendWelcomeEmail() { } }
class ReportService { generateReport() { } }
class PaymentService { validateCreditCard() { } }
```

#### O — Open/Closed

```typescript
// ✅ Open for extension, closed for modification
interface PaymentProcessor {
  process(amount: number): Promise<PaymentResult>;
}

class StripeProcessor implements PaymentProcessor { }
class PayPalProcessor implements PaymentProcessor { }
// Adding new processor doesn't modify existing code
```

#### L — Liskov Substitution

```typescript
// ❌ VIOLATION: Square breaks Rectangle contract
class Rectangle { setWidth(w) { } setHeight(h) { } }
class Square extends Rectangle {
  setWidth(w) { this.width = w; this.height = w; } // Breaks expectations
}
```

#### I — Interface Segregation

```typescript
// ❌ VIOLATION: Fat interface
interface Worker {
  work(): void;
  eat(): void;
  sleep(): void;
}

// ✅ CORRECT: Segregated interfaces
interface Workable { work(): void; }
interface Feedable { eat(): void; }
```

#### D — Dependency Inversion

```typescript
// ❌ VIOLATION: High-level depends on low-level
class OrderService {
  private db = new MySQLDatabase(); // Direct dependency
}

// ✅ CORRECT: Both depend on abstractions
class OrderService {
  constructor(private repository: OrderRepository) {} // Interface
}
```

### Domain-Driven Design Patterns

#### Bounded Contexts

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Ordering   │  │   Shipping   │  │   Billing    │
│              │  │              │  │              │
│  Order       │  │  Shipment    │  │  Invoice     │
│  LineItem    │  │  Tracking    │  │  Payment     │
│  Customer*   │  │  Address     │  │  Customer*   │
└──────────────┘  └──────────────┘  └──────────────┘

* Customer may have different representations in each context
```

#### Aggregate Roots

```typescript
// Order is the aggregate root — all access goes through it
class Order {
  private items: OrderItem[] = [];

  addItem(product: Product, quantity: number): void {
    // Enforce business rules at the aggregate boundary
    if (this.status !== 'draft') throw new Error('Cannot modify submitted order');
    const existing = this.items.find(i => i.productId === product.id);
    if (existing) {
      existing.increaseQuantity(quantity);
    } else {
      this.items.push(new OrderItem(product, quantity));
    }
  }

  get total(): Money {
    return this.items.reduce((sum, item) => sum.add(item.subtotal), Money.zero());
  }
}
```

### Architecture Decision Record (ADR) Template

```markdown
# ADR-001: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
[What is the issue that we're seeing that is motivating this decision?]

## Decision
[What is the change that we're proposing and/or doing?]

## Consequences
### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Trade-off 1]
- [Trade-off 2]

### Risks
- [Risk 1 and mitigation strategy]

## Alternatives Considered
### Alternative A: [Name]
- Pros: [...]
- Cons: [...]
- Rejected because: [...]
```

### Scalability Assessment

| Dimension | Question | Pattern |
|-----------|----------|---------|
| Read scale | Can reads be cached? | Cache-aside, CDN, read replicas |
| Write scale | Can writes be queued? | Message queue, event sourcing |
| Compute | Can processing be parallelized? | Worker pools, serverless |
| Storage | Does data grow unboundedly? | Archival, partitioning, TTL |
| Network | Are there chatty services? | Batch APIs, BFF pattern |

### Code Organization Review

```
✅ GOOD structure:
src/
├── domain/          # Business logic (pure, no dependencies)
│   ├── entities/
│   ├── value-objects/
│   └── repositories/  (interfaces only)
├── application/     # Use cases, orchestration
│   ├── commands/
│   ├── queries/
│   └── services/
├── infrastructure/  # External implementations
│   ├── database/
│   ├── http/
│   └── messaging/
└── presentation/    # API controllers, CLI, UI
    ├── rest/
    ├── graphql/
    └── cli/

❌ BAD structure:
src/
├── models/          # Mixed concerns
├── utils/           # Dumping ground
├── helpers/         # More dumping ground
└── index.ts         # God file
```

## Output Format

```
## Architecture Review: [System/Module Name]

### Layer Analysis
| Layer | Status | Issues |
|-------|--------|--------|
| Domain | ✅ Clean | No external dependencies |
| Application | ⚠️ | Leaks infrastructure details |
| Infrastructure | ✅ | Properly implements interfaces |
| Presentation | ❌ | Contains business logic |

### SOLID Compliance
| Principle | Status | Notes |
|-----------|--------|-------|
| S - Single Responsibility | ✅ | Services are focused |
| O - Open/Closed | ⚠️ | Switch statements in PaymentService |
| L - Liskov Substitution | ✅ | No violations found |
| I - Interface Segregation | ❌ | UserService interface too fat |
| D - Dependency Inversion | ✅ | DI container properly used |

### Findings
1. **[Critical]** Business logic in controller layer — move to application service
2. **[Important]** No clear bounded context boundaries — services are tightly coupled
3. **[Suggestion]** Consider CQRS for the reporting module

### ADR Recommendations
- ADR-XXX: Adopt CQRS for reporting queries
- ADR-XXX: Define bounded context boundaries
```

## Anti-patterns

- **NEVER** put business logic in controllers or API handlers
- **NEVER** let domain entities depend on infrastructure
- **NEVER** create "God classes" that do everything
- **NEVER** use the `utils/` or `helpers/` folder as a dumping ground
- **NEVER** skip ADRs for significant architectural decisions
- **NEVER** couple services directly — use interfaces/events
- **NEVER** ignore scalability until it's too late — plan for it
- **NEVER** over-engineer — YAGNI applies to architecture too
