# GitHub Actions Workflows

## Overview

This repository uses 3 complementary CI/CD workflows:

1. **quality.yml** - Comprehensive quality checks (runs on push/PR)
2. **pr-quality-gates.yml** - Strict PR validation (blocking)
3. **deploy.yml** - Continuous deployment (manual + auto)

---

## 1. quality.yml - Code Quality & Security

**Triggers:** Push to main/master/develop, Pull Requests, Manual
**Purpose:** Non-blocking quality feedback with matrix testing

### Jobs

#### Python Quality (Matrix: 3.10, 3.11, 3.12)
- Ruff linting + formatting
- Bandit security scan
- Uploads artifacts per Python version

#### JavaScript Quality
- ESLint + Prettier
- TypeScript type checking

#### Security Scan
- Trivy vulnerability scanner
- SARIF upload to GitHub Security tab

#### Secrets Detection
- TruffleHog for hardcoded credentials
- Scans entire history

#### Tests & Coverage
- Pytest with coverage reporting
- Codecov integration
- Coverage reports uploaded as artifacts

#### E2E Tests (Playwright)
- **Conditional:** Only on PRs or manual trigger
- Starts test server (uvicorn)
- Runs Playwright browser tests
- Uploads test reports

### Features
- **Matrix Testing:** Python 3.10/3.11/3.12 in parallel
- **Smart Caching:** Pip + NPM dependencies cached
- **Path Ignore:** Skips on docs-only changes
- **Artifacts:** Bandit reports, coverage, Playwright results
- **Non-Blocking:** All jobs allow failures (warnings only)

---

## 2. pr-quality-gates.yml - Pull Request Validation

**Triggers:** Pull Requests (opened, synchronize, reopened)
**Purpose:** Strict quality gates that block PR merging

### Jobs

#### Changes Detection
- Uses `dorny/paths-filter` to detect file changes
- Skips irrelevant jobs (e.g., no JS changes → skip JS lint)
- Outputs: `python`, `javascript`, `docs`

#### Python Linting (Blocking)
- **Runs if:** Python files changed
- **Fails on:** Ruff errors or formatting issues
- **Strict:** No `|| true` - must pass

#### JavaScript Linting (Blocking)
- **Runs if:** JS/TS files changed
- **Fails on:** ESLint errors, Prettier violations
- **Strict:** Enforces code style

#### Security Check (Blocking)
- **Always runs**
- Bandit for Python (fails on HIGH severity)
- TruffleHog for secrets (fails on verified leaks)
- **Critical:** Blocks merge on security issues

#### Required Tests
- **Runs if:** Python files changed
- Pytest with **minimum 70% coverage**
- **Fails if:** Coverage < 70% or tests fail
- Uploads coverage to Codecov with PR flag

#### PR Quality Summary
- Aggregates all gate results
- **Fails PR** if any gate fails
- **Passes PR** if all gates pass or skip
- Clear status reporting

### Features
- **Concurrency Control:** Cancels old runs on new push
- **Change-Based Execution:** Only runs relevant jobs
- **Blocking:** Must pass to merge (enforced via branch protection)
- **Coverage Requirement:** Minimum 70% enforced

---

## 3. deploy.yml - Continuous Deployment

**Triggers:** Push to main/master, Manual dispatch
**Purpose:** Automated and manual deployments

### Environments
- **Staging:** Auto-deploy on push to main
- **Production:** Manual only (workflow_dispatch)

### Jobs

#### Build & Test
- Runs full test suite
- Generates build artifacts
- Shows commit metadata

#### Deploy to Staging
- **Auto-triggered** on push to main/master
- Environment: `staging`
- Placeholder for actual deployment steps
- TODO: SSH, pull, restart, health checks

#### Deploy to Production
- **Manual trigger only**
- Requires environment approval
- Environment: `production`
- Extra safety: Notifications + smoke tests

#### Deployment Summary
- Aggregates all results
- Status reporting

### Features
- **Environment Protection:** Production requires approval
- **Manual Control:** Production never auto-deploys
- **Path Ignore:** Skips on docs/workflow changes
- **Audit Trail:** Full deployment history in GitHub

---

## Branch Protection Rules

Recommended settings for `main` and `master`:

```yaml
Protected branches: main, master

Require pull request before merging:
  ✅ Enabled
  Required approvals: 1
  Dismiss stale reviews: true

Require status checks to pass:
  ✅ Python Linting (Blocking)
  ✅ JavaScript Linting (Blocking)  
  ✅ Security Check (Blocking)
  ✅ Required Tests
  ✅ PR Quality Gate

Require conversation resolution: true
Require signed commits: false (optional)
Require linear history: false
```

---

## Local Testing

Reproduce CI checks locally before pushing:

```bash
# Quick checks (staged files only)
make quality

# Full quality scan
make quality-full

# Run tests with coverage
make test-coverage

# Install all tools
make install-hooks
```

---

## Workflow Diagram

```
Push/PR
  ├─> quality.yml (non-blocking feedback)
  │    ├─> Python 3.10/3.11/3.12 (matrix)
  │    ├─> JavaScript lint
  │    ├─> Security scan (Trivy)
  │    ├─> Secrets detection
  │    ├─> Tests + Coverage
  │    └─> E2E (Playwright) [PR only]
  │
  ├─> pr-quality-gates.yml (blocking)
  │    ├─> Detect changes
  │    ├─> Python lint [FAIL = BLOCK]
  │    ├─> JS lint [FAIL = BLOCK]
  │    ├─> Security [FAIL = BLOCK]
  │    ├─> Tests 70%+ [FAIL = BLOCK]
  │    └─> Summary [FAIL = BLOCK]
  │
  └─> On merge to main
       └─> deploy.yml
            ├─> Build & Test
            ├─> Deploy Staging (auto)
            └─> Deploy Production (manual)
```

---

## Secrets Required

Configure these in repository settings → Secrets:

- `CODECOV_TOKEN` - For coverage uploads
- `DEPLOYMENT_SSH_KEY` - For server deployments (future)
- `SLACK_WEBHOOK` - For deployment notifications (future)

---

## Maintenance

### Update Dependencies
```bash
# Python
pip-compile requirements-dev.txt --upgrade

# JavaScript  
npm update
```

### Add New Job
1. Add to `quality.yml` for feedback
2. Add to `pr-quality-gates.yml` if blocking
3. Update this README
4. Test with workflow_dispatch

---

## Troubleshooting

### Job always skipped
- Check `needs` dependencies
- Check `if` conditions
- Verify branch name matches trigger

### Coverage fails locally but passes in CI
- Different Python versions
- Missing test dependencies
- Run `make test-coverage` to reproduce

### E2E tests timeout
- Increase server startup wait (currently 10s)
- Check if port 8099 available
- Review Playwright config timeouts

### Secrets not detected
- TruffleHog only catches **verified** secrets
- Add custom patterns in `.trufflehog.yml`
- Use `--no-verification` for more aggressive scan
