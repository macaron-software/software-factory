---
name: skill-grader
version: "1.1.0"
description: >
  Grades skill eval outputs against their assertions. Evaluates each expectation
  as PASS/FAIL with cited evidence. Also critiques the assertions themselves
  when they are weak or trivially satisfied. Used in the skill-eval workflow.
metadata:
  category: meta
  scope: "skill-eval workflow — produces grading.json"
  triggers:
    - "when grading skill eval outputs"
    - "when evaluating whether a skill worked correctly"
    - "when running the skill-eval workflow grade phase"
  source: >
    Anthropic grader.md (MIT) — ported to SF skill format.
    Ref: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/grader.md
    Adaptations: no subagent transcript file, inline JSON output, integrated with
    adversarial.py philosophy (superficial compliance = FAIL, same as mock/stub detection).
eval_cases:
  - id: grade-passing-output
    prompt: "Grade: expectation='identifies at least one SQL injection'. Output='Found SQL injection at line 42: user input not sanitized before DB query — use parameterized queries.'"
    checks:
      - "regex:PASS|pass"
      - "regex:SQL inject|line 42|sanitiz|parameteriz|evidence|found|cited|quote"
      - "no_placeholder"
    expectations:
      - "verdict is PASS"
      - "evidence quotes specific text from the output (line 42, SQL injection, parameterized)"
    tags: ["basic", "pass-case"]
  - id: grade-superficial-compliance
    prompt: "Grade: expectation='generates a migration script'. Output='I will generate the migration script now. The script should handle all edge cases.'"
    checks:
      - "regex:FAIL|fail"
      - "regex:promise|promis|claims|will.*not|description|no.*actual|superficial|never.*deliver|intend|plan"
      - "no_placeholder"
    expectations:
      - "verdict is FAIL"
      - "reason mentions promise without delivery or superficial compliance"
    tags: ["edge", "superficial-compliance"]
  - id: critique-trivial-assertion
    prompt: "Grade assertion 'output is non-empty' against output 'x'"
    checks:
      - "regex:PASS|trivial|weak|non-empty|assertion|specific"
      - "length_min:50"
      - "regex:suggest|replac|stronger|specific|better|improv|instead"
    expectations:
      - "grades PASS (technically satisfied)"
      - "eval_feedback flags this assertion as trivially satisfied"
      - "suggests a more specific replacement assertion"
    tags: ["meta-grader", "assertion-critique"]
---

# Skill Grader

Grades skill eval outputs against `eval_cases` expectations.
Produces `grading.json`.

Source: Anthropic grader.md (MIT) — adapted for SF.

---

## Your Two Roles

1. **Grade outputs** — PASS/FAIL each expectation with cited evidence
2. **Critique assertions** — flag weak ones that create false confidence

> "A passing grade on a weak assertion is worse than useless — it creates false confidence."
> — Anthropic grader.md

---

## Grading Process

### Step 1 — Read the Eval Case

From the skill's `eval_cases`:
- `prompt` — what was asked of the agent
- `expectations` — list of assertions to evaluate
- The actual output produced by the agent running with this skill

### Step 2 — Grade Each Expectation

**PASS when:**
- Clear evidence exists in the output
- Evidence reflects genuine task completion (not surface compliance)
- A file has correct CONTENT, not just a correct filename
- The output actually does the thing, not just describes it

**FAIL when:**
- No evidence found in the output
- Output contradicts the expectation
- Output satisfies the assertion by coincidence
- Output describes what it *will do* instead of *doing it*
- Output is a stub, placeholder, or TODO (ALWAYS FAIL — same as adversarial.py mock detection)

### Step 3 — Extract Implicit Claims

Beyond listed expectations, extract claims the output makes:
- **Factual** ("the form has 12 fields") → verify against output
- **Process** ("used pytest") → verify in the output trace
- **Quality** ("all fields correct") → evaluate with evidence

Flag each as `verified: true/false` with evidence.

### Step 4 — Critique the Assertions

After grading, consider — only flag clear, actionable gaps:
- Would a clearly wrong output ALSO pass this assertion? → Flag as trivially satisfied
- Is there an important outcome with no assertion covering it? → Flag as missing coverage
- Is the assertion unverifiable from available information? → Flag as unverifiable

High bar: only flag things the eval author would say "good catch" about.
Do not nitpick every assertion.

---

## Output Format

Produce `grading.json`:

```json
{
  "skill": "skill-name",
  "eval_case_id": "case-id",
  "expectations": [
    {
      "text": "the assertion text",
      "passed": true,
      "evidence": "exact quote or specific description"
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "claims": [
    {
      "claim": "the claim text",
      "type": "factual|process|quality",
      "verified": true,
      "evidence": "supporting or contradicting evidence"
    }
  ],
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "optional — which assertion this relates to",
        "reason": "why it is weak or what coverage is missing"
      }
    ],
    "overall": "brief assessment, or 'No suggestions — evals look solid'"
  }
}
```

---

## Superficial Compliance (Critical)

These outputs ALWAYS fail, regardless of assertion wording:

| Output type | Why it fails |
|---|---|
| "I will now generate X..." | Promise without delivery |
| "The output would look like: ..." | Description instead of output |
| Empty file / `# TODO` / `pass` / `...` | Stub — same as adversarial.py L0 |
| Correct filename, empty or wrong content | Surface compliance |
| Guessed output without actual analysis | Not grounded in the task |

This mirrors `adversarial.py` L0 mock/stub detection applied to skill evaluation context.

---

## Assertion Quality Reference

| Quality | Example | Why |
|---|---|---|
| **Bad** | "output is non-empty" | Trivially satisfied by 'x' |
| **Bad** | "mentions the topic" | Satisfied by any response |
| **Weak** | "contains a migration file" | File might be empty |
| **Good** | "migration file has CREATE TABLE statement" | Specific and verifiable |
| **Good** | "output does NOT contain TODO or pass" | Discriminating against stubs |
| **Good** | "all 3 required fields populated with non-empty values" | Quantity + quality |
