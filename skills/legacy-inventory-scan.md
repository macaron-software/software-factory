---
name: legacy-inventory-scan
version: 1.0.0
description: >
  Systematically inventory all elements of a legacy system using legacy_scan tool:
  database objects, code structures, API endpoints, configurations.
metadata:
  category: development
  triggers:
    - "when starting a legacy system migration"
    - "when inventorying an existing codebase"
    - "when analyzing a legacy system for modernization"
    - "when building a migration plan from an existing system"
eval_cases:
  - id: inventory-database
    prompt: "We need to inventory all database tables and their relationships from the legacy Java app"
    should_trigger: true
    checks:
      - "regex:legacy_scan|scan.*db|item_type.*table"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "calls legacy_scan with scope=db"
      - "explains that tables, columns, FK, PK, indexes will be discovered"
    tags: [legacy, inventory]
  - id: inventory-full
    prompt: "Give me a complete inventory of this legacy system"
    should_trigger: true
    checks:
      - "regex:legacy_scan|scope.*all"
      - "no_placeholder"
      - "length_min:100"
    expectations:
      - "calls legacy_scan with scope=all"
      - "plans follow-up with traceability_coverage to check completeness"
    tags: [legacy, inventory]
---
# Legacy Inventory Scan

Systematically discover and catalog every element of a legacy system
before migration. The inventory becomes the foundation for traceability.

## Use this skill when

- Starting a new migration project — first step is always inventory
- Analyzing an unfamiliar legacy codebase
- Building a migration plan that tracks every legacy element
- Auditing completeness of a migration inventory

## Do not use this skill when

- Working on a greenfield project
- The legacy system has already been fully inventoried

## How to Inventory

### Step 1: Full Scan
```
legacy_scan(project_id="myproject", scope="all")
```
This auto-discovers:
- **DB scope**: tables, columns, foreign keys, primary keys, indexes, triggers, views, procedures
- **Code scope**: classes, methods, services, controllers, DTOs, entities, validators
- **API scope**: endpoints, routes, middleware, interceptors

### Step 2: Targeted Scans (if needed)
```
# Scan only database objects
legacy_scan(project_id="myproject", scope="db")

# Scan only a specific directory
legacy_scan(project_id="myproject", scope="code", path="src/main/java/com/legacy/")

# Scan only API layer
legacy_scan(project_id="myproject", scope="api")
```

### Step 3: Review Results
Each discovered item gets:
- **UUID**: `li-xxxxxxxx` (auto-generated, permanent identifier)
- **Type**: table, class, endpoint, etc.
- **Name**: extracted from source
- **Source file + line**: where it was found
- **Status**: starts as `identified`

### Step 4: Status Tracking
Legacy items progress through statuses:
```
identified → analyzed → mapped → migrated → verified
```

### Step 5: Coverage Check
After inventory, check completeness:
```
traceability_coverage(project_id="myproject", include_orphans=true)
```

## Item Types Supported

| Category | Types |
|----------|-------|
| Database | table, column, fk, pk, index, trigger, view, procedure, function |
| Code | class, method, service, controller, dto, entity, validator, interceptor, filter |
| API | endpoint, config, permission, role |
| UI | menu, page, report |
| Infra | scheduler, listener, migration, seed_data |

## Rules

- ALWAYS start migration projects with `legacy_scan(scope="all")`
- Review scan results — automated discovery may miss dynamic elements
- Add manually discovered items via `traceability_link` with notes
- Re-scan after codebase changes to catch new elements
- Target: 100% of legacy elements inventoried before story generation begins
