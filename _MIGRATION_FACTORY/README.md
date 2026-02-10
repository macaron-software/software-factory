# Migration Factory - Framework Upgrade Automation

Specialized factory for **code migrations** (framework upgrades, breaking changes).

**Different from Software Factory (TDD):**

| Aspect | Software Factory | Migration Factory |
|--------|------------------|-------------------|
| **Vision** | VISION.md (features roadmap) | MIGRATION_PLAN.md (before→after state) |
| **Workers** | TDD (RED→GREEN→REFACTOR) | Transform (VALIDATE→TRANSFORM→COMPARE) |
| **Adversarial** | Code quality (no skip/stub) | Behavioral equivalence (old === new) |
| **Skills** | tdd, e2e_ihm, smoke_ihm | breaking_changes, golden_files, codemods |
| **Task Flow** | pending → tdd → build → deploy | pending → pre_validate → transform → compare |
| **Success** | Tests pass | Old behavior === new behavior |

## Supported Migrations

- **Angular:** 16→17, 17→18 (standalone, typed forms, control flow)
- **React:** 17→18, 18→19 (hooks, concurrent rendering)
- **Spring Boot:** 3.x→3.y (breaking changes)
- **Vue:** 2→3 (composition API)

## Architecture

```
_MIGRATION_FACTORY/
├── core/
│   ├── migration_brain.py         # Delta analysis (before→after)
│   ├── transform_worker.py        # VALIDATE→TRANSFORM→COMPARE
│   ├── comparative_adversarial.py # old === new?
│   ├── breaking_changes.py        # Framework changelog DB
│   ├── analyzers/
│   │   ├── angular_analyzer.py
│   │   └── react_analyzer.py
│   └── codemods/
│       ├── angular/
│       │   ├── standalone.ts
│       │   └── typed_forms.ts
│       └── react/
│           └── hooks.ts
├── skills/
│   ├── breaking_changes.md        # Detection & documentation
│   ├── backward_compat.md         # Compatibility testing
│   ├── golden_files.md            # Snapshot comparison
│   └── codemod_patterns.md        # AST transformations
├── projects/
│   └── sharelook.yaml             # Angular 16→17 config
├── cli/
│   └── migrate.py                 # CLI commands
├── data/
│   └── migration.db               # Migration tasks DB
└── golden_files/
    ├── api/
    ├── screenshots/
    ├── console/
    └── network/
```

## Workflow

### 1. Analysis (Migration Brain)

```bash
cd _MIGRATION_FACTORY
python3 cli/migrate.py sharelook analyze
```

**Outputs:**
- `MIGRATION_PLAN.md` (before/after state, breaking changes)
- Migration tasks with risk scores
- Phases ordered (deps → standalone → forms → ...)

### 2. Execution (Transform Worker)

```bash
# Phase 1: Dependencies (auto)
python3 cli/migrate.py sharelook execute --phase deps

# Phase 2: Standalone (manual, high-risk)
python3 cli/migrate.py sharelook execute --phase standalone --workers 3

# Phase 3-N: ...
```

**Each task:**
1. **PRE-VALIDATE:** Capture golden files (API, screenshots, console)
2. **TRANSFORM:** Run codemod OR LLM
3. **POST-VALIDATE:** Capture new golden files
4. **COMPARE:** Diff old vs new (Comparative Adversarial)
5. **If diff > threshold:** ROLLBACK
6. **If OK:** COMMIT

### 3. Deploy (Canary)

```bash
python3 cli/migrate.py sharelook deploy --canary 1,10,50,100
```

**Auto-rollback if:**
- Error rate > baseline + 10%
- Visual regression > 1% pixel diff
- API responses changed
- Console errors increased

## Projects

### Sharelook (Angular 16→17)

**Config:** `projects/sharelook.yaml`

**Stack:**
- Frontend: Angular 16.2.12, TypeScript 5.1.3
  - ai08-admin-ihm (30 modules)
  - ai12-reporting-ihm (20 modules)
- Backend: Spring Boot 3.5.5, Java 21 (microservices)

**Migration phases:**
1. **deps** - Update Angular 16→17 (auto, low-risk)
2. **standalone** - NgModule → Standalone (manual, HIGH-risk, 50 tasks)
3. **typed-forms** - FormGroup → FormGroup<T> (semi-auto, 45 tasks)
4. **control-flow** - *ngIf → @if (auto, 150 tasks)
5. **signals** - Optional Signals API (manual, opt-in)
6. **material** - Angular Material 16→17 (semi-auto, visual changes)

