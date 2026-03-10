---
name: agent-manager-skill
version: 1.0.0
description: Manage multiple local CLI agents via tmux sessions (start/stop/monitor/assign)
  with cron-friendly scheduling.
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on agent manager skill
eval_cases:
- id: agent-manager-skill-approach
  prompt: How should I approach agent manager skill for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on agent manager skill
  tags:
  - agent
- id: agent-manager-skill-best-practices
  prompt: What are the key best practices and pitfalls for agent manager skill?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for agent manager skill
  tags:
  - agent
  - best-practices
- id: agent-manager-skill-antipatterns
  prompt: What are the most common mistakes to avoid with agent manager skill?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - agent
  - antipatterns
---
# agent-manager-skill

# Agent Manager Skill

## When to use

Use this skill when you need to:

- run multiple local CLI agents in parallel (separate tmux sessions)
- start/stop agents and tail their logs
- assign tasks to agents and monitor output
- schedule recurring agent work (cron)

## Prerequisites

Install `agent-manager-skill` in your workspace:

```bash
git clone https://github.com/fractalmind-ai/agent-manager-skill.git
```

## Common commands

```bash
python3 agent-manager/scripts/main.py doctor
python3 agent-manager/scripts/main.py list
python3 agent-manager/scripts/main.py start EMP_0001
python3 agent-manager/scripts/main.py monitor EMP_0001 --follow
python3 agent-manager/scripts/main.py assign EMP_0002 <<'EOF'
Follow teams/fractalmind-ai-maintenance.md Workflow
EOF
```

## Notes

- Requires `tmux` and `python3`.
- Agents are configured under an `agents/` directory (see the repo for examples).
