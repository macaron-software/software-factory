---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/advanced-evaluation
# WHY: Our skill-grader and eval framework use LLM-as-judge. This skill gives
#      agents the research-backed patterns for building reliable eval systems:
#      direct scoring vs pairwise, bias mitigation, metric selection.
name: advanced-evaluation
version: "1.0.0"
description: >
  Production-grade LLM evaluation patterns: LLM-as-judge, direct scoring,
  pairwise comparison, bias mitigation, and eval pipeline design.
  Use when building eval rubrics, comparing model outputs, implementing
  automated quality assessment, or designing A/B tests for prompts.
metadata:
  category: ai
  triggers:
    - "when implementing LLM-as-judge"
    - "when comparing model outputs"
    - "when creating evaluation rubrics"
    - "when eval results are inconsistent or biased"
    - "when designing automated quality assessment"
    - "when building eval pipelines for agent skills"
# EVAL CASES
eval_cases:
  - id: choose-eval-method
    prompt: |
      We need to evaluate whether our customer support agent provides
      empathetic, helpful responses. Two approaches: (A) score each response
      1-5, or (B) compare pairs of responses and pick the better one.
      Which is better and why?
    should_trigger: true
    checks:
      - "regex:pairwise|direct.*scor|pair.*compar|subjective|prefer|relative|MT.?Bench|agreement"
      - "regex:tone|empathy|style|preference.*subjective|human.*judge"
      - "length_min:80"
    expectations:
      - "recommends pairwise comparison for subjective criteria like empathy/tone"
      - "explains: pairwise achieves higher agreement with human judges for preference-based evaluation"
      - "notes direct scoring better for objective criteria with clear ground truth"
    tags: [pairwise, direct-scoring, methodology]

  - id: bias-mitigation
    prompt: |
      Our LLM judge consistently rates longer responses higher even when
      they're just verbose. How do we fix this?
    should_trigger: true
    checks:
      - "regex:length.*bias|verbosity.*bias|explicit.*prompt|penaliz.*length|length.?normaliz|rubric"
      - "regex:mitigat|fix|address|criterion|relevant|unnecessar"
      - "length_min:80"
    expectations:
      - "identifies length bias as a known LLM judge failure mode"
      - "recommends: explicit prompt instruction to ignore length, criteria-specific rubrics"
      - "may suggest length-normalized scoring or penalizing irrelevant verbosity"
    tags: [bias, length-bias, mitigation]

  - id: eval-rubric-design
    prompt: |
      Design an evaluation rubric for a code review agent that should:
      identify bugs, suggest improvements, and avoid hallucinating issues.
    should_trigger: true
    checks:
      - "regex:rubric|criterion|dimension|score|weight|scale|0.*10|1.*5|pass.*fail"
      - "regex:precision|recall|false.*positive|hallucin|actual.*issue|fabricat"
      - "length_min:100"
    expectations:
      - "proposes a multi-dimensional rubric: bug detection, quality of suggestions, hallucination rate"
      - "includes both positive criteria (finds real bugs) and negative criteria (doesn't invent issues)"
      - "suggests concrete scoring scale with definitions"
    tags: [rubric, code-review-eval, multi-dimensional]
---

# Advanced Evaluation — LLM-as-Judge Patterns

Production-grade techniques for evaluating LLM outputs reliably.

**Key insight**: LLM-as-Judge is a family of approaches. Choosing the right one
and mitigating biases is the core competency.

## Evaluation Taxonomy

### Direct Scoring
One LLM rates one response on a defined scale.

```
Input → LLM Response → Judge → Score (e.g., 1-5 or 0-1)
```

**Best for**: Objective criteria (factual accuracy, instruction following, format compliance)
**Failure mode**: Scale drift, inconsistent interpretation across runs

### Pairwise Comparison
An LLM compares two responses and picks the better one.

```
Input → [Response A, Response B] → Judge → "A is better because..."
```

**Best for**: Subjective preferences (tone, style, empathy, persuasiveness)
**Failure mode**: Position bias (first response rated higher)

**Research** (MT-Bench, Zheng et al. 2023): Pairwise achieves higher agreement
with human judges for preference-based evaluation.

---

## Known Biases & Mitigations

| Bias | Description | Mitigation |
|------|-------------|------------|
| **Position bias** | First response rated higher in pairwise | Evaluate twice with swapped order, take majority |
| **Length bias** | Longer = better, regardless of quality | Explicit prompt: "ignore length", length-normalized scoring |
| **Verbosity bias** | Detailed explanations rated higher even if irrelevant | Criteria-specific rubrics penalizing irrelevant detail |
| **Self-enhancement** | Model rates its own outputs higher | Use different model for generation vs evaluation |
| **Authority bias** | Confident tone rated higher regardless of accuracy | Require citation/evidence, add fact-check layer |

---

## Metric Selection

| Task Type | Primary Metric | Secondary |
|-----------|----------------|-----------|
| Binary pass/fail | Precision, Recall, F1 | Cohen's κ |
| Ordinal scale (1-5) | Spearman's ρ, Kendall's τ | Weighted κ |
| Pairwise preference | Agreement rate, Position consistency | Confidence |
| Multi-label | Macro-F1, Micro-F1 | Per-label P/R |

**Critical insight**: Systematic disagreement patterns matter more than absolute agreement.
A judge that always disagrees on security issues is worse than one with random noise.

---

## Rubric Design Patterns

### Good Rubric Structure

```markdown
Dimension: Bug Detection
Weight: 40%
Scale: 0-3
  0 = Misses obvious bugs or hallucinates non-existent bugs
  1 = Finds some bugs but misses critical ones
  2 = Finds most bugs with minor misses
  3 = Finds all real bugs, zero hallucinated issues

Dimension: Suggestion Quality
Weight: 40%
...

Dimension: Hallucination Rate
Weight: 20%
  0 = Multiple invented issues
  1 = One invented issue
  2 = No invented issues
```

### Anti-patterns to Avoid

- `length_min:N` alone — trivially satisfied by any long response
- `regex:PASS|pass` alone — satisfied by any mention of the word
- `not_regex:X` where X appears in valid explanatory text

---

## Our SF Eval Framework

SF uses:
- `checks_pass_rate`: regex/not_regex/length_min/no_placeholder checks (70% weight)
- `llm_judge_score`: LLM-as-judge with rubric (30% weight)
- Case passes if `0.7*checks + 0.3*judge >= 0.80`
- Skill passes if `≥80%` of cases pass

Results saved to `data/skill_evals/{skill}.json` + history JSONL per run.