**Command:**
```bash
cd _MIGRATION_FACTORY
python3 cli/migrate.py sharelook analyze
python3 cli/migrate.py sharelook execute --phase deps
# ... repeat for each phase
```

## Key Concepts

### Breaking Changes Database

**Source:** Framework CHANGELOG.md (GitHub)

**Example:** Angular 17 breaking changes
- `ANG-17-001`: ModuleWithProviders<T> type parameter required
- `ANG-17-002`: RouterModule.forRoot → provideRouter
- `ANG-17-003`: FormGroup must be typed
- `ANG-17-004`: Control flow syntax (*ngIf → @if)

**Each breaking change:**
- REF (unique ID)
- Impact (low/medium/high)
- Files affected (pattern)
- Codemod (if available)
- Manual steps (if no codemod)

### Golden Files (Behavior Preservation)

**Before transformation:**
- API responses (JSON)
- Screenshots (PNG)
- Console logs (errors/warnings)
- Network requests
- Test outputs

**After transformation:**
- Same captures

**Comparison:**
- API: JSON diff (must be identical)
- Screenshots: Pixel diff (<1% allowed)
- Console: Error count (same or fewer)
- Tests: Pass count (same or more)

**If diff > threshold:** REJECT + ROLLBACK

### Codemods (AST Transformations)

**Tool:** jscodeshift (JS/TS), libcst (Python), OpenRewrite (Java)

**Example:** Angular standalone
```bash
jscodeshift -t codemods/angular/standalone.ts ai08-admin-ihm/**/*.component.ts
```

**Best practices:**
- One transformation per codemod
- Test with dry-run first
- Preserve formatting (prettier)
- Skip generated files

### Comparative Adversarial (L0→L1→L2)

**L0: Golden file diff (deterministic)**
- Compare before/after snapshots
- API, screenshots, console, network
- Catch rate: ~40%

**L1: Backward compatibility (LLM)**
- Can old clients call new API?
- Feature flags work?
- Hybrid state valid?
- Catch rate: ~30%

**L2: Breaking changes documented (LLM)**
- All breaking changes in CHANGELOG?
- Migration guide exists?
- Rollback strategy?
- Catch rate: ~10%

**Total:** ~80% issues caught before production

## CLI Commands

```bash
# Analysis
migrate <project> analyze

# Execution
migrate <project> execute --phase <phase>
migrate <project> execute --phase <phase> --workers <N>
migrate <project> execute --phase <phase> --task <task-id>

# Status
migrate <project> status
migrate <project> status --phase <phase>

# Rollback
migrate <project> rollback --phase <phase>
migrate <project> rollback --task <task-id>

# Deploy
migrate <project> deploy --canary <stages>
migrate <project> deploy --prod
```

## Example: Sharelook Angular 16→17

