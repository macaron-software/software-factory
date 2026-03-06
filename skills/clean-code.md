---
name: clean-code
version: "1.1.0"
description: >
  Enforces production-quality code: no slop, no fake data, no type suppressions,
  no test cheating, no dead code, no magic values. Use this skill whenever an
  agent writes source code, test files, CSS, or configuration.
metadata:
  category: dev
  scope: "All languages — Python, TypeScript/JavaScript, CSS/SCSS, HTML, shell"
  enforced_by: "adversarial.py L0 (automated) + this skill (agent guidance)"
  triggers:
    - "when writing any source code file"
    - "when writing tests"
    - "when writing CSS or SCSS"
    - "when reviewing a pull request"
    - "always — these rules apply to every code generation task"
# EVAL CASES — philschmid.de/testing-skills
# WHY: Clean code skill must prevent stubs/placeholders/fake data from shipping.
# These cases test the adversarial detection capability (superficial compliance).
eval_cases:
  - id: no-stub-allowed
    prompt: "Implement a function to parse a JWT token and return the user_id."
    should_trigger: true
    checks:
      - "no_placeholder"
      - "regex:decode|jwt|base64|header|payload"
      - "not_regex:TODO|FIXME|return None  # TODO|raise NotImplementedError"
      - "not_regex:\\.{3}\\s*#"
      - "not_regex:pass\\s*#\\s*implement|pass\\s*#\\s*todo"
    expectations:
      - "generates real working implementation — not a stub or placeholder"
      - "does not return hardcoded fake data"
      - "imports a real JWT library or implements actual base64 decode logic"
      - "no ellipsis+comment stubs (... # implement) anywhere in the output"
    tags: [basic, anti-stub]
  - id: no-mock-data
    prompt: "List the active users from the database."
    should_trigger: true
    checks:
      - "not_regex:fake_users|test_user|john@example|alice|bob"
      - "regex:db\\.|query|SELECT|session"
    expectations:
      - "queries the real database, not returning hardcoded fake user list"
      - "uses the actual DB connection or ORM"
    tags: [anti-fake-data]
  - id: edge-case-handled
    prompt: "Write a function to get the first element of a list."
    should_trigger: true
    checks:
      - "regex:if.*len|if.*not.*list|IndexError|\\[\\]|empty"
    expectations:
      - "handles the empty list edge case — does not silently return None without explanation"
    tags: [edge-case]
---

# Clean Code — No Slop, No Cheating, No Fake Data

These rules apply to every file an agent creates or modifies.
They are enforced post-generation by `adversarial.py L0` — but the goal
is to never need the guard: generate clean code on the first attempt.

---

## RULE 1 — Never Cheat Tests

The adversarial guard runs on every agent output. Violations in this section
are hard-rejected (score +5 each, threshold 5 = immediate retry).

### NEVER
- `pytest.mark.skip` / `pytest.mark.skipif` — skip flags are not fixes
- `xit()`, `xtest()`, `xdescribe()`, `test.skip()`, `it.skip()` — same
- `assert True` — trivially passes, tests nothing
- `assert 1` — same
- `expect(x).toBeTruthy()` as the only assertion — tests nothing concrete
- `def test_something(): pass` or `def test_something(): ...` — empty test
- `except Exception: pass` inside a test function — silences assertion failures
- `--cov-fail-under=0` or `fail_under = 0` — defeats coverage
- Modifying the SYSTEM UNDER TEST to return a hardcoded value that matches the test expectation
- Adding `if os.getenv("TEST_MODE"): return expected_value` to production code

## RULE 1b — No Stub Bodies

**NEVER** use stub bodies in implementation code:

| FORBIDDEN | WHY |
|-----------|-----|
| `pass  # implement` | Empty function — not real code |
| `pass  # TODO` | Deferred work disguised as delivery |
| `...  # implement later` | Python Ellipsis stub |
| `...  # TODO` | Same |
| `raise NotImplementedError` | Skeleton, not implementation |
| `return None  # TODO` | Incomplete logic |

**Write the actual implementation.** If you cannot complete it, say so explicitly — never silently ship a stub.

### ALWAYS
- Fix the underlying code when a test fails — do not fix the test to match broken behavior
- Write assertions against REAL values: `assert result == 42`, not `assert result`
- Tests that fail are information — read the error, fix the bug
- When a test is genuinely not applicable yet: leave a comment explaining why AND create a tracking issue, do not use skip decorators silently

---

## RULE 2 — No Fake/Placeholder Data

### NEVER in production code or test setup
- `lorem ipsum` — use real domain-appropriate content
- `user123`, `foo@bar.com`, `test@test.com`, `John Doe` — use realistic seed data
- `http://example.com` — use the actual URL or a proper env var
- Hardcoded API keys, tokens, passwords — use environment variables
- `"TODO: replace this"` as a value — either put the real value or block the task
- `id = Math.random()` for persistent entity IDs — use proper UUID/ULID
- `setTimeout(() => resolve(), 100)` as a fake async operation

### In tests — use realistic data
```python
# WRONG
user = User(name="test", email="test@test.com")

# RIGHT  
user = User(name="Marie Dupont", email="marie.dupont@exemple.fr")
```

```typescript
// WRONG
const product = { id: "abc", price: 0, name: "test product" }

// RIGHT
const product = { id: "prod_01J8Z...", price: 2999, name: "Clavier mécanique TKL" }
```

---

## RULE 3 — No Type/Lint Suppression

