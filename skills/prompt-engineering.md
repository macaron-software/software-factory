---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/prompt-engineering
# WHY: Our Prompt Engineer and LLM Ops agents need concrete techniques for
#      improving system prompts, few-shot learning, CoT, and template design.
name: prompt-engineering
version: "1.0.0"
description: >
  Expert prompt engineering patterns: few-shot learning, chain-of-thought,
  system prompt design, template systems, and optimization techniques.
  Use when improving agent system prompts, debugging agent behavior,
  or designing eval rubrics for LLM outputs.
metadata:
  category: ai
  triggers:
    - "when improving or designing a system prompt"
    - "when an agent produces inconsistent or wrong outputs"
    - "when adding few-shot examples to a prompt"
    - "when implementing chain-of-thought reasoning"
    - "when creating a prompt template system"
    - "when debugging why an agent ignores instructions"
# EVAL CASES
eval_cases:
  - id: improve-weak-prompt
    prompt: |
      This agent system prompt is producing inconsistent code reviews:
      "You are a code reviewer. Review the code."
      Improve it.
    should_trigger: true
    checks:
      - "regex:role|persona|format|output.*format|few.?shot|example|chain|step|criteria"
      - "regex:specif|explicit|structur|consistent|dimension|check"
      - "length_min:80"
    expectations:
      - "identifies the prompt as too vague: no criteria, no format, no examples"
      - "recommends adding: explicit role, review dimensions, output format, examples"
      - "provides an improved version with structured output and at least one criterion"
    tags: [system-prompt, improvement]

  - id: chain-of-thought
    prompt: |
      The agent often gives wrong severity scores for security vulnerabilities.
      It just outputs a number without reasoning. How to fix?
    should_trigger: true
    checks:
      - "regex:chain.*thought|step.*step|reason.*before|think.*step|let.*think|CoT|intermediate"
      - "regex:scratchpad|reasoning|explain.*before|criteria.*first"
      - "length_min:80"
    expectations:
      - "recommends chain-of-thought: force agent to reason step by step before scoring"
      - "suggests adding 'Think step by step' or structured reasoning steps"
      - "may suggest few-shot examples showing reasoning traces"
    tags: [chain-of-thought, scoring, reasoning]

  - id: few-shot-examples
    prompt: |
      Our classification agent miscategorizes edge cases. We need it to be more
      consistent on subtle cases like 'urgent but not critical'.
    should_trigger: true
    checks:
      - "regex:few.?shot|example|demonstrate|show.*case|input.*output|pair"
      - "regex:edge.*case|subtle|border|consistent|anchor"
      - "length_min:80"
    expectations:
      - "recommends few-shot examples: 2-5 input/output pairs demonstrating edge cases"
      - "explains that examples teach better than rules for ambiguous cases"
      - "suggests including the specific 'urgent but not critical' case as an example"
    tags: [few-shot, classification, edge-cases]
---

# Prompt Engineering Patterns

Advanced techniques to maximize LLM **reliability, consistency, and controllability**.

## Core Techniques

### 1. Few-Shot Learning

Teach by example, not rules. Include 2–5 input/output pairs that demonstrate desired behavior.

```markdown
Classify support ticket severity:

Input: "My login doesn't work, error 403, can't access anything"
Output: {"severity": "high", "category": "auth", "escalate": true}

Input: "Feature request: add dark mode to settings"
Output: {"severity": "low", "category": "feature", "escalate": false}

Now classify: "Payment fails for 30% of users since this morning"
```

**Rule**: More examples = more accuracy, but costs tokens. Use 2-3 for simple patterns, 5+ for complex/ambiguous ones.

### 2. Chain-of-Thought (CoT)

Force step-by-step reasoning before the final answer. Improves accuracy 30-50% on analytical tasks.

```markdown
Analyze this bug. Think step by step:
1. What is the expected behavior?
2. What is the actual behavior?
3. What changed recently?
4. What is the most likely root cause?

Bug: "Users can't save drafts after cache update deployed yesterday"
```

**Zero-shot CoT**: Just add "Let's think step by step" — surprisingly effective.

### 3. System Prompt Design

Set stable global behavior that persists across turns. Free up user messages for variable content.

```markdown
You are a Senior Backend Engineer specializing in Python/FastAPI.

Rules:
- Always consider performance and scalability
- Flag security issues immediately with [SECURITY] prefix
- Use early return pattern for guard clauses
- Never suggest .unwrap() — handle errors explicitly

Output format:
1. Assessment (2-3 sentences)
2. Issues found (list with severity)
3. Recommendations (numbered)
4. Code example (if applicable)
```

**Key**: Be explicit about **role**, **rules**, and **output format**. Vague prompts produce vague outputs.

### 4. Template Systems

Build reusable prompt structures with variables:

```python
REVIEW_TEMPLATE = """
Review this {language} code for {focus_area}.

Code:
{code_block}

Checklist:
{checklist}

Output format: {output_format}
"""
```

### 5. Structured Output

Force consistent formats via output specification:
- Specify JSON schema explicitly in the prompt
- Use `json_object` mode when supported
- Include a complete example of the expected output
- For classification: give the exact set of valid values

---

## Common Failure Modes

| Problem | Cause | Fix |
|---------|-------|-----|
| Ignores instructions | Instructions buried in long prompt | Put critical rules FIRST and LAST |
| Inconsistent format | No output format specified | Add explicit format + example |
| Wrong on edge cases | No examples for edges | Add few-shot examples for those cases |
| Doesn't reason | No CoT instruction | Add "Think step by step" |
| Overrides rules | Instruction conflict | Remove conflicting instructions |

---

## Prompt Optimization Process

1. **Start minimal** — add only what you can justify
2. **Measure** — run 20+ diverse inputs, track accuracy
3. **Identify failure patterns** — group by error type
4. **Fix one thing at a time** — A/B test each change
5. **Iterate** — each fix may reveal new issues

**Principle**: The simplest prompt that achieves target accuracy is the best prompt.

---

## MiniMax / Small Model Tips

- Shorter, more direct prompts work better than elaborate ones
- Break complex tasks into smaller prompts
- Explicit "Output X directly" beats implicit format expectations
- Add `# CRITICAL:` prefix for rules that must not be ignored
- Avoid multi-phase instructions — one task per prompt