```bash
# 1. Setup
cd _MIGRATION_FACTORY
export PYTHONPATH="/Users/sylvain/_MACARON-SOFTWARE:$PYTHONPATH"

# 2. Analyze (generates MIGRATION_PLAN.md + 127 tasks)
python3 cli/migrate.py sharelook analyze

# Output:
# ✅ MIGRATION_PLAN.md created
# ✅ 127 tasks generated:
#    - Phase deps: 1 task (auto)
#    - Phase standalone: 50 tasks (manual, HIGH-risk)
#    - Phase typed-forms: 45 tasks (semi-auto)
#    - Phase control-flow: 20 tasks (auto)
#    - Phase material: 11 tasks (semi-auto)

# 3. Phase 1: Dependencies (auto, low-risk)
python3 cli/migrate.py sharelook execute --phase deps

# Output:
# [PRE-VALIDATE] Capturing golden files...
#   ✅ API responses captured (12 endpoints)
#   ✅ Screenshots captured (8 pages)
#   ✅ Console logs captured
#   ✅ Tests run: 150 passed, 0 failed
# [TRANSFORM] Running: ng update @angular/core@17
#   ✅ Dependencies updated
# [POST-VALIDATE] Capturing new golden files...
#   ✅ API responses captured
#   ✅ Screenshots captured
# [COMPARE] Comparing golden files...
#   ✅ API responses identical
#   ✅ Screenshots identical (0.02% pixel diff)
#   ✅ Console errors unchanged (2 errors before/after)
#   ✅ Tests: 150 passed (no regression)
# [COMMIT] Creating commit...
#   ✅ Committed: "chore: upgrade Angular 16→17 dependencies"

# 4. Phase 2: Standalone (manual, HIGH-risk, module-by-module)
python3 cli/migrate.py sharelook execute --phase standalone --workers 3

# Output:
# [WORKER 1] Task standalone-auth-001: auth.module.ts
#   [PRE-VALIDATE] ✅
#   [TRANSFORM] Codemod: codemods/angular/standalone.ts
#   [POST-VALIDATE] ✅
#   [COMPARE] ✅ Behavior preserved
#   [COMMIT] ✅
# [WORKER 2] Task standalone-users-002: users.module.ts
#   ...
# [WORKER 3] Task standalone-posts-003: posts.module.ts
#   ...

# 5. Repeat for phases 3-6...

# 6. Deploy with canary
python3 cli/migrate.py sharelook deploy --canary 1,10,50,100

# Output:
# [CANARY 1%] Deploying to 1% users...
#   ✅ Error rate: 0.5% (baseline: 0.4%, delta: +0.1%, OK)
#   ✅ Latency p95: 320ms (baseline: 310ms, delta: +10ms, OK)
#   ⏳ Waiting 5min...
# [CANARY 10%] Deploying to 10% users...
#   ✅ Error rate: 0.6% (delta: +0.2%, OK)
#   ⏳ Waiting 5min...
# [CANARY 50%] Deploying to 50% users...
#   ✅ All metrics OK
# [CANARY 100%] Full rollout
#   ✅ Migration complete!
```

## Differences from Software Factory

### 1. Vision

**SF:** VISION.md (product roadmap, features to build)
```markdown
# Vision: Veligo V2

## Features
- Offline sync
- Geolocation
- Push notifications
```

**MF:** MIGRATION_PLAN.md (before→after state, delta to apply)
```markdown
# Migration Plan: Angular 16 → 17

## Before
- Architecture: NgModule-based
- Forms: Untyped

## After
- Architecture: Standalone
- Forms: Typed

## Breaking Changes
- [ANG-17-001] ModuleWithProviders<T>
- [ANG-17-002] provideRouter
```

### 2. Workers

**SF TDD Worker:**
```
RED (test fails) → GREEN (fix) → REFACTOR (clean) → COMMIT
```

**MF Transform Worker:**
```
PRE-VALIDATE (capture) → TRANSFORM (codemod/LLM) → POST-VALIDATE (capture) → COMPARE (diff) → COMMIT or ROLLBACK
```

### 3. Adversarial

**SF Adversarial:** "Is this code good quality?"
- L0: test.skip, @ts-ignore, stubs
- L1: Syntax, API misuse, SLOP
- L2: Architecture, SOLID, patterns

**MF Comparative Adversarial:** "Is old === new?"
- L0: Golden file diff (API, screenshots, console)
- L1: Backward compatibility (old clients still work)
- L2: Breaking changes documented

### 4. Skills

**SF Skills:**
- `tdd.md` - RED-GREEN-REFACTOR
- `e2e_ihm.md` - Browser tests
- `smoke_ihm.md` - Quick checks

**MF Skills:**
- `breaking_changes.md` - Detection & docs
- `backward_compat.md` - Compatibility testing
- `golden_files.md` - Snapshot comparison
- `codemod_patterns.md` - AST transformations

### 5. Success Criteria

**SF:** Tests pass, code quality, no regressions
**MF:** Old behavior === new behavior, no visual/API changes

## Next Steps

1. ✅ Create Migration Factory structure
2. ✅ Add Sharelook project config
3. ✅ Create skills (4 files)
4. ⏳ Implement `migration_brain.py`
5. ⏳ Implement `transform_worker.py`
6. ⏳ Implement `comparative_adversarial.py`
7. ⏳ Create Angular codemods (standalone, typed-forms, control-flow)
8. ⏳ Test on Sharelook ai08-admin-ihm

## References

- **Angular Update Guide:** https://angular.io/guide/update
- **jscodeshift:** https://github.com/facebook/jscodeshift
- **Feature Flags:** https://martinfowler.com/articles/feature-toggles.html
- **Canary Deployments:** https://martinfowler.com/bliki/CanaryRelease.html
