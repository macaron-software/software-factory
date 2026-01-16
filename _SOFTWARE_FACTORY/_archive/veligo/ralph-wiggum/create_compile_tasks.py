#!/usr/bin/env python3
"""Create tasks from compilation errors."""
from pathlib import Path

TASKS_DIR = Path("tasks")
STATUS_DIR = Path("status")

# Find next task ID
existing = [int(f.stem[1:]) for f in TASKS_DIR.glob("T*.md") if f.stem[1:].isdigit()]
next_id = max(existing) + 1 if existing else 200

COMPILE_ERRORS = [
    {
        "file": "veligo-platform/backend/src/services/reporting/report_routes.rs",
        "line": "1-30",
        "error": "Missing imports: Serialize, Deserialize, ToSchema, IntoParams, Arc, Router",
        "fix": "Add use statements: use serde::{Serialize, Deserialize}; use utoipa::{ToSchema, IntoParams}; use std::sync::Arc; use axum::{Router, routing::get}; use axum::http::header;",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/services/reporting/report_routes.rs",
        "line": "312",
        "error": "Cannot find value aom_name in scope",
        "fix": "Define aom_name variable or pass it as parameter",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/station_management_module.rs",
        "line": "1-10",
        "error": "Missing Serialize derive on Station struct",
        "fix": "Add #[derive(Serialize)] to Station struct and use serde::Serialize",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/station_management_module.rs",
        "line": "78-101",
        "error": "DatabaseError trait not implemented for std::io::Error",
        "fix": "Map io::Error to proper sqlx error or use anyhow::Error",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/station_management_module.rs",
        "line": "264,363",
        "error": "Borrow of partially moved value e",
        "fix": "Clone error before moving or use reference",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/station_management_module.rs",
        "line": "378",
        "error": "Type mismatch: expected Arc<StationRepository> found Arc<Pool<Postgres>>",
        "fix": "Create StationRepository from pool or change function signature",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/subscription_module.rs",
        "line": "84-140",
        "error": "tonic::Status::bad_request and internal_server_error don't exist",
        "fix": "Use Status::invalid_argument() and Status::internal() instead",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/modules/subscription_module.rs",
        "line": "140",
        "error": "with_context method doesn't exist on tonic::Status",
        "fix": "Remove with_context or use Status::new(Code::Internal, message)",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/api/planner_api.rs",
        "line": "139,232",
        "error": "Field pool of TripPlanner is private",
        "fix": "Add pub to pool field or create getter method",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/infrastructure/database/repositories/tenant_config/json_file_repository.rs",
        "line": "119",
        "error": "Missing fields in ModulesConfig: carbon_tracking, chatbot_assistance, gamification, etc.",
        "fix": "Add all missing fields to ModulesConfig initializer with default values",
        "priority": "P0"
    },
]

print(f"Creating {len(COMPILE_ERRORS)} compilation fix tasks starting at T{next_id}")

for i, err in enumerate(COMPILE_ERRORS):
    task_id = f"T{next_id + i}"
    
    content = f"""# Task {task_id}: Fix compilation error in {err['file'].split('/')[-1]}

**Priority**: {err['priority']}
**Queue**: TDD
**Type**: compilation_fix

## Error
{err['error']}

## File
{err['file']}:{err['line']}

## Fix Required
{err['fix']}

## Success Criteria
- [ ] Error fixed
- [ ] cargo check passes for this file
- [ ] No new errors introduced

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: simple
WSJF: 10
---END_RALPH_STATUS---
"""
    
    (TASKS_DIR / f"{task_id}.md").write_text(content)
    (STATUS_DIR / f"{task_id}.status").write_text("PENDING\n")
    print(f"  {task_id}: {err['error'][:50]}...")

print(f"\nCreated T{next_id} to T{next_id + len(COMPILE_ERRORS) - 1}")
