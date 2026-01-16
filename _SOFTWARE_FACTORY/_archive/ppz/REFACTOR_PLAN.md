# Plan de Refactoring RLM Chain

## Problème Actuel

La chaîne RLM ne fonctionne PAS selon les spécifications:
- Brain n'utilise PAS de vrais LLM (juste grep/subprocess)
- Wiggum fait RED mais PAS GREEN (active tests sans implémenter)
- Pas de MCP tools
- Pas de LEAN filtering
- Pas de swarm/fractal fonctionnel

## Priorités de Correction

### P0 - CRITIQUE (à faire immédiatement)

#### 1. Brain: Vrai LLM avec MCP

```python
# ACTUEL (BROKEN):
class SubAgent:
    async def analyze(self):
        result = subprocess.run(cmd, ...)  # Just grep!

# CORRIGÉ:
async def analyze_with_llm(domain: str, files: List[str]) -> List[Dict]:
    """Use real LLM via opencode with MCP tools"""
    prompt = f"""
    Analyze {domain} files for issues.
    Use Read tool to examine files.
    Return JSON array of findings.
    """
    result = subprocess.run([
        "opencode", "run",
        "--model", "qwen3-30b-a3b",
        "--tools", "read,write,bash",
        prompt
    ], capture_output=True, text=True)
    return json.loads(result.stdout)
```

#### 2. Wiggum: Vrai TDD (RED → GREEN → VERIFY)

```python
# ACTUEL (BROKEN):
async def process_task(task):
    # Just calls opencode once and marks complete
    subprocess.run(["opencode", "run", prompt])
    task["status"] = "completed"  # Without verification!

# CORRIGÉ:
async def process_task_tdd(task):
    # Phase RED: Write failing test
    red_prompt = f"""
    Write a test that FAILS for this issue:
    {task['description']}

    File: {task['files'][0]}

    The test MUST FAIL initially. Use test() not test.skip().
    """
    red_result = await run_opencode(red_prompt, tools=["read", "write"])

    # Verify RED: Test must fail
    test_result = await run_test(task['files'][0])
    if test_result.passed:
        return {"status": "failed", "reason": "RED phase: test should fail but passed"}

    # Phase GREEN: Implement fix
    green_prompt = f"""
    Implement the code to make this test PASS:
    {task['description']}

    Test file: {task['test_file']}
    Source file: {task['files'][0]}
    """
    green_result = await run_opencode(green_prompt, tools=["read", "write"])

    # Phase VERIFY: Test must pass
    test_result = await run_test(task['files'][0])
    if not test_result.passed:
        return {"status": "failed", "reason": "GREEN phase: test still fails"}

    return {"status": "completed"}
```

#### 3. Brain: LEAN Filtering avec Vision

```python
# ACTUEL (BROKEN):
def _calculate_wsjf(self, task):
    bv = task.get("business_value", 5)  # INVENTED!

# CORRIGÉ:
async def calculate_wsjf_with_vision(task, vision_doc: str) -> float:
    """Use LLM to assess business value against vision"""
    prompt = f"""
    Given this product vision:
    {vision_doc}

    And this task:
    {task['description']}

    Rate (1-10):
    - Business Value: How much does this help users?
    - Time Criticality: Is this urgent?
    - Risk Reduction: Does this reduce technical debt/risk?
    - Job Size: Effort estimate

    Return JSON: {{"bv": N, "tc": N, "rr": N, "size": N}}
    """
    result = await run_opencode(prompt)
    scores = json.loads(result)
    return (scores["bv"] + scores["tc"] + scores["rr"]) / scores["size"]
```

### P1 - IMPORTANT

#### 4. Multi-projet Configuration

