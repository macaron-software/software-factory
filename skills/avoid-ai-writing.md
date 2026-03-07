---
name: avoid-ai-writing
version: 1.0.0
description: Audit and rewrite content to remove 21 categories of AI writing patterns
  with a 43-entry replacement table
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/conorbronsdon/avoid-ai-writing'
  triggers:
  - when asked to "remove ai-isms," "clean up ai writing," or "make this sound less
eval_cases:
- id: avoid-ai-writing-approach
  prompt: How should I approach avoid ai writing for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on avoid ai writing
  tags:
  - avoid
- id: avoid-ai-writing-best-practices
  prompt: What are the key best practices and pitfalls for avoid ai writing?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for avoid ai writing
  tags:
  - avoid
  - best-practices
- id: avoid-ai-writing-antipatterns
  prompt: What are the most common mistakes to avoid with avoid ai writing?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - avoid
  - antipatterns
---
# avoid-ai-writing

# Avoid AI Writing — Audit & Rewrite

Detects and fixes AI writing patterns ("AI-isms") that make text sound machine-generated. Covers 21 pattern categories with a 43-entry word/phrase replacement table that maps each flagged term to a specific, plainer alternative.

## When to Use This Skill

- When asked to "remove AI-isms," "clean up AI writing," or "make this sound less like AI"
- After drafting content with AI and before publishing
- When editing any text that sounds like it was generated rather than written
- When auditing documentation, blog posts, marketing copy, or internal communications for AI tells

## What It Detects

**21 pattern categories:** formatting issues (em dashes, bold overuse, emoji headers, bullet-heavy sections), sentence structure problems (hedging, hollow intensifiers, rule of three), word/phrase replacements (43 entries like leverage→use, utilize→use, robust→reliable), template phrases, transition phrases, structural issues, significance inflation, copula avoidance, synonym cycling, vague attributions, filler phrases, generic conclusions, chatbot artifacts, notability name-dropping, superficial -ing analyses, promotional language, formulaic challenges, false ranges, inline-header lists, title case headings, and cutoff disclaimers.

## Example

**Prompt:**
```
Audit this for AI writing patterns:

"In today's rapidly evolving AI landscape, developers are embarking on a pivotal journey to leverage cutting-edge tools that streamline their workflows. Moreover, these robust solutions serve as a testament to the industry's commitment to fostering seamless experiences."
```

**Output:** The skill returns four sections:
1. **Issues found** — every AI-ism quoted (landscape, embarking, pivotal, leverage, cutting-edge, streamline, robust, serves as, testament to, fostering, seamless, Moreover, In today's rapidly evolving...)
2. **Rewritten version** — "Developers are starting to use newer AI tools to simplify their work. These tools are reliable, and they're making development less painful."
3. **What changed** — summary of edits
4. **Second-pass audit** — re-reads the rewrite to catch any surviving tells

## Limitations

- Does not detect AI-generated code, only prose
- Pattern matching is guideline-based, not absolute — some flagged words are fine in context
- The replacement table suggests alternatives but the best choice depends on context
- Cannot verify factual claims or find real citations to replace vague attributions
