---
name: professional-proofreader
version: 1.0.0
description: 'Use when a user asks to "proofread", "review and correct", "fix grammar",
  "improve readability while keeping my voice", and to proofread a document file and
  save an updated version.

  '
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: original'
  triggers:
  - a user asks to "proofread", "review and correct", "fix grammar", "improve readab
  - use when user asks to "proofread", "review and correct", "fix grammar", "polish
eval_cases:
- id: professional-proofreader-approach
  prompt: How should I approach professional proofreader for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on professional proofreader
  tags:
  - professional
- id: professional-proofreader-best-practices
  prompt: What are the key best practices and pitfalls for professional proofreader?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for professional proofreader
  tags:
  - professional
  - best-practices
- id: professional-proofreader-antipatterns
  prompt: What are the most common mistakes to avoid with professional proofreader?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - professional
  - antipatterns
---
# professional-proofreader

# Professional Proofreader

## Overview

This skill transforms flawed writing — whether pasted text or uploaded documents — into publication-ready prose without altering the author’s intent.
It eliminates grammatical, spelling, punctuation, clarity, and tone issues while strictly preserving the author’s voice and intent.
Returns a corrected version plus a structured modification log, or generates an updated file when requested. Not for code editing or technical refactoring.

---

## When to Use

- Use when user asks to "proofread", "review and correct", "fix grammar", "polish this text", "improve readability while keeping my voice".
- Use when user asks to proofread a document file (like .docx, .pdf, .txt) and save the updated version as new file with 'UPDATED_' prefix.

---

# WORKFLOW MODES

This skill operates in two modes:
1. Inline Text Mode
2. File Processing Mode

### MODE 1: Inline Text

Refer [markdown](references/inline-text-mode.md) for complete inline text mode.

### MODE 2: File Processing

Trigger when user says:

- "Proofread [filename].[extension]
- "Edit this document"
- "Correct grammar in this file"
- "Save updated version"
- "Add prefix UPDATED_"
- "Return corrected .[extension]"

Refer [markdown](references/file-processing-mode.md) for complete file processing mode.

---

## Best Practices

### ✅ **Do:** [Good practice]
- Always include modification explanations.
- Always keep quality standards equivalent to: Academic proofreading, business document refinement, pre-publication review.
- Always follow below editing standards:

#### Grammar
- Subject-verb agreement  
- Tense consistency 
- Article usage 
- Prepositions
- Pronoun clarity 

#### Spelling
- Correct typos 
- Maintain original spelling variant (US/UK)

#### Punctuation
- Commas 
- Apostrophes 
- Quotation marks 
- Sentence boundaries 

#### Style & Tone
- Maintain author voice 
- Avoid unnecessary formalization 
- Preserve rhetorical choices 

#### Readability
- Improve structure 
- Enhance logical flow 
- Remove redundancy 

### ❌ **Don't:** [What to avoid] 
- Never alter meaning.
- Never drop formatting intentionally.
- Never change file name logic beyond request.
- Never expand the content

---

# Output Rules

If inline:
-> Return Corrected Version + Modifications list.

If file rewrite:
-> Save updated file.
-> Confirm filename.
-> Provide modifications list unless suppressed.

Give friendly message to user in the end.

---
