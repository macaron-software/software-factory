# Contributing to Software Factory

Thank you for your interest in contributing! This document provides guidelines for code quality, commit conventions, and development workflow.

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR-USERNAME/software-factory.git
cd software-factory
```

### 2. Install Git Hooks + Quality Tools

**This is the most important step!** It installs local linters and Git hooks that enforce code quality.

```bash
make install-hooks
```

This will:

- Install Python linters (ruff, bandit, safety, pytest)
- Install JavaScript linters (eslint, prettier, jest) if `package.json` exists
- Setup Git hooks: `pre-commit`, `commit-msg`, `pre-push`
- Create configuration files: `.ruff.toml`, `.eslintrc.json`, `.prettierrc`, `pytest.ini`

### 3. Create a Branch

```bash
git checkout -b feat/my-feature
# or
git checkout -b fix/bug-description
```

## Coding Standards

### Python

- **Line length**: 100 characters
- **Style**: Follow PEP8, enforced by Ruff
- **Security**: No hardcoded secrets, SQL injections, or unsafe eval()
- **Tests**: Coverage ≥ 80% for new code

**Ruff** will auto-fix most style issues on commit.

### JavaScript/TypeScript

- **Line length**: 100 characters
- **Style**: Prettier enforced (semi-colons, double quotes)
- **Linting**: ESLint with TypeScript + React plugins
- **Tests**: Coverage ≥ 75% for new code

**Prettier + ESLint** will auto-fix on commit.

### Documentation

- **Markdown**: Use markdownlint rules (see `.markdownlintrc` if created)
- **Docstrings**: Required for all public functions/classes
- **Comments**: Only when necessary (code should be self-explanatory)

## Commit Message Format

We follow **Conventional Commits** format. Your commits will be validated by the `commit-msg` hook.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `chore`: Maintenance tasks (dependencies, configs)
- `refactor`: Code refactoring (no functional changes)
- `test`: Test changes
- `ci`: CI/CD changes
- `perf`: Performance improvements
- `build`: Build system changes
- `style`: Code style changes (formatting)

### Examples

```bash
feat(auth): add OAuth2 login support
fix(api): handle null pointer in user endpoint
docs: update README with installation steps
chore(deps): upgrade fastapi to 0.104
refactor(agents): simplify adversarial pattern logic
test(memory): add integration tests for vector search
```

### Description Rules

- **Minimum 10 characters**
- **Imperative mood**: "add feature" not "added feature"
- **Lowercase**: "add feature" not "Add feature"
- **No period**: "add feature" not "add feature."

## Git Hooks Workflow

### pre-commit (Auto-fix + Validation)

Runs on every `git commit`:

1. **Python**: Ruff linter + auto-fix, Bandit security scan
2. **JavaScript**: ESLint + auto-fix, Prettier format
3. **Secrets**: detect-secrets scan
4. **Result**: Auto-fixed files are re-staged, critical errors block commit

**Auto-fix example:**

```bash
git add my_file.py
git commit -m "feat: add new feature"
# → Ruff auto-fixes style issues
# → Files re-staged automatically
# → Commit succeeds if no critical errors
```

### commit-msg (Format Validation)

Validates commit message follows Conventional Commits format.

**If invalid:**

```bash
❌ Invalid commit message format!

Expected: <type>(<scope>): <description>
Your message: Added new feature

# Fix:
git commit -m "feat: add new feature"
```

### pre-push (Tests + Security)

Runs before `git push`:

1. **Python tests**: pytest with coverage ≥ 80%
2. **JavaScript tests**: jest with coverage ≥ 75%
3. **Security scans**: safety (Python deps), npm audit (JS deps), trivy (containers)
4. **Result**: Push blocked if tests fail or coverage too low

**Example output:**

```bash
git push
🚀 Running pre-push checks...
🧪 Running Python tests with coverage...
✅ Python tests passed with ≥80% coverage
🔒 Running security scans...
✅ Pre-push checks passed! Pushing...
```

## Bypassing Hooks (Emergency Only)

If you **absolutely must** bypass hooks (not recommended):

```bash
# Skip pre-commit + commit-msg
git commit --no-verify -m "hotfix: urgent fix"

# Skip pre-push
git push --no-verify
```

⚠️ **Use sparingly!** Bypassed commits may be rejected in code review.

## Running Quality Checks Manually

### Check Staged Files Only

```bash
make quality
```

### Full Quality Scan (All Files)

```bash
make quality-full
```

### Tests with Coverage Report

```bash
make test-coverage
# Opens: htmlcov/index.html
```

## Code Review Checklist

Before submitting a PR, ensure:

- [ ] All Git hooks passed (pre-commit, commit-msg, pre-push)
- [ ] Tests added for new features
- [ ] Coverage ≥ 80% (Python) / 75% (JavaScript)
- [ ] No hardcoded secrets or credentials
- [ ] Documentation updated (README, docstrings)
- [ ] Commit messages follow Conventional Commits
- [ ] Branch is up-to-date with `master`

## Testing

### Run All Tests

```bash
make test
```

### Run Tests with Coverage

```bash
make test-coverage
```

### Run Specific Test File

```bash
pytest tests/test_my_feature.py -v
```

### Run Tests for Modified Files Only

```bash
# The pre-push hook does this automatically
pytest --lf  # Last failed tests only
```

## Security

### Before Committing

- **No secrets**: API keys, tokens, passwords in code
- **Use .env**: Store secrets in `.env` (gitignored)
- **Scan first**: Run `detect-secrets scan` manually if unsure

### Security Tools

- **Bandit**: SAST for Python (injection, eval, hardcoded secrets)
- **Safety**: CVE scanner for Python dependencies
- **npm audit**: CVE scanner for JavaScript dependencies
- **Trivy**: Container and IaC vulnerability scanner

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue with reproducible steps
- **Features**: Open a GitHub Issue with use case description

## License

By contributing, you agree that your contributions will be licensed under AGPL v3.

---

## Quick Reference

```bash
# Setup
make install-hooks          # Install hooks + tools (once)

# Development
make dev                    # Run platform locally (no Docker)
make run                    # Run platform with Docker
make logs                   # View platform logs

# Quality
make quality                # Lint staged files
make quality-full           # Lint all files
make test-coverage          # Tests + HTML coverage report

# Commit
git add .
git commit -m "feat(scope): description"  # Auto-linting happens here
git push                                   # Tests run here

# Emergency bypass (not recommended)
git commit --no-verify
git push --no-verify
```

---

**Happy coding!** 🚀
