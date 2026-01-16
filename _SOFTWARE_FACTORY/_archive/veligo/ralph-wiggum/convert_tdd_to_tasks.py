#!/usr/bin/env python3
"""Convert Brain's TDD-xxx planning docs to atomic T### tasks."""
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TASKS_DIR = SCRIPT_DIR / "tasks"
STATUS_DIR = SCRIPT_DIR / "status"

# Find next task ID
existing_ids = []
for f in TASKS_DIR.glob("T*.md"):
    try:
        existing_ids.append(int(f.stem[1:]))
    except:
        pass
next_id = max(existing_ids) + 1 if existing_ids else 200

# Map TDD tasks to atomic micro-tasks
ATOMIC_TASKS = [
    # TDD-001: FranceConnect
    {
        "file": "veligo-platform/backend/src/auth/franceconnect/mod.rs",
        "description": "Create FranceConnect OAuth config module",
        "ao_ref": "AO-IDFM-AUTH-3.1.3",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/backend/src/api/google_oauth.rs", 
        "description": "Add FranceConnect authorization endpoint alongside Google OAuth",
        "ao_ref": "AO-IDFM-AUTH-3.1.3",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/frontend/src/lib/components/FranceConnectButton.svelte",
        "description": "Create FranceConnect login button with data-testid='franceconnect-login'",
        "ao_ref": "AO-IDFM-AUTH-3.1.3",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/tests/e2e/journeys/idfm-franceconnect-sso.spec.ts",
        "description": "Create FranceConnect SSO E2E journey test",
        "ao_ref": "AO-IDFM-AUTH-3.1.3",
        "priority": "P0"
    },
    
    # TDD-002: Box Securisés Nantes
    {
        "file": "veligo-platform/backend/src/domain/station/box_securise.rs",
        "description": "Implement box sécurisé booking logic for Nantes tenant",
        "ao_ref": "AO-NANTES-BOX-5.1",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/frontend/src/routes/(tenant)/nantes/boxes/+page.svelte",
        "description": "Create Nantes box sécurisé booking page with real selectors",
        "ao_ref": "AO-NANTES-BOX-5.1",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/tests/e2e/journeys/nantes-box-booking.spec.ts",
        "description": "Create Nantes box sécurisé E2E journey test",
        "ao_ref": "AO-NANTES-BOX-5.1",
        "priority": "P0"
    },
    
    # TDD-003: TCL Lyon
    {
        "file": "veligo-platform/backend/src/integration/tcl_api.rs",
        "description": "Implement TCL Open Data API client for Lyon",
        "ao_ref": "AO-LYON-TCL-4.1",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/frontend/src/routes/(tenant)/lyon/tcl/+page.svelte",
        "description": "Create TCL multimodal journey page for Lyon",
        "ao_ref": "AO-LYON-TCL-4.1",
        "priority": "P0"
    },
    {
        "file": "veligo-platform/tests/e2e/journeys/lyon-tcl-multimodal.spec.ts",
        "description": "Create Lyon TCL multimodal E2E journey test",
        "ao_ref": "AO-LYON-TCL-4.1",
        "priority": "P0"
    },
    
    # TDD-004: data-testid standardization
    {
        "file": "veligo-platform/frontend/src/lib/components/LoginWidget.svelte",
        "description": "Standardize data-testid selectors in LoginWidget",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
    {
        "file": "veligo-platform/frontend/src/lib/components/StationCard.svelte",
        "description": "Add data-testid='station-card-{id}' selector to StationCard",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
    {
        "file": "veligo-platform/frontend/src/lib/components/BookingForm.svelte",
        "description": "Add data-testid selectors to BookingForm fields",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
    
    # TDD-005: Fixtures unification
    {
        "file": "veligo-platform/tests/e2e/fixtures/users.json",
        "description": "Unify user fixtures with consistent domain structure",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
    {
        "file": "veligo-platform/tests/e2e/fixtures/test-data.ts",
        "description": "Create unified test data export with all fixtures",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
    
    # TDD-006: Mocks to integration
    {
        "file": "veligo-platform/tests/e2e/helpers/api.helper.ts",
        "description": "Replace mock API calls with real gRPC-Web integration",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
    
    # TDD-010: Selector validation
    {
        "file": "veligo-platform/tests/e2e/helpers/selectors.helper.ts",
        "description": "Create selector validation helper that checks frontend components",
        "ao_ref": "AO-COMMON",
        "priority": "P1"
    },
]

print(f"Creating {len(ATOMIC_TASKS)} atomic tasks starting at T{next_id}")

for i, task in enumerate(ATOMIC_TASKS):
    task_id = f"T{next_id + i}"
    
    # Create task file
    content = f"""# Task {task_id}: {task['description']}

**Priority**: {task['priority']}
**Queue**: TDD
**AO Reference**: {task['ao_ref']}

## Description
{task['description']}

## File
{task['file']}

## Success Criteria
- [ ] File created/modified correctly
- [ ] Code compiles
- [ ] Tests pass
- [ ] No regressions

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
WSJF: 8
---END_RALPH_STATUS---
"""
    
    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(content)
    
    # Create status file
    status_file = STATUS_DIR / f"{task_id}.status"
    status_file.write_text("PENDING\n")
    
    print(f"  Created {task_id}: {task['description'][:50]}...")

print(f"\nDone! Created tasks T{next_id} to T{next_id + len(ATOMIC_TASKS) - 1}")
