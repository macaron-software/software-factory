#!/usr/bin/env python3
"""Create micro-tasks for unimplemented routes/actions found by the explore agent."""
from pathlib import Path

TASKS_DIR = Path("tasks")
STATUS_DIR = Path("status")
TASKS_DIR.mkdir(exist_ok=True)
STATUS_DIR.mkdir(exist_ok=True)

# Tasks from the explore agent analysis
TASKS = [
    # P0 - Bike Service CRUD
    {"id": "T200", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement CreateBike gRPC method", "desc": "Implement CreateBike to create new bike record with tenant_id, code, serial_number, bike_type, station_id"},
    {"id": "T201", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement UpdateBike gRPC method", "desc": "Implement UpdateBike to update bike attributes (code, station_id, model, brand, battery_level)"},
    {"id": "T202", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement DeleteBike gRPC method", "desc": "Implement DeleteBike with soft delete (set deleted_at timestamp)"},
    {"id": "T203", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement UpdateBikeStatus gRPC method", "desc": "Implement UpdateBikeStatus to change status (available, reserved, in_use, maintenance, out_of_service, stolen)"},
    {"id": "T204", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement ReserveBike gRPC method", "desc": "Implement ReserveBike to create a reservation with expiration time"},
    {"id": "T205", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement CancelReservation gRPC method", "desc": "Implement CancelReservation to cancel an existing reservation"},
    {"id": "T206", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement ScheduleMaintenance gRPC method", "desc": "Implement ScheduleMaintenance to create maintenance record for a bike"},
    {"id": "T207", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement CompleteMaintenance gRPC method", "desc": "Implement CompleteMaintenance to mark maintenance as done and update bike status"},
    {"id": "T208", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/grpc/services/bike.rs",
     "title": "Implement ListMaintenanceRecords gRPC method", "desc": "Implement ListMaintenanceRecords to get maintenance history for a bike with pagination"},

    # P0 - Module Service
    {"id": "T209", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/bin/tonic-server.rs",
     "title": "Implement GetModule gRPC method", "desc": "Implement GetModule to return single module details by ID"},
    {"id": "T210", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/bin/tonic-server.rs",
     "title": "Implement GetModuleStatus gRPC method", "desc": "Implement GetModuleStatus to return module installation status for a tenant"},
    {"id": "T211", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/bin/tonic-server.rs",
     "title": "Implement ToggleModule gRPC method", "desc": "Implement ToggleModule to enable/disable a module for a tenant"},

    # P0 - Module Hooks
    {"id": "T215", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/handlers/admin_owner.rs",
     "title": "Implement module hook execution on enable", "desc": "Execute on_install and on_enable hooks from module_catalog.hooks_json when module is activated"},
    {"id": "T216", "priority": "P0", "queue": "TDD", "file": "veligo-platform/backend/src/handlers/admin_owner.rs",
     "title": "Register module HTTP routes dynamically", "desc": "Register HTTP routes at /api/modules/{slug}/* from module_catalog.routes_json on module activation"},

    # P1 - Module Admin
    {"id": "T212", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/infrastructure/http/module_routes.rs",
     "title": "Check module dependencies before deactivation", "desc": "In deactivate_module, check if other modules depend on this one before allowing deactivation"},
    {"id": "T213", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/infrastructure/http/module_routes.rs",
     "title": "Validate module config against JSON schema", "desc": "In update_module_config, validate config against module JSON schema before applying"},

    # P1 - Document API
    {"id": "T217", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/api/document_api.rs",
     "title": "Fetch real subscription details for contract", "desc": "In GET /api/documents/contract/:subscription_id, fetch actual subscription from database instead of mock"},

    # P1 - Rate Limiting
    {"id": "T223", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/bin/tonic-server.rs",
     "title": "Implement gRPC rate limiting via interceptors", "desc": "Implement rate limiting via tonic interceptors instead of tower layers for proper type compatibility"},

    # P1 - OAuth Error Handling
    {"id": "T224", "priority": "P1", "queue": "TDD", "file": "veligo-platform/backend/src/api/google_oauth.rs",
     "title": "Replace panic with error handling in OAuth", "desc": "Replace panic!() on invalid COOKIE_SECRET hex with proper Result error handling"},
]

print(f"Creating {len(TASKS)} micro-tasks...")

for task in TASKS:
    task_file = TASKS_DIR / f"{task['id']}.md"
    status_file = STATUS_DIR / f"{task['id']}.status"

    content = f"""# Task {task['id']}: {task['title']}

**Priority**: {task['priority']}
**Queue**: {task['queue']}
**Type**: implementation

## File
{task['file']}

## Description
{task['desc']}

## Success Criteria
- [ ] Implementation complete
- [ ] cargo check passes
- [ ] Unit tests added
- [ ] No new warnings

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
WSJF: {"12" if task['priority'] == "P0" else "8"}
---END_RALPH_STATUS---
"""
    task_file.write_text(content)
    status_file.write_text("PENDING\n")
    print(f"  Created {task['id']}: {task['title'][:50]}...")

print(f"\nDone: {len(TASKS)} tasks created (T200-T224)")
