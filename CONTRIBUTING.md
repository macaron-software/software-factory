<p align="center">
  <a href="CONTRIBUTING.md">English</a> |
  <a href="CONTRIBUTING.fr.md">Français</a> |
  <a href="CONTRIBUTING.zh-CN.md">中文</a> |
  <a href="CONTRIBUTING.es.md">Español</a> |
  <a href="CONTRIBUTING.ja.md">日本語</a> |
  <a href="CONTRIBUTING.pt.md">Português</a> |
  <a href="CONTRIBUTING.de.md">Deutsch</a> |
  <a href="CONTRIBUTING.ko.md">한국어</a>
</p>

# Contributing to Software Factory

Thank you for your interest in contributing to Software Factory! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/macaron-software/software-factory/issues) to avoid duplicates
2. Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
3. Include: steps to reproduce, expected vs actual behavior, environment details

### Suggesting Features

1. Open an issue with the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
2. Describe the use case and expected behavior
3. Explain why this would be useful to other users

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes following the coding standards below
4. Write or update tests
5. Run tests: `make test`
6. Commit with clear messages (see conventions below)
7. Push and open a Pull Request

## Development Setup

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Run tests
make test

# Start dev server
make dev
```

## Coding Standards

### Python

- **Style**: PEP 8, enforced by `ruff`
- **Type hints**: required for public APIs
- **Docstrings**: Google style for modules, classes, public functions
- **Imports**: `from __future__ import annotations` in all files

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add WebSocket real-time channel
fix: resolve route ordering in missions API
refactor: split api.py into sub-modules
docs: update architecture diagrams
test: add worker queue tests
```

### Testing

- Unit tests in `tests/` using `pytest`
- Async tests use `pytest-asyncio`
- E2E tests in `platform/tests/e2e/` using Playwright
- All new features must have tests

### Architecture Rules

- **LLM generates, deterministic tools validate** — use AI for creative tasks, scripts/compilers for validation
- **No god files** — split modules over 500 lines into sub-packages
- **SQLite for persistence** — no external database dependencies
- **Multi-provider LLM** — never hard-code a single provider
- **Backward compatible** — new features must not break existing APIs

## Project Structure

```
platform/           # Core platform (FastAPI)
  agents/           # Agent engine (store, executor, loop)
  patterns/         # Orchestration patterns (10 types)
  missions/         # SAFe lifecycle management
  web/routes/       # API routes (modular sub-packages)
  llm/              # LLM client with cache and fallback
  tools/            # Deterministic tools (AST, lint, type-check)
  events/           # Event sourcing
  plugins/          # Plugin SDK
  workers/          # Job queue
cli/                # CLI client (sf)
tests/              # Test suite
```

## License

By contributing, you agree that your contributions will be licensed under the [AGPL v3 License](LICENSE).
