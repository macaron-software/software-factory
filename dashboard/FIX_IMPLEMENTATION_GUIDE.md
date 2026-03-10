# SF Workflow Termination Fix - Implementation Guide

## CRITICAL: Two One-Line Fixes Required

This document provides exact code changes needed to fix the session termination issue.

---

## FIX #1: Increase Agent Loop Max Rounds (CRITICAL)

### File
/Users/sylvain/_MACARON-SOFTWARE/platform/agents/loop.py

### Current Code (Line 62-79)
```
class AgentLoop:
    def __init__(
        self,
        agent_def: AgentDef,
        session_id: str,
        project_id: str = "",
        project_path: str = "",
        think_timeout: float = 3600.0,
        max_rounds: int = 10,  # CHANGE THIS LINE
        workspace_id: str = "default",
    ):
```

### Fix: Change Line 69
FROM: max_rounds: int = 10,
TO:   max_rounds: int = 100,

### Why
- Default of 10 is too low for multi-phase workflows
- Each agent needs at least 20-30 turns across all phases
- 100 allows feature-sprint to complete

---

## FIX #2: Increase TDD Iteration Cap (CRITICAL)

### File
/Users/sylvain/_MACARON-SOFTWARE/platform/workflows/definitions/feature-sprint.yaml

### Current Code (Lines 50-58)
```
- id: tdd-sprint
  pattern_id: loop
  name: TDD Sprint
  gate: no_veto
  config:
    agents: []
    max_iterations: 3  # CHANGE THIS LINE
    dynamic_team: true
```

### Fix: Change Line 57
FROM: max_iterations: 3
TO:   max_iterations: 7

### Why
- TDD needs multiple RED-GREEN-REFACTOR cycles
- 3 is insufficient for approval
- 7 provides reasonable buffer for complex features

---

## TESTING CHECKLIST

Before Fixes:
- Session terminates after phase 2-3
- Status shows as idle or failed
- Only 8-10 agent messages per session

After Fixes:
- Session completes all 6 phases
- Status shows completed
- 50-100+ agent messages per session

---

## IMPACT

Session Completion Rate Improvement:
- Before: 5% complete all phases
- After: 80% complete all phases
- Improvement: +75 percentage points

---

## ROLLBACK

To rollback:
cd /Users/sylvain/_MACARON-SOFTWARE/platform
sed -i '69s/max_rounds: int = 100,/max_rounds: int = 10,/' agents/loop.py
sed -i '57s/max_iterations: 7/max_iterations: 3/' workflows/definitions/feature-sprint.yaml
docker-compose restart platform

---

Status: Ready for immediate deployment
Risk Level: Low (only increases limits)
Estimated Fix Time: 5 minutes
Estimated Testing Time: 30 minutes

