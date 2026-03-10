# SF Pipeline Investigation — Full Report

## 1. RTE AGENT SKILL (Release Train Engineer)

### Agent Definition
- **ID**: `rte`
- **Name**: Marc Delacroix
- **Role**: Release Train Engineer
- **File**: `/Users/sylvain/_MACARON-SOFTWARE/platform/agents/store.py`, lines 720-745

### System Prompt
```
Tu es le Release Train Engineer (RTE). Tu orchestre l'ART.
Responsabilités: PI Planning, Scrum of Scrums, Inspect & Adapt.
Tu coordonnes 8 Feature Teams. WIP max 4 features en //.
PI = 5 jours. Sprints = 4h. Daily sync cross-team.
```

### Configuration
- **Temperature**: 0.5 (moderate creativity)
- **Hierarchy Rank**: 5 (high authority — just below CEO level 0)
- **Permissions**:
  - `can_delegate`: True
  - `can_veto`: True (STRONG veto level)
- **Tags**: `["safe", "art", "orchestration", "pi-planning"]`
- **Tools**: None explicitly configured (relies on LLM generation)
- **Skills**: None listed

### Phase Transition Knowledge
**❌ CRITICAL GAP**: The RTE system prompt does NOT mention:
- How to detect phase completion criteria
- When/how to trigger transitions to next phase
- What gates or checks to perform before transitioning
- How to communicate phase completion to the system

**System Prompt is MINIMAL** — only 4 lines, no detail on:
- Phase names or phase IDs
- Phase state checkpoints
- Failure recovery procedures
- Impediment escalation paths

### How RTE Facilitates Transitions
From `platform/workflows/store.py`, lines 201-300:

**Function**: `_rte_facilitate(session_id, prompt, to_agent, project_id)`

**What happens**:
1. Looks up RTE agent from agent store
2. Creates ExecutionContext with `tools_enabled=False` — **RTE can ONLY SPEAK, NOT ACT**
3. Calls LLM via `executor.run_streaming()` with the prompt
4. Streams response via SSE (Server-Sent Events)
5. Stores message in session message store
6. **Returns the RTE's text content** (does NOT return structured phase transition data)

**Key Issue**: RTE produces text messages, NOT structured phase events:
- No return of `{phase: next_id, criteria_met: bool}`
- No structured JSON phase transition commands
- All phase advancement is driven by hard-coded workflow loop logic, NOT by RTE output

---

## 2. PRODUCT AGENT SKILL

### Agent Definition
- **ID**: `product`
- **Name**: Laura Vidal
- **Role**: Product Owner
- **File**: `/Users/sylvain/_MACARON-SOFTWARE/platform/agents/store.py`, lines 418-433

### Configuration
- **Temperature**: 0.5 (moderate)
- **System Prompt**: **MISSING** — defaults to empty string
- **Skills**: `["brainstorming", "spec-driven-quality"]`
- **Tools**: None explicitly configured
- **Tags**: `["product", "business"]`
- **Hierarchy Rank**: 50 (default, junior-level positioning — **WEAK**)

### What Product Agent Does (Feature-Design Phase)
**❌ CRITICAL GAP**: Product agent has:
- NO system prompt instructions
- NO explicit connection to feature-design phase
- NO defined acceptance criteria generation method
- Only skill names: "brainstorming" (undefined) and "spec-driven-quality" (undefined)

**Likely Behavior**: 
- Generic LLM behavior with minimal guidance
- No safeguards for slop/repetitive output
- No WSJF scoring template
- No traceability to user stories or requirements

The agent likely:
1. Reads feature brief
2. Generates user stories (weakly)
3. Generates acceptance criteria (generic)
4. No structured output validation

**Why it stalls**:
- Low hierarchy rank (50) means other agents may override
- No explicit product phase checklist
- No defined "done" criteria for feature-design

---

## 3. FT-INFRA-LEAD AGENT (Environment Setup)

### Agent Definition
- **ID**: `ft-infra-lead`
- **Name**: Francois Mercier
- **Role**: Lead DevOps
- **File**: `/Users/sylvain/_MACARON-SOFTWARE/platform/agents/store.py`, lines 1170-1202

