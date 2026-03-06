---
name: code-review-excellence
description: >
  Guides the agent through systematic, high-quality code reviews. Use this skill when
  reviewing pull requests or code changes for correctness, security, performance, and
  maintainability. Covers severity classification, constructive feedback patterns,
  test coverage verification, and common vulnerability detection.
metadata:
  category: development
  triggers:
    - "when user asks to review code or a PR"
    - "when user asks for feedback on code quality"
    - "when reviewing a pull request"
    - "when user wants to check code for bugs or security issues"
    - "when assessing code maintainability"
version: "1.1.0"
# EVAL CASES — philschmid.de/testing-skills
# WHY: Verifies the review skill surfaces real issues (not just style), avoids
# false positives on clean code, and never rubber-stamps broken code.
eval_cases:
  - id: review-with-bug
    prompt: "Review this code:\ndef get_user(id):\n    return db.query(f'SELECT * FROM users WHERE id={id}')\n"
    should_trigger: true
    checks:
      - "regex:SQL inject|f-string|parameteriz|prepared statement"
      - "no_placeholder"
      - "length_min:100"
    expectations:
      - "identifies the SQL injection vulnerability"
      - "suggests using parameterized queries or an ORM"
      - "explains the security risk, not just the fix"
    tags: [security, basic]
  - id: review-clean-code
    prompt: "Review this code:\ndef add(a: int, b: int) -> int:\n    return a + b\n"
    should_trigger: true
    checks:
      - "length_min:30"
      - "not_regex:SQL inject|injection|vulnerability|security risk|dangerous|critical|bug found|broken"
      - "regex:correct|clean|simple|LGTM|looks good|no.{0,20}issue|no.{0,20}bug|straightforward|fine|OK|minimal|well.written|good"
    expectations:
      - "does not flag false positives on clean, correct code"
      - "brief response — no major issues invented"
      - "acknowledges the code is correct/clean (LGTM or equivalent)"
    tags: [clean, negative-issues]
  - id: review-performance
    prompt: "Review:\ndef find_user(name, users):\n    for u in users:\n        if u.name == name: return u\n    return None\n# called 10000x per request"
    should_trigger: true
    checks:
      - "regex:O\\(n\\)|linear|index|dict|hash|performance|slow"
      - "no_placeholder"
    expectations:
      - "identifies the O(n) linear scan as a performance issue"
      - "suggests a dict/hashmap or indexed lookup"
    tags: [performance]
---

# Code Review Excellence

This skill enables the agent to perform thorough, constructive code reviews that catch
real issues while maintaining a positive, collaborative tone.

## Use this skill when

- Reviewing pull requests or merge requests
- Evaluating code quality of a file or module
- Checking for security vulnerabilities in code
- Assessing test coverage of changes
- Reviewing architecture decisions in code

## Do not use this skill when

- Writing code from scratch (use TDD or implementation skills)
- Doing security-only audits (use security-audit)
- Reviewing infrastructure/deployment (use devops-pipeline)

## Instructions

### Review Priorities (in order)

1. **Correctness** — Does it work? Edge cases? Race conditions?
2. **Security** — Injection, auth bypass, data exposure, secrets?
3. **Performance** — N+1 queries, unnecessary re-renders, memory leaks?
4. **Maintainability** — Readable? Well-named? Single responsibility?
5. **Testing** — Are changes tested? Coverage sufficient?

### Severity Classification

| Level | Label          | Meaning                                       | Action Required              |
| ----- | -------------- | --------------------------------------------- | ---------------------------- |
| 🔴    | **Blocking**   | Bug, security issue, data loss risk           | Must fix before merge        |
| 🟠    | **Important**  | Performance issue, missing test, poor pattern | Should fix before merge      |
| 🟡    | **Suggestion** | Better approach exists, minor improvement     | Consider for this or next PR |
| 🔵    | **Nit**        | Style, naming, minor readability              | Optional, low priority       |
| 💬    | **Question**   | Clarification needed                          | Answer before merge          |

### Review Checklist

#### Correctness

```
- [ ] Logic handles all expected inputs correctly
- [ ] Edge cases covered (null, empty, boundary values)
- [ ] Error paths handled gracefully
- [ ] Async operations have proper error handling
- [ ] State changes are atomic/consistent
- [ ] No off-by-one errors in loops/slices
```

#### Security

```
- [ ] No hardcoded secrets, API keys, or passwords
- [ ] User input is validated and sanitized
- [ ] SQL queries use parameterized statements
- [ ] HTML output is escaped (XSS prevention)
- [ ] Authentication checked on protected routes
- [ ] Authorization verified (not just authentication)
- [ ] Sensitive data not logged or exposed in errors
```

