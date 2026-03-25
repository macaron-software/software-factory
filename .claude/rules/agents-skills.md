---
description: Agent definitions and skill YAML files
globs: platform/skills/definitions/**/*.yaml, platform/agents/**/*.yaml
---

- Every skill MUST have `eval_cases` in YAML frontmatter for quality tracking.
- eval_cases format: `id`, `prompt`, `checks` (deterministic), `expectations` (LLM judge).
- Checks must be discriminant (stub -> FAIL). No trivial checks like "output is non-empty".
- Pass threshold: `pass_rate >= 0.80` to ship. Grade = `0.6*checks + 0.4*llm_judge`.
- Never delete eval_cases. Never lower expectations. Always bump version on change.
- Agent `tools` field: merged with role floor (`ROLE_TOOL_MAP`). Custom tools ADD, never replace.
- Agent `model` field: must match a valid provider model. Default from `DEFAULT_MODEL`.
- Adversarial rules: code writers cannot declare their own success (L0+L1 review required).
