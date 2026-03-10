# SF Workflow Engine Session Termination Analysis
## CRITICAL FINDINGS: Why Sessions Terminate After 3-9 LLM Messages

---

## EXECUTIVE SUMMARY

The SF workflow engine terminates sessions prematurely due to **multiple cascading limits** that prevent agents from completing full workflows:

1. **Agent Loop Max Rounds: 10 turns** (line 69, agents/loop.py)
2. **Feature-Sprint TDD Loop: 3 iterations max** (line 57, workflows/definitions/feature-sprint.yaml)
3. **Pattern Execution: 5 max_iterations default** (line 691, patterns/engine.py)
4. **Tool Calling: 8 rounds per executor run** (line 41, agents/executor.py)

The **root cause**: Agent loops hit `max_rounds > self.max_rounds` (line 236-244, agents/loop.py), immediately transitioning to IDLE status and terminating the session.

---

## DETAILED FINDINGS

### 1. AGENT LOOP MAX ROUNDS LIMIT (PRIMARY CULPRIT)

**File:** `/Users/sylvain/_MACARON-SOFTWARE/platform/agents/loop.py`

#### Constructor (lines 62-79):
```python
def __init__(
    self,
    agent_def: AgentDef,
    session_id: str,
    project_id: str = "",
    project_path: str = "",
    think_timeout: float = 3600.0,
    max_rounds: int = 10,  # ← DEFAULT = 10 ROUNDS
    workspace_id: str = "default",
):
    ...
    self.max_rounds = max_rounds
    self._rounds = 0
```

**Problem:** Default is 10 rounds, but instantiation doesn't override it.

#### Instantiation (lines 879-884):
```python
loop = AgentLoop(
    agent_def=agent_def,
    session_id=session_id,
    project_id=project_id,
    project_path=project_path,
)  # ← NO max_rounds PASSED → uses default 10
```

#### Round Limit Enforcement (lines 235-244):
```python
# Round limit to prevent infinite loops
self._rounds += 1
if self._rounds > self.max_rounds:
    logger.warning(
        "Agent %s hit max rounds (%d), pausing  session=%s",
        self.agent.id,
        self.max_rounds,
        self.session_id,
    )
    await self._set_status(AgentStatus.IDLE)  # ← TERMINATES AGENT
    break
```

**Status Update (line 243):** Sets agent to IDLE, causing the loop to exit.

**Impact:** After 10 messages through an agent, it stops processing. In a 6-phase workflow where agents collaborate, this is catastrophically low.

---

### 2. FEATURE-SPRINT WORKFLOW: TDD LOOP 3-ITERATION CAP

**File:** `/Users/sylvain/_MACARON-SOFTWARE/platform/workflows/definitions/feature-sprint.yaml`

#### TDD Sprint Phase (lines 50-58):
```yaml
- id: tdd-sprint
  pattern_id: loop
  name: TDD Sprint
  description: 'Devs implémentent en TDD. RED→GREEN→REFACTOR. FRACTAL: feature/guards/failures.'
  gate: no_veto
  config:
    agents: []
    max_iterations: 3  # ← ONLY 3 ITERATIONS ALLOWED
    dynamic_team: true
```

**Location:** Line 57

**Impact:** 
- Each iteration = writer produces code, reviewer provides feedback
- After 3 iterations, TDD phase ENDS (loop exits at line 77, patterns/impls/loop.py)
- If code isn't perfect by iteration 3, phase fails

#### Loop Pattern Implementation (lines 77-122, patterns/impls/loop.py):
```python
for i in range(run.max_iterations):  # ← Uses max_iterations=3 from phase config
    run.iteration = i + 1
    sprint_id = _create_sprint(i + 1)
    
    # Writer produces → sends to reviewer
    writer_output = await engine._execute_node(...)
    
    # ... run build/tests ...
    
    # Reviewer evaluates → sends to writer
    review_output = await engine._execute_node(...)
    
    # Check for approval or veto
    state = run.nodes[reviewer_id]
    if state.status == NodeStatus.VETOED:
        # ← REJECTION: Continue to next iteration
        _finish_sprint(sprint_id, rejected=True, quality=0)
        prev_output = f"[Reviewer feedback, iteration {i+1}]:\n{review_output}"
    else:
        # ← APPROVAL: Break loop early
        _finish_sprint(sprint_id, rejected=False, quality=80)
        sprint_id = None
        break

# If we exited the loop without approving (max iterations), mark last sprint failed
if sprint_id:
    _finish_sprint(sprint_id, rejected=False, quality=30)  # ← FAILURE AFTER 3 TRIES
```

