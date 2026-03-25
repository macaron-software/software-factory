---
description: Test files — zero skip, real assertions
globs: tests/**/*.py, platform/tests/**/*.py, platform/tests/e2e/**/*.ts
---

- ZERO SKIP: never `test.skip`, `describe.skip`, `@pytest.mark.skip`, `#[ignore]`. Fix > skip.
- No mock data or fake DB. Tests run against live PG (`DATABASE_URL`).
- Every test must assert something meaningful. No empty tests, no `assert True`.
- E2E tests: Playwright with `--max-failures=1`. Stop at first failure.
- Python tests: `pytest -v`. No `unittest` unless legacy.
- Adversarial test quality check: `no_placeholder`, `length_min:50`, `has_keyword:assert`.