#### Performance

```
- [ ] No N+1 query patterns
- [ ] Large lists are paginated
- [ ] Expensive computations are cached when appropriate
- [ ] No unnecessary re-renders (React: memo, useMemo, useCallback)
- [ ] Database queries use appropriate indexes
- [ ] File/network operations are properly streamed for large data
```

#### Testing

```
- [ ] New code has corresponding tests
- [ ] Edge cases are tested
- [ ] Error paths are tested
- [ ] Mocks are appropriate (not over-mocking)
- [ ] Test names describe behavior, not implementation
- [ ] No flaky test patterns (timeouts, shared state)
```

### Feedback Patterns

#### Constructive Comment Template

```
🔴 **Blocking: SQL Injection Risk**

The query concatenates user input directly:
` `
const query = `SELECT * FROM users WHERE name = '${name}'`;
` `

This is vulnerable to SQL injection. Use parameterized queries:
` `
const query = 'SELECT * FROM users WHERE name = $1';
const result = await db.query(query, [name]);
` `
```

#### Asking Questions (Not Demanding)

```
💬 **Question**: I see this fetches all users then filters in memory.
Was there a reason not to filter in the database query?
If not, moving the filter to SQL would reduce memory usage significantly
for large user sets.
```

#### Positive Feedback

```
✅ **Nice**: Clean use of the Strategy pattern here — makes it easy
to add new payment providers without modifying existing code.
```

### Common Issues to Watch For

#### JavaScript/TypeScript

```typescript
// 🔴 Missing await
async function saveUser(user: User) {
  db.save(user); // Missing await — error won't be caught
}

// 🟠 Type assertion hiding bugs
const user = data as User; // Use type guard instead
function isUser(data: unknown): data is User {
  return typeof data === 'object' && data !== null && 'email' in data;
}

// 🟡 Unnecessary re-render
function UserList({ users }: Props) {
  const sorted = users.sort(); // Mutates prop! Use [...users].sort()
  return <div>{sorted.map(u => <User key={u.id} user={u} />)}</div>;
}
```

#### Python

```python
# 🔴 Mutable default argument
def add_item(item, items=[]):  # BAD: shared mutable default
    items.append(item)
    return items

# ✅ Fix
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items

# 🟠 Broad exception catching
try:
    process_data()
except Exception:  # Too broad — catches KeyboardInterrupt, SystemExit
    pass

# ✅ Fix
try:
    process_data()
except (ValueError, KeyError) as e:
    logger.error(f"Data processing failed: {e}")
```

#### SQL

```sql
-- 🔴 No LIMIT on potentially large result set
SELECT * FROM logs WHERE created_at > '2024-01-01';

-- ✅ Fix
SELECT * FROM logs WHERE created_at > '2024-01-01' LIMIT 1000;

-- 🟠 SELECT * in production code
SELECT * FROM users WHERE id = $1;

-- ✅ Fix: Select only needed columns
SELECT id, name, email FROM users WHERE id = $1;
```

### PR Review Workflow

1. **Read the PR description** — understand intent before reading code
2. **Check the tests first** — tests tell you what the code should do
3. **Review file by file** — focus on changed lines + surrounding context
4. **Check for missing changes** — are there files that SHOULD have changed but didn't?
5. **Run the code mentally** — trace through the logic with sample inputs
6. **Write constructive feedback** — suggest solutions, not just problems

## Output Format

```
## Code Review: [PR Title / File Name]

### Summary
[1-2 sentence overview of the changes and overall quality]

### Findings
| # | Severity | Category | File:Line | Description |
|---|----------|----------|-----------|-------------|
| 1 | 🔴 Blocking | Security | auth.ts:42 | SQL injection in login query |
| 2 | 🟠 Important | Testing | - | No tests for error handling |
| 3 | 🟡 Suggestion | Performance | api.ts:15 | Consider caching this query |

### Details
[Detailed comments for each finding with code examples]

### Verdict: [Approve / Request Changes / Needs Discussion]
```

## Anti-patterns

- **NEVER** just say "this is wrong" without explaining why and suggesting a fix
- **NEVER** bikeshed on style when there are real bugs to find
- **NEVER** approve without actually reading the code
- **NEVER** block on personal preferences — only block on real issues
- **NEVER** review more than 400 lines in one session without a break
- **NEVER** forget to check that tests exist for new/changed code
- **NEVER** ignore the PR description — context matters
- **NEVER** leave ambiguous comments — be specific about file, line, and fix