### System Prompt (Explicit & Detailed)
```
Lead DevOps. Docker, nginx, CI/CD, monitoring, Azure. Multi-tenant.
DEPLOY PHASE — quand phase_id contient 'deploy': après chaque déploiement réussi, 
émettre obligatoirement un DELIVERY_REPORT avec le format suivant :
```
DELIVERY_REPORT
image: <nom_image:version>
url: <url_deployed>
health: OK|FAIL
smoke_tests: PASS|FAIL
rollback_available: true|false
```
Sans DELIVERY_REPORT, le deploy est considéré incomplet et retourne VETO.
```

### Configuration
- **Temperature**: 0.3 (low, focused)
- **Hierarchy Rank**: 20 (lead level)
- **Permissions**:
  - `can_delegate`: True
  - `can_veto`: True (ADVISORY level)
- **Tags**: `["feature-team", "infra", "devops", "lead"]`
- **Model**: DEFAULT (varies by provider)

### Environment Setup Phase Details
**What env-setup requires**:
1. Create Docker build environment
2. Set up CI/CD pipeline
3. Configure health checks
4. Prepare rollback procedures
5. **MUST emit DELIVERY_REPORT after deployment**

**Critical Pattern**: 
- The system prompt **mandates structured output** (DELIVERY_REPORT)
- Missing DELIVERY_REPORT = automatic VETO
- This is the ONLY agent with such explicit gate requirements

**Why it succeeds**:
- Explicit system prompt with checkpoints
- Clear acceptance format (DELIVERY_REPORT)
- Unambiguous failure condition (missing report = veto)

---

## 4. WORKER AGENT (TDD Sprint Loop)

### Agent Definition
- **ID**: `worker`
- **Name**: Yann Lefevre
- **Role**: TDD Worker
- **File**: `/Users/sylvain/_MACARON-SOFTWARE/platform/agents/store.py`, lines 293-322

### System Prompt
```
You are a TDD Worker. Write code following strict Red-Green-Refactor.
Each task is atomic and KISS. Write the test FIRST, then minimal code to pass.
Never skip tests. Never use .unwrap() in Rust. Handle all errors explicitly.
```

### Configuration
- **Temperature**: 0.4 (low, deterministic)
- **Skills**: 10 tech skills including TDD, debugging, API design, FastAPI, testing patterns
- **Tags**: `["coding", "tdd"]`
- **Hierarchy Rank**: 50 (junior)

### TDD Sprint Loop Behavior
1. **Red**: Write failing test
2. **Green**: Write minimal code to pass
3. **Refactor**: Clean up code
4. **Repeat**: Atomic cycles

**In practice**:
- Worker writes code via `code_write` tool
- System calls adversarial guard on output
- Guard checks for:
  - Test cheating (`test.skip()`, `@ts-ignore`, empty tests)
  - Mock implementations (`pass`, `NotImplementedError`)
  - Test coverage (source files must have corresponding test files)
  - NO_TESTS flag if ≥3 source files but 0 test files

**Why it stalls**:
- If adversarial guard scores > 5, worker output is REJECTED and message says "REJECTED (score=X): [issues]"
- Worker does NOT receive feedback on WHY (only the score)
- No explicit retry strategy or learning loop
- Workers keep trying same patterns because system only says "rejected" not "try this instead"

---

## 5. ADVERSARIAL QUALITY SYSTEM

### Location
`/Users/sylvain/_MACARON-SOFTWARE/platform/agents/adversarial.py` (1336 lines)

### Architecture: Swiss Cheese Model (Two Layers)

#### L0: Deterministic Fast Checks (0ms)
**Always runs.** Returns immediately if critical issues found.

**Pattern Categories**:
1. **SLOP** (score +3): Generic filler text
   - Lorem ipsum, placeholder text, "TBD", "XXX", example.com URLs

2. **MOCK** (score +4): Fake implementations
   - `raise NotImplementedError`, `pass # TODO`, stub returns
   - `@ts-ignore`, `# type:ignore`, unused imports

