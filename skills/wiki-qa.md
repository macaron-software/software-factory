---
name: wiki-qa
version: 1.0.0
description: Answers questions about a code repository using source file analysis.
  Use when the user asks a question about how something works, wants to understand
  a component, or needs help navigating the code...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - the user asks a question about how something works, wants to understand a compon
eval_cases:
- id: wiki-qa-approach
  prompt: How should I approach wiki qa for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on wiki qa
  tags:
  - wiki
- id: wiki-qa-best-practices
  prompt: What are the key best practices and pitfalls for wiki qa?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for wiki qa
  tags:
  - wiki
  - best-practices
- id: wiki-qa-antipatterns
  prompt: What are the most common mistakes to avoid with wiki qa?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - wiki
  - antipatterns
---
# wiki-qa

# Wiki Q&A

Answer repository questions grounded entirely in source code evidence.

## When to Activate

- User asks a question about the codebase
- User wants to understand a specific file, function, or component
- User asks "how does X work" or "where is Y defined"

## Procedure

1. Detect the language of the question; respond in the same language
2. Search the codebase for relevant files
3. Read those files to gather evidence
4. Synthesize an answer with inline citations

## Response Format

- Use `##` headings, code blocks with language tags, tables, bullet lists
- Cite sources inline: `(src/path/file.ts:42)`
- Include a "Key Files" table mapping files to their roles
- If information is insufficient, say so and suggest files to examine

## Rules

- ONLY use information from actual source files
- NEVER invent, guess, or use external knowledge
- Think step by step before answering

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
