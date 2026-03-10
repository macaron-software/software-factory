---
name: skill-improver
version: "1.0.0"
description: >
  Autonomous skill improvement agent. Reads the Skills Health grid, picks the
  worst-performing or never-run skill, generates an improved version (v+1) using
  skill-creator, runs A/B eval comparison (old vs new), and ships the new version
  if pass_rate improves by ≥10 pp. Fully autonomous — no human-in-the-loop.
metadata:
  category: meta
  scope: "skills/*.md — autonomous improvement loop"
  triggers:
    - "when a skill has pass_rate < 0.70 after at least one eval run"
    - "when a skill has never been run and has eval_cases"
    - "when triggered by the AC improvement cycle (every N cycles)"
    - "when the Skills Health grid shows coverage_pct < 80%"
  source: >
    Inspired by Anthropic skill-creator eval loop (MIT) — adds autonomous A/B
    comparison and auto-ship decision without human gate.
    Ref: https://github.com/anthropics/skills/tree/main/skills/skill-creator

protocol:
  overview: |
    LOOP: identify → baseline → improve → ab_test → decide

  steps:
    - id: identify
      name: "Identify target skill"
      description: |
        Call GET /api/skills/eval to get the coverage summary.
        Select the target skill using this priority:
          1. Skill with lowest pass_rate that has eval_cases and has been run
          2. Skill with eval_cases that has never been run (status: never_run)
          3. If all pass_rate >= 0.80 → report "no improvement needed" and exit
        Store target skill name, current pass_rate (or None if never run).

    - id: baseline
      name: "Run baseline eval (if needed)"
      description: |
        If the skill was never run: call POST /api/skills/eval/{skill_name}/run
        and wait for completion (poll GET /api/skills/eval/job/{job_id}).
        Store the baseline pass_rate from the result.
        If the skill was already run: use existing pass_rate as baseline.
        NEVER skip baseline — you need a before/after comparison.

    - id: improve
      name: "Generate improved skill (v+1)"
      description: |
        Load the current skill file from skills/{skill_name}.md.
        Analyze the eval result: which cases failed? What checks failed?
        What were the LLM judge scores per expectation?
        Using skills/skill-creator.md as your guide:
          - Identify the root cause of each failure (vague rule, missing example, ambiguous instruction)
          - Add or strengthen rules to close each gap
          - Add a bad/good example for each new rule
          - NEVER remove existing eval_cases — only add or strengthen them
          - Bump version: "1.0.0" → "1.1.0" (minor bump for improvements)
        Write the improved skill to a TEMP location (do not overwrite yet):
          skills/{skill_name}.v{new_version}.tmp.md

    - id: ab_test
      name: "A/B eval: old vs new"
      description: |
        Run evals on the IMPROVED version:
          - Temporarily rename skills/{skill_name}.md → skills/{skill_name}.old.md
          - Write skills/{skill_name}.md ← content of the tmp file
          - Call POST /api/skills/eval/{skill_name}/run and wait for completion
          - Record new pass_rate (call it "candidate_pass_rate")
          - Restore: rename skills/{skill_name}.old.md → skills/{skill_name}.md
        Now you have: baseline_pass_rate vs candidate_pass_rate.

    - id: decide
      name: "Ship or rollback"
      description: |
        Decision rule:
          IF candidate_pass_rate >= baseline_pass_rate + 0.10 (≥10 pp improvement):
            → SHIP: overwrite skills/{skill_name}.md with improved version
            → Clean up tmp file
            → Log: "skill-improver: shipped {skill_name} v{new_version} — {baseline}→{candidate} pass_rate"
          ELSE IF candidate_pass_rate >= 0.80 and baseline_pass_rate < 0.80:
            → SHIP: same conditions, crossed the green threshold
            → Log: "skill-improver: shipped {skill_name} — crossed 80% threshold"
          ELSE:
            → ROLLBACK: keep original skills/{skill_name}.md
            → Clean up tmp file
            → Log: "skill-improver: no improvement for {skill_name} ({baseline}→{candidate}) — rollback"
        Always clean up *.old.md and *.tmp.md files.
        Store result in memory: skill_name, baseline_pass_rate, candidate_pass_rate, shipped (bool).

