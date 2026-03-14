# Formal Verification (TLA+)

This directory contains TLA+ specifications that formally model critical
invariants of the SF platform.  The specs are checked with the TLC model
checker (`tla2tools.jar`) and can also be explored interactively in the
TLA+ Toolbox IDE.

## Specifications

| Module | What it models | Key invariants |
|---|---|---|
| `NodeStateMachine` | Node execution lifecycle (PENDING / RUNNING / COMPLETED / VETOED / FAILED) | Monotonic transitions, retry bound, eventual termination |
| `PMCheckpoint` | PM v2 decision loop (next / loop / skip / done / phase) | Decision budget (20), consecutive-loop cap (2), phase-queue boundedness, termination |
| `ConcurrentPatterns` | Parallel workers + barrier aggregator + wave dependencies | Aggregator safety, wave ordering |
| `AdversarialGuard` | Adversarial retry guard (score evaluation, nudge, critical flags) | No limbo state, retry bound, eventual resolution |
| `SafetyProperties` | Cross-cutting platform safety | No RUNNING+PAUSED, YOLO suppresses pause, protected branches, workspace sandbox |

## Running TLC

### Prerequisites

TLC is distributed as a single JAR.  Inside the SF container it lives at
`/app/tools/tla2tools.jar`.  On a dev machine you can grab it from the
[TLA+ releases](https://github.com/tlaplus/tlaplus/releases):

```bash
curl -Lo tla2tools.jar \
  https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
```

### Check a specification

```bash
java -jar tla2tools.jar -config NodeStateMachine.cfg NodeStateMachine.tla
```

Or use the platform tool:

```bash
# via agent tool call
tla_check spec_path=NodeStateMachine.tla
tla_list
```

### Keeping state spaces small

Each `.cfg` file uses small constant values (e.g., `N = 3`, `NUM_PHASES = 3`)
to keep the state space tractable for automated CI checks.  For deeper
exploration, increase constants at the cost of longer run times.

## Design principles

1. **One module per concern** -- keeps TLC state explosion manageable.
2. **PlusCal optional** -- specs use raw TLA+ for precision; PlusCal is
   encouraged for future imperative-style models.
3. **Liveness via fairness** -- `WF_vars(Next)` ensures enabled actions
   eventually fire, proving termination properties.
4. **Small constants in .cfg** -- CI-friendly; increase for exploration.

## Adding a new spec

1. Create `MySpec.tla` with `SPECIFICATION Spec` and `INVARIANTS`.
2. Create `MySpec.cfg` with `SPECIFICATION Spec` and constant assignments.
3. Run `tla_check spec_path=MySpec.tla` to verify.
4. The spec will automatically appear in `tla_list` output.