3. **FAKE_BUILD** (score +7): Hardcoded success
   - `echo "BUILD SUCCESS"`, fake shell scripts
   - Suspiciously small build scripts (<50 chars)

4. **TEST_CHEAT** (score +5): Hidden bugs via test manipulation
   - `test.skip()`, `@xtest`, empty test bodies
   - `assert True`, `except: pass` (empty catch)
   - Coverage = 0

5. **CODE_SLOP** (score +2 per hit, max 3): Bad patterns in code
   - `@ts-ignore`, `# type:ignore`, `!important`, vendor prefixes
   - Dead/unnecessary code patterns

6. **HALLUCINATION** (score +5): Claims without tool evidence
   - Agent says "I created file X" but no `code_write` tool call exists
   - Agent says "Ran test" but no test tool call exists

7. **LIE** (score +5): Invented results
   - Claims about file creation without tool evidence

8. **NO_TESTS** (score +4): ≥3 source files written, 0 test files
   - Critical for TDD validation

9. **STACK_MISMATCH** (score +7): Wrong language for project
   - Task says Rust/axum backend, agent writes TypeScript

10. **TOO_SHORT** (score +2): Content < min length
    - Minimum varies by role (default 100 chars)

11. **ECHO** (score +4): >70% quoted text
    - Agent just pasted the prompt back

12. **HIGH_COMPLEXITY** (score +3): Nesting >6 levels or >120 lines per function

13. **MISSING_DEPS** (score +2): Source code written but no dependency manifest
    - Wrote Python but no requirements.txt/pyproject.toml
    - Wrote Go but no go.mod

14. **FAKE_TESTS** (score +6): Non-code files (.md, .txt) in test directory

15. **HARDCODED_SECRET** (score +8): Credentials in source (not test fixtures)
    - API keys, passwords, connection strings

16. **SECURITY_VULN** (score varies): Unsafe operations in code

**L0 Rejection Threshold**:
- **score >= 5**: REJECTED
- **score < 5**: WARNING (pass but record issues)

**Example Score Calculation** ("ADVERSARIAL REJECT score=7"):
- `test.skip()` detected in test file: +5
- Empty catch block in code: +2
- **Total: 7 → REJECTED**

#### L1: Semantic LLM Check (~5s)
**Only if**:
- L0 passed (score < 5)
- Pattern type in {sequential, hierarchical, parallel, loop, aggregator}
- Agent role is "dev" (not product/business/strategic)

