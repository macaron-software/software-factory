---
name: employment-contract-templates
version: 1.0.0
description: Create employment contracts, offer letters, and HR policy documents following
  legal best practices. Use when drafting employment agreements, creating HR policies,
  or standardizing employment docume...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - drafting employment agreements, creating hr policies, or standardizing employmen
  - creating offer letters
  - writing employee handbooks
eval_cases:
- id: employment-contract-templates-approach
  prompt: How should I approach employment contract templates for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on employment contract templates
  tags:
  - employment
- id: employment-contract-templates-best-practices
  prompt: What are the key best practices and pitfalls for employment contract templates?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for employment contract templates
  tags:
  - employment
  - best-practices
- id: employment-contract-templates-antipatterns
  prompt: What are the most common mistakes to avoid with employment contract templates?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - employment
  - antipatterns
---
# employment-contract-templates

# Employment Contract Templates

Templates and patterns for creating legally sound employment documentation including contracts, offer letters, and HR policies.

## Use this skill when

- Drafting employment contracts
- Creating offer letters
- Writing employee handbooks
- Developing HR policies
- Standardizing employment documentation
- Preparing onboarding documentation

## Do not use this skill when

- You need jurisdiction-specific legal advice
- The task requires licensed counsel review
- The request is unrelated to employment documentation

## Instructions

- Confirm jurisdiction, employment type, and required clauses.
- Choose a document template and tailor role-specific terms.
- Validate compensation, benefits, and compliance requirements.
- Add signature, confidentiality, and IP assignment terms as needed.
- If detailed templates are required, open `resources/implementation-playbook.md`.

## Safety

- These templates are not legal advice; consult qualified counsel before use.

## Resources

- `resources/implementation-playbook.md` for detailed templates and checklists.
