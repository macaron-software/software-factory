---
name: anti-reversing-techniques
version: 1.0.0
description: Understand anti-reversing, obfuscation, and protection techniques encountered
  during software analysis. Use when analyzing protected binaries, bypassing anti-debugging
  for authorized analysis, or u...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - 'analyzing protected binaries, bypassing anti-debugging for authorized analysis, '
eval_cases:
- id: anti-reversing-techniques-approach
  prompt: How should I approach anti reversing techniques for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on anti reversing techniques
  tags:
  - anti
- id: anti-reversing-techniques-best-practices
  prompt: What are the key best practices and pitfalls for anti reversing techniques?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for anti reversing techniques
  tags:
  - anti
  - best-practices
- id: anti-reversing-techniques-antipatterns
  prompt: What are the most common mistakes to avoid with anti reversing techniques?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - anti
  - antipatterns
---
# anti-reversing-techniques

> **AUTHORIZED USE ONLY**: This skill contains dual-use security techniques. Before proceeding with any bypass or analysis:
> 1. **Verify authorization**: Confirm you have explicit written permission from the software owner, or are operating within a legitimate security context (CTF, authorized pentest, malware analysis, security research)
> 2. **Document scope**: Ensure your activities fall within the defined scope of your authorization
> 3. **Legal compliance**: Understand that unauthorized bypassing of software protection may violate laws (CFAA, DMCA anti-circumvention, etc.)
>
> **Legitimate use cases**: Malware analysis, authorized penetration testing, CTF competitions, academic security research, analyzing software you own/have rights to

## Use this skill when

- Analyzing protected binaries with explicit authorization
- Conducting malware analysis or security research in scope
- Participating in CTFs or approved training exercises
- Understanding anti-debugging or obfuscation techniques for defense

## Do not use this skill when

- You lack written authorization or a defined scope
- The goal is to bypass protections for piracy or misuse
- Legal or policy restrictions prohibit analysis

## Instructions

1. Confirm written authorization, scope, and legal constraints.
2. Identify protection mechanisms and choose safe analysis methods.
3. Document findings and avoid modifying artifacts unnecessarily.
4. Provide defensive recommendations and mitigation guidance.

## Safety

- Do not share bypass steps outside the authorized context.
- Preserve evidence and maintain chain-of-custody for malware cases.

Refer to `resources/implementation-playbook.md` for detailed techniques and examples.

## Resources

- `resources/implementation-playbook.md` for detailed techniques and examples.