**Process**:
1. Uses a **DIFFERENT LLM** (not the producer's LLM)
2. Runs semi-formal reasoning protocol (arXiv:2603.01896):
   - **PREMISES**: Extract verifiable facts from tool evidence
   - **TRACE**: Map each agent claim to a premise OR mark UNVERIFIED
   - **VERDICT**: Derive conclusion ONLY from trace
3. Checks for:
   - HALLUCINATION: Claims not in tool evidence
   - SLOP: Generic filler
   - MOCK: Fake code
   - LIES: Invented results
   - ECHO: Task rephrasing
   - STACK_MISMATCH: Wrong language

4. Unverified claims in hierarchical patterns are softened:
   - **LEADS/TESTERS can reference files from WORKERS** (not hallucination)
   - Accounts for multi-agent team structure

**L1 Rejection Threshold**:
- **score >= 7 OR verdict=REJECT**: REJECTED
- **score 6-8 with soft issues only**: Depends on whether agent used `code_write` tools
  - If code_write present: pass threshold raised to 8 (tolerance for soft issues)
  - If no code_write: pass threshold = 6

**Example L1 Rejection Message**:
- "L1: HALLUCINATION — claims executed git commit but no git_commit tool call"
- "L1: STACK_MISMATCH — task requires Rust backend, agent wrote Python"

### Key Gaps in Adversarial System

**❌ Gap 1**: L0 rejects with NO feedback on fix
- Only returns "REJECTED (score=7): SLOP/ECHO/MOCK"
- Does NOT return "To fix: Remove placeholder text, write real content"

**❌ Gap 2**: No learning loop for worker agents
- Worker gets rejected, doesn't learn why
- System doesn't suggest corrective action
- Worker may repeat same mistake

**❌ Gap 3**: L1 semantic check requires different LLM
- If all instances use same LLM provider, L1 is useless
- L1 score sensitive to model temperature and random seed

**❌ Gap 4**: Hierarchical pattern false negatives
- Leads can reference workers' files (correct)
- But no validation that those files actually exist
- Can allow leads to make up file contents

---

## 6. AUTO-RESUME SYSTEM

### Location
`/Users/sylvain/_MACARON-SOFTWARE/platform/services/auto_resume.py` (1261 lines)

### Resume Candidates Selection (Lines 237-356)

**Function**: `_resume_batch(stagger: float = 3.0)`

**Query Candidates From Database**:

#### 1. Paused Runs (SQL, lines 247-258)
```sql
SELECT mr.id, mr.workflow_id, m.name, m.type, m.status, mr.resume_attempts
FROM epic_runs mr
LEFT JOIN epics m ON m.id = mr.session_id
WHERE mr.status = 'paused' AND mr.workflow_id IS NOT NULL
  AND COALESCE(mr.human_input_required, 0) = 0
  AND mr.updated_at >= datetime('now', '-48 hours')
ORDER BY mr.created_at DESC
LIMIT 500
```
- **Duration constraint**: Only last 48 hours
- **Excludes**: Runs with `human_input_required` flag set
- **Returns**: up to 500 paused runs

#### 2. Stuck Pending Runs (SQL, lines 261-271)
```sql
SELECT mr.id, mr.workflow_id, m.name, m.type, m.status
FROM epic_runs mr
LEFT JOIN epics m ON m.id = mr.session_id
WHERE mr.status = 'pending' AND mr.workflow_id IS NOT NULL
  AND mr.created_at <= datetime('now', '-10 minutes')
  AND (m.status IS NULL OR m.status = 'active')
ORDER BY mr.created_at ASC
LIMIT 20
```
- **Stall Threshold**: Pending >10 minutes = stalled
- **Returns**: up to 20 stuck runs

#### 3. Failed Continuous Missions (SQL, lines 274-294)
```sql
SELECT mr.id, mr.workflow_id, m.name, m.type, m.status
FROM epic_runs mr
LEFT JOIN epics m ON m.id = mr.session_id
WHERE mr.status = 'failed' AND mr.workflow_id IS NOT NULL
  AND (m.status IS NULL OR m.status = 'active')
  AND mr.created_at >= datetime('now', '-7 days')
  AND mr.id = (SELECT mr2.id FROM epic_runs mr2
               WHERE mr2.session_id = mr.session_id
               ORDER BY mr2.created_at DESC LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM epic_runs mr3
                  WHERE mr3.session_id = mr.session_id
                    AND mr3.status IN ('pending', 'running'))
ORDER BY mr.created_at DESC
LIMIT 20
```
- **Only latest run per mission**: One failed run per mission tracked
- **Active missions only**: Only retry if mission status = 'active'
- **No concurrent runs**: Must not have pending/running version
- **7-day window**: Only retry failures from last 7 days

#### Candidate Filtering (Lines 298-356)

**Categorize into 4 buckets**:
1. `continuous_paused`: Paused runs where `_is_continuous(name, type)` = True
   - **Continuous keywords**: "tma", "sécurité", "securite", "security", "dette technique", "tech debt", "self-heal", "tmc", "load test", "chaos", "endurance", "monitoring", "audit"
2. `others_paused`: Paused runs that are NOT continuous
3. `stuck_pending`: Pending runs stuck >10 minutes
4. `continuous_failed`: Failed continuous missions (latest only, no running counterpart)

**Exponential Backoff Filter** (Lines 320-332):
```python
def _backoff_ok(run_id: str) -> bool:
    attempts = _attempts.get(run_id, 0)
    if attempts <= 2:
        return True  # Always retry first 2 times
    if attempts <= 5:
        interval = 2 ** (attempts - 2)  # 2, 4, 8, 16, 32 min intervals
        return (_now_minute % interval) == 0
    return False  # >5 attempts = wait for manual review
```
- **Attempt 0-2**: Always retry (immediate)
- **Attempt 3**: Skip 50% chance (mod arithmetic)
- **Attempt 4**: Skip unless low system load
- **Attempt 5+**: STOP — wait for manual intervention

**Final Candidate List** (Line 334-344):
```python
candidates = [r for r in (continuous_paused + others_paused + stuck_pending + continuous_failed)
              if _backoff_ok(r)]
to_resume = candidates

# On startup (large stagger), cap batch to avoid CPU saturation
if stagger >= stagger_startup:
    to_resume = to_resume[:batch_max]  # batch_max defaults to 1
```

**Log Output** (Line 349-356):
```
"auto_resume: %d candidates (paused-continuous=%d, paused-other=%d, stuck-pending=%d, failed-continuous=%d)"
```
Example: `auto_resume: 3 candidates (paused-continuous=1, paused-other=1, stuck-pending=1, failed-continuous=0)`

### Resume Process (Lines 385-431)

**For each run in to_resume**:

1. **Slot Gate** (Lines 388-395): Check active container count
   - Max active projects (config): `max_active_projects` (default if missing)
   - Current containers: `docker ps --format {{.Names}}` filtered for `macaron-app-*` or `proj-*`
   - If active ≥ max: STOP resuming this batch

2. **CPU/RAM Backpressure** (Lines 396-426):
   - Read system load: `psutil.cpu_percent(interval=1)`, `virtual_memory().percent`
   - Thresholds (configurable):
     - `_CPU_GREEN = 40%` → launch freely
     - `_CPU_YELLOW = 65%` → slow down (2× stagger)
     - `_CPU_RED = 80%` → skip launch this cycle
     - `_RAM_RED = 75%` → skip launch

3. **Worker Dispatch** (Lines 437-496):
   - Check if remote workers available (API health check)
   - Compute worker score vs local score
   - Dispatch to worker with highest score (load balancing)
   - If local wins or no workers, launch locally

### Critical Gaps in Auto-Resume

**❌ Gap 1**: 48-hour paused run window
- Runs paused >48h are NEVER resumed
- No manual override option visible
- Long-stalled projects silently ignored

**❌ Gap 2**: 10-minute pending timeout is aggressive
- Runs pending 10+ minutes are force-resumed
- May interfere with normal scheduling delays
- No backoff before force resume

**❌ Gap 3**: Exponential backoff hits ceiling at attempt 5
- After 5 failures, system stops trying
- No escalation to human
- No alert generated (code has try/except that swallows errors)

**❌ Gap 4**: Slot gate prevents new launches
- If max_active_projects hit, NO launches at all
- Even low-resource missions blocked
- No priority queue or preemption

**❌ Gap 5**: CPU/RAM thresholds are fixed, not adaptive
- 80% CPU threshold may be too high for production
- RAM 75% threshold leaves little headroom
- No burst handling

---

## 7. SESSION LIFECYCLE

### Location
`/Users/sylvain/_MACARON-SOFTWARE/platform/workflows/store.py`, lines 1012-1082

### Session States

```
running
    ↓
completed (success)
completed_with_gaps (missing deliverables)
failed (phase timeout or error)
gated (phase rejected/blocked)
paused (manual pause)
escalated (adversarial escalation)
    ↓
interrupted (terminal state in session store)
```

### Transition to Completion (Lines 1012-1060)

**1. Pipeline DoD Check** (Lines 1012-1043):
After all phases complete, check for mandatory deliverables:
- `INCEPTION.md`: Feature inception document
- `Dockerfile`: Container image
- Source code: Any `.vue`, `.js`, `.ts`, `.rs`, `.py`, `.go`, `.html`, `.jsx`, `.tsx`
- Tests: Any file with "test" or "spec" in name

**2. Status Resolution** (Lines 1045-1056):
```python
if run.status == "running":
    run.status = "completed"

# Map workflow outcome to session status
session_status = {
    "completed": "completed",
    "completed_with_gaps": "completed",
    "failed": "failed",
    "gated": "interrupted",
    "paused": "interrupted",
    "escalated": "interrupted",
}.get(run.status, "completed")
```

### What Triggers Completion

**1. All phases complete successfully**:
- No phase returned failure/veto
- No phase exceeded timeout
- DoD check passes

**2. All phases complete (with warnings)**:
- Some phases had issues but gates allowed continuation
- DoD check finds missing deliverables → `completed_with_gaps`
- Example: Missing tests or Dockerfile → pipeline marks as incomplete

**3. Phase Timeout** (Lines 673-858):
- Per-phase timeout (default or override)
- Timeout reached → Error logged → Phase marked failed
- For "critical phases": continue anyway (never stop industrial pipeline)
- Example: 3600s timeout = 1 hour per phase

### RTE Closing Message (Lines 1062-1080)

When workflow completes:
```python
await _rte_facilitate(
    session_id,
    f"[OK] Le workflow {workflow.name} est terminé ({run.status}).\n"
    f"Bilan des phases:\n{phase_summary}\n\n"
    f"Fais la synthèse finale pour l'équipe...",
    to_agent=leader,
    project_id=project_id,
)
```

**RTE facilitates closing summary** (text message, not a gating event).

### Critical Gap: No Explicit Completion Timeout

**❌ Gap**: Session can remain in "running" state indefinitely
- If last phase hangs (network issue, LLM timeout)
- No parent-level timeout to mark session "dead"
- No zombie session cleanup
- Relies on individual phase timeouts (PHASE_TIMEOUT_SECONDS = ??)

### Critical Gap: No Session-Level Timeout

**❌ Gap**: No mention of overall workflow timeout
- Only per-phase timeout visible
- Workflow could stall if phase keeps retrying
- No automatic "mark failed after X hours"

---

## 8. RTE FACILITATION MECHANISM

### Location
`/Users/sylvain/_MACARON-SOFTWARE/platform/workflows/store.py`, lines 201-300

### How _rte_facilitate() Works

**Function Signature**:
```python
async def _rte_facilitate(
    session_id: str,
    prompt: str,
    to_agent: str = "",
    project_id: str = "",
) -> str
```

**Execution Steps**:

1. **Lookup RTE Agent** (Lines 214-226):
   - Query agent store for agent with ID = `"release_train_engineer"`
   - If NOT found: fallback to system message (no LLM call)
   - If found: proceed

2. **Create Execution Context** (Lines 238-243):
   ```python
   ctx = ExecutionContext(
       agent=rte,
       session_id=session_id,
       project_id=project_id,
       tools_enabled=False,  # ← RTE CANNOT USE TOOLS
   )
   ```

3. **Stream Response via SSE** (Lines 246-291):
   - Send "stream_start" event with agent name, pattern type = "workflow"
   - Call LLM: `executor.run_streaming(ctx, prompt)`
   - For each delta (text chunk): accumulate + send "stream_delta" event
   - On completion: send "stream_end" event

4. **Store in Message History** (Lines 293-300):
   - Create MessageDef with from_agent="rte", to_agent=[specified], content=[LLM response]
   - Add to session message store
   - Return accumulated text

### Where _rte_facilitate() Is Called

**Phase Transitions** (15 calls in store.py):

1. **Before phase start** (Line 563):
   - Facilitates briefing/kickoff for phase

2. **Phase gate blocking** (Lines 571, 616, 629):
   - When gate rejects phase entry (e.g., "all_approved" failed)
   - RTE explains why gate blocked

3. **Phase completion** (Lines 714, 722, 732, 759, 812, 846):
   - RTE summarizes phase results

4. **Workflow completion** (Lines 856, 955, 969, 1073):
   - RTE gives final summary + next steps
   - Last call before workflow_run is returned

### Critical Issues with _rte_facilitate()

**❌ Issue 1**: RTE has NO TOOLS
- Cannot verify phase completion itself
- Cannot access workspace to check deliverables
- Cannot trigger actual phase transitions in the system
- Only speaks; system continues based on hard-coded phase loop logic

**❌ Issue 2**: RTE output is TEXT ONLY, not STRUCTURED
- No return of `{phase_id: "next", criteria_met: bool}`
- Phase loop uses RTE text for communication only
- No way for RTE to programmatically advance phases

**❌ Issue 3**: RTE system prompt is VAGUE on phase semantics
- Prompt says "orchestre l'ART" and "PI Planning" etc.
- Does NOT say:
  - "When you see these criteria in prior phases, advance to next"
  - "Generate structured phase transition output"
  - "Validate gate conditions before responding"

**❌ Issue 4**: No Backpressure to RTE from Agents
- If RTE wants to transition to next phase, no way to do so
- Agent output → Guard rejects → Phase retries
- RTE never sees the rejection or learns to adjust facilitation

---

## ROOT CAUSES OF PIPELINE STALLS

### 1. Missing Feedback Loop (Worker → System)
- **Symptom**: Worker gets rejected, repeats same mistake
- **Cause**: Guard returns score, NOT actionable feedback
- **Result**: Infinite retry on same bad pattern

### 2. RTE Powerlessness
- **Symptom**: RTE cannot unblock stalled phases
- **Cause**: No tools, output is text-only
- **Result**: Phase loop ignores RTE facilitation, continues with hard-coded logic

### 3. Product Agent Underspecified
- **Symptom**: Feature-design phase produces vague user stories
- **Cause**: No system prompt, no template, low hierarchy rank
- **Result**: Subsequent phases have unclear requirements

### 4. No Session-Level Timeout
- **Symptom**: Sessions hang in "running" state indefinitely
- **Cause**: Only per-phase timeouts, no workflow timeout
- **Result**: Zombie sessions consume resources, never marked "failed"

### 5. Auto-Resume Ceiling Effects
- **Symptom**: Paused runs >48h never resume; stuck runs stop retrying at attempt 5
- **Cause**: Hard-coded windows and exponential backoff ceiling
- **Result**: Long-stalled projects abandoned silently

### 6. Adversarial Guard Lacks Guidance
- **Symptom**: Quality filtering works (rejects slop) but doesn't teach
- **Cause**: L0 returns score; L1 requires different LLM (not available)
- **Result**: Workers don't learn how to improve

---

## RECOMMENDATIONS FOR FIXES

### 1. Add Feedback Loop
Modify adversarial guard to return structured suggestions:
```json
{
  "score": 7,
  "verdict": "REJECT",
  "issues": ["MOCK: NotImplementedError"],
  "fix_suggestions": [
    "Replace 'raise NotImplementedError' with real implementation",
    "Add at least one unit test for this function"
  ]
}
```

### 2. Empower RTE with Tools
Add tools to RTE context:
- `verify_phase_criteria(phase_id)` → check if criteria met
- `advance_phase(phase_id, reason)` → trigger next phase
- `query_workspace(path)` → list files without full code_read overhead

### 3. Spec Product Agent
Add explicit system prompt:
```
You are the Product Owner. Your role in FEATURE_DESIGN phase:
1. Generate 5-8 user stories in Gherkin format
2. Each story MUST have: "Given", "When", "Then"
3. Write acceptance criteria with measurable acceptance thresholds
4. Assign WSJF scores (1-10 scale)
5. Output MUST be valid JSON: {"stories": [...]}
```

### 4. Add Session Timeout
In workflow engine:
```python
session_timeout_seconds = 28800  # 8 hours
if time.time() - session_start > session_timeout_seconds:
    run.status = "failed"
    reason = "Session exceeded 8-hour timeout"
```

### 5. Extend Auto-Resume Windows
- Paused runs: extend from 48h to 7 days
- Stuck pending: check and resume all (no hard 10-minute threshold)
- Exponential backoff: increase ceiling from attempt 5 to attempt 10

### 6. Add L1 Semantic Check Universally
Ensure L1 always runs (not just when different LLM available):
- Use same LLM with different system prompt (adversarial reviewer mode)
- Or: rotate between available providers
- Or: use smaller, faster semantic model (Qwen, Mistral) for L1 checks