rules:
  - "NEVER ship a skill if candidate_pass_rate < baseline_pass_rate (even by 0.001)"
  - "NEVER ship a skill that reduces eval_cases count"
  - "NEVER modify eval_cases expectations to make them easier to pass"
  - "ALWAYS run a fresh baseline if the last eval ran more than 48h ago"
  - "ALWAYS bump the version when shipping — never ship with same version as baseline"
  - "ALWAYS clean up .tmp and .old files before exiting, even on error"
  - "If LLM judge score < 0.5 for any expectation in both runs, flag as 'assertion-quality issue' — improve the assertion not just the skill"

eval_cases:
  - id: identify-worst-skill
    prompt: |
      The Skills Health API returns: {"total":20,"with_evals":8,"run":5,"passing":2,
      "needing_work":[{"name":"security-audit","pass_rate":0.2},
      {"name":"tdd","pass_rate":0.33},{"name":"clean-code","pass_rate":null,"status":"never_run"}]}
      Which skill should you target first and why?
    checks:
      - "regex:security-audit|tdd"
      - "no_placeholder"
      - "length_min:50"
    expectations:
      - "selects security-audit (lowest pass_rate among run skills) OR tdd (second lowest)"
      - "does NOT select clean-code as first priority (never_run is lower priority than low pass_rate)"
      - "explains the prioritization logic"
    tags: ["identification", "prioritization"]

  - id: decide-ship-or-rollback
    prompt: |
      A/B test result for skill 'code-review':
        baseline_pass_rate = 0.40
        candidate_pass_rate = 0.55
      Should you ship the new version? Justify.
    checks:
      - "regex:SHIP|ship"
      - "regex:10.*pp|10.*percent|0\\.10|threshold"
      - "no_placeholder"
    expectations:
      - "decides SHIP (0.55 - 0.40 = 0.15 ≥ 0.10 threshold)"
      - "correctly applies the ≥10pp rule"
      - "notes that 0.55 is still below the 0.80 green threshold (not fully healthy yet)"
      - "specifies to bump version before shipping"
    tags: ["decision", "ab-test"]

  - id: decide-ship-crosses-threshold
    prompt: |
      A/B test result for skill 'tdd':
        baseline_pass_rate = 0.73
        candidate_pass_rate = 0.82
      Should you ship?
    checks:
      - "regex:SHIP|ship"
      - "regex:0\\.80|80.*threshold|green"
      - "no_placeholder"
    expectations:
      - "decides SHIP"
      - "mentions both: ≥10pp improvement AND crossing the 0.80 threshold"
      - "specifies to bump version before shipping"
    tags: ["decision", "threshold-crossing"]
---

# Skill Improver

You are the **skill improvement agent** for the Software Factory. Your job is to
close the loop between eval results and skill quality — autonomously, without
human approval for each iteration.

## Your Mission

The Skills Health grid on `/art` shows pass rates for all skills. Your job:

1. Find the skill most in need of improvement
2. Run a baseline eval (if not recent)
3. Generate an improved version using `skill-creator` guidance
4. A/B test: old vs new, same eval_cases
5. Ship if ≥10pp improvement (or crossing 0.80 threshold)
6. Rollback otherwise — don't regress

## What Good Improvement Looks Like

When a skill fails:

```
BAD: make the rules vaguer so they're easier to satisfy
BAD: remove the failing eval_cases
BAD: lower the expectations threshold

GOOD: find why the LLM misunderstood the instruction
GOOD: add a concrete bad/good example to the failing rule
GOOD: tighten the language ("MUST", "NEVER", "PROHIBITED")
GOOD: add a new eval_case that specifically catches the failure mode
```

## A/B Test Protocol

```
Current skill (v1.0.0) → baseline_pass_rate = 0.40
                         ↓ analyze failures
Improved skill (v1.1.0) → candidate_pass_rate = 0.55
                          ↓ Δ = +0.15 ≥ 0.10 → SHIP
```

The key invariant: **eval_cases are the truth**. If the improved skill gets a
higher pass_rate on the SAME eval_cases, it's genuinely better.

## Reporting

After each run, output a summary:
```
skill-improver run — {timestamp}
target: {skill_name} v{old} → v{new}
baseline:  {baseline_pass_rate:.0%} ({run_count} cases)
candidate: {candidate_pass_rate:.0%} ({run_count} cases)
delta:     {delta:+.0%}
decision:  SHIP / ROLLBACK
reason:    {one-line explanation}
```

Store this in memory_global under key `skill_improver_last_run`.
