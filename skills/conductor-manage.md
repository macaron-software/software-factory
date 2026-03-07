---
name: conductor-manage
version: 1.0.0
description: 'Manage track lifecycle: archive, restore, delete, rename, and cleanup'
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on conductor manage
eval_cases:
- id: conductor-manage-approach
  prompt: How should I approach conductor manage for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on conductor manage
  tags:
  - conductor
- id: conductor-manage-best-practices
  prompt: What are the key best practices and pitfalls for conductor manage?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for conductor manage
  tags:
  - conductor
  - best-practices
- id: conductor-manage-antipatterns
  prompt: What are the most common mistakes to avoid with conductor manage?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - conductor
  - antipatterns
---
# conductor-manage

# Track Manager

Manage the complete track lifecycle including archiving, restoring, deleting, renaming, and cleaning up orphaned artifacts.

## Use this skill when

- Archiving, restoring, renaming, or deleting Conductor tracks
- Listing track status or cleaning orphaned artifacts
- Managing the track lifecycle across active, completed, and archived states

## Do not use this skill when

- Conductor is not initialized in the repository
- You lack permission to modify track metadata or files
- The task is unrelated to Conductor track management

## Instructions

- Verify `conductor/` structure and required files before proceeding.
- Determine the operation mode from arguments or interactive prompts.
- Confirm destructive actions (delete/cleanup) before applying.
- Update `tracks.md` and metadata consistently.
- If detailed steps are required, open `resources/implementation-playbook.md`.

## Safety

- Backup track data before delete operations.
- Avoid removing archived tracks without explicit approval.

## Resources

- `resources/implementation-playbook.md` for detailed modes, prompts, and workflows.
