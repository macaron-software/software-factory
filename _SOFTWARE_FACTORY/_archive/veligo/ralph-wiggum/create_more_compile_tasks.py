#!/usr/bin/env python3
"""Create more specific compilation fix tasks."""
from pathlib import Path

TASKS_DIR = Path("tasks")
STATUS_DIR = Path("status")

existing = [int(f.stem[1:]) for f in TASKS_DIR.glob("T*.md") if f.stem[1:].isdigit()]
next_id = max(existing) + 1 if existing else 200

ERRORS = [
    {
        "file": "veligo-platform/backend/src/modules/station_management_module.rs",
        "error": "sqlx compile-time queries fail - database not running",
        "fix": "Use sqlx::query! with offline mode or replace with runtime queries using sqlx::query()",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/subscription_module.rs",
        "error": "tonic::Status methods bad_request/internal_server_error don't exist",
        "fix": "Replace Status::bad_request() with Status::invalid_argument() and Status::internal_server_error() with Status::internal()",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/api/planner_api.rs",
        "error": "TripPlanner.pool field is private",
        "fix": "Make pool field pub or add a pub fn pool(&self) -> &PgPool getter method",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/infrastructure/database/repositories/tenant_config/json_file_repository.rs",
        "error": "Missing 9 fields in ModulesConfig initializer",
        "fix": "Add default values for: carbon_tracking, chatbot_assistance, gamification, loyalty_program, maintenance_scheduling, multi_language, partner_integration, push_notifications, weather_integration",
        "priority": "P0"
    },
]

print(f"Creating {len(ERRORS)} additional tasks at T{next_id}")

for i, err in enumerate(ERRORS):
    task_id = f"T{next_id + i}"
    content = f"""# Task {task_id}: {err['error'][:50]}

**Priority**: {err['priority']}
**Queue**: TDD
**Type**: compilation_fix

## Error
{err['error']}

## File
{err['file']}

## Fix Required
{err['fix']}

## Success Criteria
- [ ] cargo check passes
- [ ] No new errors

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
WSJF: 10
---END_RALPH_STATUS---
"""
    (TASKS_DIR / f"{task_id}.md").write_text(content)
    (STATUS_DIR / f"{task_id}.status").write_text("PENDING\n")
    print(f"  {task_id}: {err['file'].split('/')[-1]}")

print(f"\nDone: T{next_id}-T{next_id + len(ERRORS) - 1}")
