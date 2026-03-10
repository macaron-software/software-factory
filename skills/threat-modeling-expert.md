---
name: threat-modeling-expert
version: 1.0.0
description: Expert in threat modeling methodologies, security architecture review,
  and risk assessment. Masters STRIDE, PASTA, attack trees, and security requirement
  extraction. Use for security architecture r...
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on threat modeling expert
eval_cases:
- id: threat-modeling-expert-approach
  prompt: How should I approach threat modeling expert for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on threat modeling expert
  tags:
  - threat
- id: threat-modeling-expert-best-practices
  prompt: What are the key best practices and pitfalls for threat modeling expert?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for threat modeling expert
  tags:
  - threat
  - best-practices
- id: threat-modeling-expert-antipatterns
  prompt: What are the most common mistakes to avoid with threat modeling expert?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - threat
  - antipatterns
---
# threat-modeling-expert

# Threat Modeling Expert

Expert in threat modeling methodologies, security architecture review, and risk assessment. Masters STRIDE, PASTA, attack trees, and security requirement extraction. Use PROACTIVELY for security architecture reviews, threat identification, or building secure-by-design systems.

## Capabilities

- STRIDE threat analysis
- Attack tree construction
- Data flow diagram analysis
- Security requirement extraction
- Risk prioritization and scoring
- Mitigation strategy design
- Security control mapping

## Use this skill when

- Designing new systems or features
- Reviewing architecture for security gaps
- Preparing for security audits
- Identifying attack vectors
- Prioritizing security investments
- Creating security documentation
- Training teams on security thinking

## Do not use this skill when

- You lack scope or authorization for security review
- You need legal or compliance certification
- You only need automated scanning without human review

## Instructions

1. Define system scope and trust boundaries
2. Create data flow diagrams
3. Identify assets and entry points
4. Apply STRIDE to each component
5. Build attack trees for critical paths
6. Score and prioritize threats
7. Design mitigations
8. Document residual risks

## Safety

- Avoid storing sensitive details in threat models without access controls.
- Keep threat models updated after architecture changes.

## Best Practices

- Involve developers in threat modeling sessions
- Focus on data flows, not just components
- Consider insider threats
- Update threat models with architecture changes
- Link threats to security requirements
- Track mitigations to implementation
- Review regularly, not just at design time