```python
# Nouveau fichier: project_config.py

from pathlib import Path
from dataclasses import dataclass

@dataclass
class ProjectConfig:
    name: str
    root_path: Path
    domains: dict
    vision_doc: str
    backlog_path: Path

# Usage:
PROJECTS = {
    "popinz": ProjectConfig(
        name="popinz",
        root_path=Path("/Users/sylvain/_POPINZ/popinz-dev"),
        domains=PROJECT_DOMAINS,
        vision_doc="CLAUDE.md",
        backlog_path=Path("rlm/backlog_tasks.json"),
    ),
    "autre-projet": ProjectConfig(
        name="autre-projet",
        root_path=Path("/Users/sylvain/_AUTRE/projet"),
        domains={...},
        vision_doc="README.md",
        backlog_path=Path("backlog.json"),
    ),
}
```

#### 5. Adversarial Deep Mode Verification

```python
# Vérifier que le mode deep fonctionne vraiment
async def check_code_deep(code: str, file_type: str) -> Dict:
    prompt = f"""
    Analyze this {file_type} code for issues:

    ```{file_type}
    {code}
    ```

    Check for:
    - SLOP: Code that looks good but doesn't work
    - BYPASS: Hidden workarounds
    - INCOMPLETE: Missing logic
    - SECURITY: Vulnerabilities

    Return JSON: {{"approved": bool, "score": 0-10, "issues": [...]}}
    """
    result = subprocess.run([
        "opencode", "run",
        "--model", "qwen3-30b-a3b",
        prompt
    ], capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout)
```

### P2 - NICE TO HAVE

#### 6. Fractal Decomposition

```python
async def fractal_decompose(task) -> List[Dict]:
    """Decompose large task into subtasks"""
    if task["complexity"] < 5 and task["file_count"] < 3:
        return [task]  # Small enough, no decomposition

    prompt = f"""
    Decompose this large task into atomic subtasks:

    Task: {task['description']}
    Files: {task['files']}

    Rules:
    - Each subtask: 1 file, 1 concern
    - Max 400 LOC per subtask
    - Include test for each subtask

    Return JSON array of subtasks with: id, description, files, test_file
    """
    result = await run_opencode(prompt)
    subtasks = json.loads(result)
    return subtasks
```

#### 7. TMC Integration (k6)

```bash
# tmc/perf-smoke.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 10,
  duration: '1m',
  thresholds: {
    http_req_duration: ['p95<500'],
  },
};

export default function () {
  const res = http.get('https://staging.popi.nz/health');
  check(res, { 'status is 200': (r) => r.status === 200 });
}
```

## Fichiers à Modifier

| Fichier | Changement | Priorité |
|---------|------------|----------|
| `rlm_brain.py` | Remplacer SubAgent par vrais LLM calls | P0 |
| `wiggum_tdd.py` | Ajouter vraies phases RED/GREEN/VERIFY | P0 |
| `adversarial.py` | Vérifier/fixer mode deep | P1 |
| `project_config.py` | Nouveau - config multi-projet | P1 |
| `wiggum_orchestrator.py` | Intégrer fractal | P2 |
| `tmc.py` | Intégrer k6 | P2 |

## Validation

Après refactoring, le pipeline doit:

1. **Brain scan** → Génère tâches avec VRAI business value (LLM assessment)
2. **Wiggum TDD** → Chaque tâche:
   - ✅ Test écrit ET test ÉCHOUE (RED)
   - ✅ Code implémenté (GREEN)
   - ✅ Test PASSE (VERIFY)
3. **Adversarial** → Code vérifié (fast + deep)
4. **Deploy** → Staging → Prod avec E2E

## Commandes de Test

```bash
# Test Brain avec vrai LLM
python3 rlm_brain.py --domain rust --quick

# Test Wiggum TDD sur une tâche
python3 wiggum_tdd.py --once --task test-task-001

# Vérifier que le test a bien été écrit ET qu'il passe
grep -r "test(" popinz-tests/e2e/ | head -5
npx playwright test --grep "test-task-001"
```

## Estimation Effort

| Tâche | Durée estimée |
|-------|---------------|
| P0 - Brain LLM | 2-3h |
| P0 - Wiggum TDD | 2-3h |
| P0 - Tests validation | 1h |
| P1 - Multi-projet | 1-2h |
| P1 - Adversarial deep | 30min |
| P2 - Fractal | 1-2h |
| P2 - TMC | 2h |
| **TOTAL** | ~10-15h |