**Result:** After 3 TDD cycles, if code not approved, phase ends with quality=30 (failure).

---

### 3. PATTERN MAX_ITERATIONS DEFAULT

**File:** `/Users/sylvain/_MACARON-SOFTWARE/platform/patterns/engine.py`

#### Line 691 (run_pattern function):
```python
async def run_pattern(
    pattern: PatternDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
    project_path: str = "",
    phase_id: str = "",
    lineage: list[str] | None = None,
    technology: str = "generic",
    phase_type: str = "generic",
) -> PatternRun:
    """Execute a pattern graph in a session. Returns the run state."""
    run = PatternRun(
        pattern=pattern,
        session_id=session_id,
        project_id=project_id,
        project_path=project_path,
        phase_id=phase_id,
        max_iterations=pattern.config.get("max_iterations", 5),  # ← DEFAULT 5
    )
```

**Impact:** If pattern config doesn't specify max_iterations, defaults to 5. Used by all pattern types (parallel, sequential, loop, aggregator).

---

### 4. EXECUTOR TOOL-CALLING ROUNDS LIMIT

**File:** `/Users/sylvain/_MACARON-SOFTWARE/platform/agents/executor.py`

#### Lines 41, 44, 49:
```python
# Max tool-calling rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 8

# REF: arXiv:2602.20021 — SBD-05: per-run tool call budget to prevent resource exhaustion
MAX_TOOL_CALLS_PER_RUN = int(os.getenv("MAX_TOOL_CALLS_PER_RUN", "50"))

# Tools that produce code changes and should trigger auto-verification
_CODE_WRITE_TOOLS = frozenset({"code_write", "code_edit", "code_create"})
# Max automatic repair rounds after a failed verification (lint/build)
MAX_REPAIR_ROUNDS = 3
```

#### Enforcement (lines 661, 1447):
```python
for round_num in range(MAX_TOOL_ROUNDS):  # ← 8 ROUNDS PER EXECUTOR CALL
    # ... tool execution loop ...
    if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
        # Tell agent it's in final rounds
```

**Impact:** Each agent message can make max 8 tool calls. Combined with loop.py's 10-round limit, creates bottleneck.

---

### 5. SESSION STATUS LIFECYCLE

**File:** `/Users/sylvain/_MACARON-SOFTWARE/platform/sessions/store.py`

#### Line 23 (SessionDef):
```python
@dataclass
class SessionDef:
    """A collaboration session."""
    ...
    status: str = "planning"  # planning | active | completed | failed
    ...
```

#### Line 215 (Status Update):
```python
"UPDATE sessions SET status = ?, completed_at = ? WHERE id = ?",
(session_status, datetime.utcnow().isoformat(), session_id)
```

**Session Status Mapping** (lines 960-966, workflows/store.py):
```python
session_status = {
    "completed": "completed",
    "failed": "failed",
    "gated": "interrupted",
    "paused": "interrupted",
    "escalated": "interrupted",
}.get(run.status, "completed")
try:
    store.update_status(session_id, session_status)
except Exception:
    pass
```

**When Session Ends:**
- After all 6 phases complete → status = "completed"
- After any critical phase fails → status = "failed"
- After gate (all_approved) not met → status = "interrupted"
- After max retries exhausted → status = "failed"
- After agent hits max_rounds → agent IDLE, loop breaks → phase timeout or failure

---

### 6. WORKFLOW ENGINE PHASE LOOP

**File:** `/Users/sylvain/_MACARON-SOFTWARE/platform/workflows/store.py`

#### Main Loop (lines 585-956):
```python
for i, phase in enumerate(workflow.phases):  # ← ITERATE THROUGH 6 PHASES
    if i < resume_from:
        continue
    
    run.current_phase = i
    
    try:
        result = await asyncio.wait_for(
            run_pattern(...),  # ← EXECUTE PHASE
            timeout=phase_timeout,  # Default = 172800s (48h)
        )
        
        # Check gates
        if phase.gate == "all_approved" and not result.success:
            run.status = "gated"
            break  # ← STOP WORKFLOW
        elif phase.gate in ("no_veto", "best_effort") and not result.success:
            # Continue
            pass
        
        _save_checkpoint(store, session_id, i + 1)
        
    except asyncio.TimeoutError:
        # Handle timeout
        continue
    except Exception as e:
        # Retry logic...
        break  # ← STOP WORKFLOW ON CRITICAL ERROR
```

