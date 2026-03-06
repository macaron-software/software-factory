---
name: skill-creator
version: "1.1.0"
description: >
  Creates and improves SF agent skills. Follows a draft → eval → grade → iterate
  quality loop: write the skill, define eval_cases, run them via skill-eval workflow,
  grade with skill-grader, and refine. Every new skill gets eval_cases.
metadata:
  category: meta
  scope: "SF platform skills (skills/*.md)"
  triggers:
    - "when creating a new skill"
    - "when a user asks to add agent capability"
    - "when improving or updating an existing skill"
    - "when a skill produces poor or inconsistent outputs"
  source: >
    Anthropic skill-creator pattern (MIT) — adapted for SF YAML/markdown format.
    Ref: https://github.com/anthropics/skills/tree/main/skills/skill-creator
    Adaptations: no .skill packaging, no claude -p CLI, eval_cases embedded in
    frontmatter (not evals.json), grading via skill-grader skill,
    loop via skill-eval workflow (platform/workflows/definitions/skill-eval.yaml).
eval_cases:
  - id: create-basic-skill
    prompt: "Create a skill for generating database migration scripts"
    checks:
      - "regex:name:|version:|eval_cases:|triggers:"
      - "length_min:200"
      - "no_placeholder"
    expectations:
      - "skill has valid YAML frontmatter with name, version, description"
      - "frontmatter includes metadata.triggers with 3+ entries"
      - "frontmatter includes eval_cases with 2+ test cases"
      - "skill body defines concrete rules not vague guidelines"
      - "at least one rule has a bad/good example"
    tags: ["basic", "creation"]
  - id: improve-existing-skill
    prompt: "The tdd skill produces test stubs without assertions — write the complete improved skill .md file"
    checks:
      - "regex:NEVER|MUST|PROHIBITED|assertion|version:"
      - "length_min:200"
      - "no_placeholder"
    expectations:
      - "outputs a complete .md skill file with YAML frontmatter (name/version/eval_cases)"
      - "adds explicit prohibition against stubs using NEVER or MUST keyword"
      - "increments version in the frontmatter (e.g. 1.0.0 → 1.1.0)"
      - "adds at least one eval_case targeting the stub anti-pattern"
    tags: ["improvement", "anti-slop"]
  - id: weak-assertion-detection
    prompt: "Write eval_cases for a skill that formats JSON output"
    checks:
      - "not_regex:output is non-empty|output exists"
      - "regex:key|field|schema|structure|specific|format"
      - "length_min:100"
      - "no_placeholder"
    expectations:
      - "does NOT include 'output is non-empty' as an expectation"
      - "does NOT include 'output exists' as an expectation"
      - "expectations reference specific JSON keys or structure"
    tags: ["meta-eval", "assertion-quality"]
---

# Skill Creator

Creates and evolves SF agent skills via the eval loop:
**Draft → Eval Cases → Execute → Grade → Iterate**.

Source: Anthropic skill-creator (MIT) — adapted for SF.

---

## STEP 1 — Understand the Skill

Before writing, answer:
- **What task does this skill guide?** (concrete, not abstract)
- **What triggers it?** (which LLM tasks, keywords, contexts)
- **What failure modes should it prevent?** (slop, fake data, bad patterns)
- **Who are the consumers?** (which agents, which workflows)

---

## STEP 2 — Write the Skill

### Frontmatter schema

```yaml
name: my-skill
version: "1.0.0"
description: >
  One clear sentence. What the skill does, when to use it.
metadata:
  category: dev | ux | security | ops | meta
  scope: "target files / languages / contexts"
  triggers:
    - "when doing X"
    - "when the task involves Y"
    - "always for Z type of output"
  source: "origin if ported/inspired from external"  # optional
eval_cases:
  - id: happy-path
    prompt: "Ask that triggers the skill naturally"
    expectations:
      - "output contains X"
      - "output does NOT contain Y"
      - "format matches Z"
    tags: ["basic"]
  - id: anti-pattern
    prompt: "Input likely to produce the wrong output"
    expectations:
      - "skill prevents the anti-pattern"
      - "output follows rule X instead"
    tags: ["edge", "anti-pattern"]
```

### Skill body rules

- **Rules, not guidelines** — "NEVER do X" beats "try to avoid X"
- **Concrete bad/good examples** for each rule
- **Explicit rejection criteria** — what output should trigger a retry
- **No meta-commentary** — the skill is read by an LLM agent, not a human
- **Short sections** — max 10 rules, each ≤5 lines

---

## STEP 3 — Write Eval Cases

For each skill, define at minimum:
1. **Happy path** — typical trigger, verifiable output
2. **Anti-pattern case** — input likely to produce the wrong output
3. **Edge case** — boundary condition, ambiguous input (optional but recommended)

### Good expectations (specific, verifiable, discriminating)

| Good | Bad |
|---|---|
| "output contains a SQL injection warning at line 42" | "output identifies a security issue" |
| "migration file starts with `-- Migration:` header" | "migration file is correct" |
| "all 3 required fields are populated with non-empty values" | "fields are populated" |
| "output does NOT contain `TODO` or `pass`" | "output has no stubs" |

An expectation is **discriminating** when:
- A correct output passes it
- An incorrect output fails it
- A trivially empty or placeholder output fails it

An expectation is **trivially satisfied** (don't write these) when:
- Any non-empty output passes it (`output is non-empty`, `response exists`)
- A stub or placeholder passes it (`output mentions the topic`)

---

## OUTPUT RULE — ALWAYS OUTPUT THE COMPLETE FILE

**NEVER** describe changes or list what to fix. **ALWAYS** output the complete `.md` file.

| Mode | WRONG ❌ | RIGHT ✓ |
|---|---|---|
| Creating | "Here's how I'd structure a skill for X..." | Full `---\nname: x\n...---\n# X\n...` |
| Improving | "Add a NEVER rule and bump version to 1.1.0" | Complete improved `.md` with the rule already applied |

When improving a skill you don't have access to: **infer a plausible minimal version** then apply the fix. The output must be a real, runnable `.md` skill file.

---

## STEP 4 — Grade and Iterate

1. Run `skill-eval` workflow with your skill
2. Review `grading.json` — check PASS/FAIL + evidence
3. Read `eval_feedback.suggestions` — grader flags weak assertions
4. Fix failing cases OR tighten assertions if they were wrong
5. Repeat until all eval_cases pass
6. Bump `version` (semver: breaking→major, rule change→minor, typo/fix→patch)

---

## STEP 5 — Commit

```bash
git commit -m "feat(skills): add <name> skill v1.0.0

- triggers: <list main triggers>
- eval_cases: N test cases
- source: <if applicable>

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Quality Checklist

Before shipping:
- [ ] YAML frontmatter parses without error
- [ ] `eval_cases` has ≥2 test cases
- [ ] Each expectation is specific and verifiable (not trivially satisfied)
- [ ] Skill body has ≥3 rules with at least one concrete bad/good example
- [ ] Version bumped if updating existing skill
- [ ] No meta-commentary in skill body