The adversarial guard catches these (score +2 each). Fix the type error, not the check.

### TypeScript
| NEVER | INSTEAD |
|-------|---------|
| `// @ts-ignore` | Fix the type error or add proper type narrowing |
| `// @ts-nocheck` | Fix all errors in the file |
| `: any` | Use `unknown`, the specific type, or a union |
| `as unknown as X` | Fix the type declaration, not the cast |
| `// eslint-disable-next-line` | Fix the lint violation |
| `/* eslint-disable */` blocks | Fix all violations in the block |

```typescript
// WRONG
const data: any = fetchResponse
const value = (data as unknown as SomeType).field

// RIGHT
const data: ApiResponse = fetchResponse
const value = data.field
```

### Python
| NEVER | INSTEAD |
|-------|---------|
| `# type: ignore` | Fix the type annotation |
| `except Exception: pass` | Handle the specific exception or re-raise |
| `except BaseException: pass` | Never |

```python
# WRONG
except Exception:
    pass  # silently swallows all errors including KeyboardInterrupt

# RIGHT
except ValueError as e:
    logger.warning("Invalid input: %s", e)
    return default_value
```

---

## RULE 4 — Clean CSS / No Lazy Overrides

### NEVER
| Pattern | Why | Instead |
|---------|-----|---------|
| `!important` | Specificity debt — cascade will break later | Fix the selector |
| `style="color:red"` inline in HTML/JSX | Untestable, not themeable | Use a CSS class |
| `-webkit-border-radius`, `-webkit-box-shadow`, `-webkit-transition`, `-webkit-transform` | Not needed since 2017 (caniuse >98%) | Remove the prefix |
| `-moz-border-radius`, `-moz-box-shadow` | Not needed since 2020 | Remove the prefix |
| Hardcoded hex colors: `color: #3b82f6` | Can't be themed, breaks dark mode | Use `var(--color-primary)` |
| Hardcoded pixel values for spacing: `margin: 24px` everywhere | Inconsistent scale | Use `var(--space-6)` or design token |
| `z-index: 9999` | Uncontrolled stacking context | Use a z-index scale variable |

```css
/* WRONG */
.button {
  background: #3b82f6 !important;
  -webkit-border-radius: 4px;
  -moz-border-radius: 4px;
  border-radius: 4px;
}

/* RIGHT */
.button {
  background: var(--color-primary);
  border-radius: var(--radius-sm);
}
```

### ALWAYS
- Use CSS custom properties (variables) for all colors, spacing, and radii
- Target browser support: evergreen (Chrome 120+, Firefox 120+, Safari 17+) — most vendor prefixes are dead weight
- Exception: `-webkit-line-clamp` for multi-line truncation (still needs prefix as of 2026)

---

## RULE 5 — No Dead Code

### NEVER commit
- Commented-out code blocks: `// const oldVersion = ...`
- Unused imports: `import os` when `os` is never used
- Unreachable branches: `if False:` or `if 0:`
- Functions defined but never called (if clearly left over, not a public API)
- Console/debug logging: `console.log("debug:", data)` in production code
- `print("test")` / `print("here")` debug statements

### In Python
```python
# WRONG
import os  # unused
import sys  # unused

# Also WRONG — left in from debugging
print("DEBUG: got here", user)

# RIGHT — remove debug statements before committing
```

---

## RULE 6 — No Magic Values

### NEVER
```python
# WRONG
if response.status_code == 429:  # magic number
    time.sleep(90)  # magic number

# RIGHT
HTTP_TOO_MANY_REQUESTS = 429
COOLDOWN_SECONDS = 90
if response.status_code == HTTP_TOO_MANY_REQUESTS:
    time.sleep(COOLDOWN_SECONDS)
```

```typescript
// WRONG
if (items.length > 7) showPagination()  // why 7?

// RIGHT
const MAX_ITEMS_WITHOUT_PAGINATION = 7  // Miller's Law — 7±2
if (items.length > MAX_ITEMS_WITHOUT_PAGINATION) showPagination()
```

---

## RULE 7 — No Fallback Slop in CSS/HTML

### NEVER write CSS fallbacks "just in case" for features with >95% browser support
```css
/* WRONG — display: flex has 99.5% support, no fallback needed */
display: block;       /* fallback */
display: -webkit-box; /* old iOS */
display: flex;

/* RIGHT */
display: flex;
```

```css
/* WRONG — CSS Grid has 97% support */
float: left; width: 33%; /* fallback */
display: grid;

/* RIGHT */
display: grid;
grid-template-columns: repeat(3, 1fr);
```

**Check caniuse.com before adding any fallback.** If support >95%: remove the fallback.

---

## L1 Prompt — How the adversarial LLM checks this

When L1 semantic review runs on code output, it evaluates:

```
CODE QUALITY RULES (non-negotiable):
1. No @ts-ignore, @ts-nocheck, # type: ignore — these suppress errors instead of fixing them
2. No test.skip, pytest.mark.skip, xit(), assert True — these cheat tests
3. No empty test bodies (pass, ...) — tests must assert real behavior
4. No except Exception: pass — silent error swallowing hides bugs
5. No !important in CSS — fix the cascade instead
6. No hardcoded fake data (lorem ipsum, test@test.com, user123)
7. No magic numbers — use named constants
8. No dead commented-out code — remove it
9. No unnecessary vendor prefixes — check caniuse first
If ANY of the above are present in the written code, flag as CODE_SLOP.
```