#### Workflow Completion (lines 956-957):
```python
if run.status == "running":
    run.status = "completed"
```

**Phases in Feature-Sprint** (6 total):
1. `feature-design` (aggregator)
2. `env-setup` (sequential)
3. `tdd-sprint` (loop) ← **STOPS AFTER 3 ITERATIONS**
4. `adversarial-review` (sequential)
5. `feature-e2e` (parallel)
6. `feature-deploy` (sequential)

---

## ROOT CAUSE CHAIN

```
Agent Loop hits max_rounds=10
    ↓
Agent status → IDLE
    ↓
Agent loop breaks (line 244)
    ↓
Pattern execution halted prematurely
    ↓
Phase incomplete / gated status
    ↓
Workflow stops (phases 1-3 complete, phases 4-6 never reach)
    ↓
Session status → "interrupted" or "failed"
    ↓
LLM messages in that session: typically 3-9 per agent per phase
    ↓
= 6-54 total LLM calls across all phases before termination
```

---

## CONFIG PARAMETERS SUMMARY

| Parameter | File | Line | Value | Scope |
|-----------|------|------|-------|-------|
| `max_rounds` | agents/loop.py | 69 | **10** | Per agent instance |
| `MAX_TOOL_ROUNDS` | agents/executor.py | 41 | **8** | Per executor run |
| `MAX_TOOL_CALLS_PER_RUN` | agents/executor.py | 44 | **50** (env var) | Per run |
| `MAX_REPAIR_ROUNDS` | agents/executor.py | 49 | **3** | Per code verification |
| `max_iterations` (pattern default) | patterns/engine.py | 691 | **5** | Per pattern |
| `max_iterations` (tdd-sprint) | workflows/definitions/feature-sprint.yaml | 57 | **3** | TDD phase only |
| `PHASE_TIMEOUT_SECONDS` | workflows/store.py | 503 | **172800** (48h) | Per phase |

---

## EVIDENCE: WHERE SESSION TERMINATES

### Agent Loop Termination (Line 244):
```python
if self._rounds > self.max_rounds:
    await self._set_status(AgentStatus.IDLE)
    break  # ← EXIT AGENT LOOP
```

### Pattern Execution Returns (Line 940):
```python
return run  # ← PatternRun with success/failure status
```

### Workflow Loop Break (Line 708):
```python
if phase.gate == "all_approved" and not result.success:
    run.status = "gated"
    await _rte_facilitate(...)
    break  # ← EXIT WORKFLOW LOOP
```

### Session Status Update (Line 968):
```python
store.update_status(session_id, session_status)  # ← "interrupted" or "failed"
```

---

## RECOMMENDATIONS FOR FIXES

### IMMEDIATE (Critical):
1. **Increase agent loop max_rounds** from 10 → 50-100
   - File: agents/loop.py:69
   - Pass as parameter in start_agent() call
   
2. **Increase TDD iteration cap** from 3 → 7-10
   - File: workflows/definitions/feature-sprint.yaml:57
   - Allow more refinement cycles

3. **Make max_rounds configurable** via environment variable
   - Add `MAX_AGENT_ROUNDS` env var
   - Add `MAX_TDD_ITERATIONS` env var

### SHORT-TERM:
4. Add telemetry to track session termination reasons
5. Implement early-warning logging when approaching limits
6. Add resumable checkpoints between phases

### LONG-TERM:
7. Implement adaptive limits based on workflow complexity
8. Use phase_outcomes data to calibrate limits
9. Add human-in-the-loop pause before termination

---

## TESTING

To confirm this diagnosis:
1. Start a feature-sprint workflow
2. Monitor agent loop status in session logs
3. Watch for "Agent %s hit max rounds" messages (line 237)
4. Verify session transitions to "idle" → phase timeout/failure
5. Count LLM messages before termination (should be ~10 per agent)

