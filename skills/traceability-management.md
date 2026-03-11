---
name: traceability-management
version: 1.0.0
description: >
  Manage end-to-end traceability in the Software Factory: legacy items → stories → code → tests.
  Uses legacy_scan, traceability_link, traceability_coverage, traceability_validate tools.
metadata:
  category: development
  triggers:
    - "when migrating a legacy system"
    - "when creating stories from legacy items"
    - "when linking code to stories or acceptance criteria"
    - "when validating traceability coverage"
    - "when checking for orphaned items (unlinked legacy, untested stories)"
eval_cases:
  - id: trace-link-creation
    prompt: "I just wrote UserService.swift that implements user story us-abc123. How do I record this?"
    should_trigger: true
    checks:
      - "regex:traceability_link|link.*create"
      - "regex:source_type.*code|implements"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "suggests calling traceability_link with action=create"
      - "uses source_type=code and link_type=implements"
    tags: [traceability, basic]
  - id: trace-coverage-check
    prompt: "How complete is our migration traceability? Any orphans?"
    should_trigger: true
    checks:
      - "regex:traceability_coverage|coverage_report|orphan"
      - "no_placeholder"
      - "length_min:100"
    expectations:
      - "calls traceability_coverage with include_orphans=true"
      - "interprets coverage percentages and lists orphaned items"
    tags: [traceability, coverage]
  - id: trace-matrix-validate
    prompt: "Show me the full traceability chain for all database tables"
    should_trigger: true
    checks:
      - "regex:traceability_validate|traceability_matrix"
      - "regex:item_type.*table"
      - "no_placeholder"
    expectations:
      - "calls traceability_validate with item_type=table"
      - "shows legacy→story→code→test chain per item"
    tags: [traceability, validation]
---
# Traceability Management

Manage bidirectional traceability across the full migration lifecycle:
**Legacy Item → User Story → Code → Test**.

## Use this skill when

- Migrating a legacy system and need to track every element
- Creating user stories from legacy inventory
- Linking new code to stories/acceptance criteria
- Validating that all legacy items are covered by stories, code, and tests
- Reporting on migration progress via coverage metrics

## Do not use this skill when

- Working on greenfield projects with no legacy system
- The task has no traceability or migration component

## Tools Available

### `legacy_scan`
Auto-discover legacy items from project source code.
```
legacy_scan(project_id="myproject", scope="all")
# scope: "all" | "db" (tables/columns/FK) | "code" (classes/methods) | "api" (endpoints)
# Optional: path="src/legacy/" to scan subdirectory only
```
Creates `legacy_items` entries with auto-generated UUIDs (li-xxxxxxxx).

### `traceability_link`
Create or list bidirectional links between items.
```
# Link a legacy table to a user story
traceability_link(action="create", source_id="li-abc12345", source_type="legacy_item",
                  target_id="us-xyz789", target_type="story", link_type="covers",
                  notes="Users table → user management story")

# Link code to a story
traceability_link(action="create", source_id="us-xyz789", source_type="story",
                  target_id="UserService.swift", target_type="code", link_type="implements")

# Link test to a story
traceability_link(action="create", source_id="us-xyz789", source_type="story",
                  target_id="UserServiceTests.swift", target_type="test", link_type="tests")

# List all links for an item
traceability_link(action="list", source_id="li-abc12345")
```

**Link types:**
| Type | Meaning | Example |
|------|---------|---------|
| `covers` | Story covers a legacy item | story → legacy table |
| `implements` | Code implements a story | code file → story |
| `tests` | Test covers a story/AC | test file → story |
| `migrates_from` | New code migrates from legacy | new service → old class |
| `maps_to` | Legacy item maps to new item | old table → new table |
| `replaces` | New item replaces legacy | new API → old endpoint |
| `depends_on` | Item depends on another | service → database |
| `references` | Generic reference | doc → architecture |

### `traceability_coverage`
Get coverage report: what percentage of legacy items have downstream links.
```
traceability_coverage(project_id="myproject", include_orphans=true)
```
Returns per-type stats (table: 80% covered, class: 60% covered, etc.)
plus lists of orphaned items (legacy with no story, stories with no tests).

### `traceability_validate`
Full traceability matrix: legacy → story → code → test chain per item.
```
traceability_validate(project_id="myproject", item_type="table")
```
Returns each legacy item with its complete trace chain. Items marked
`fully_traced: true` have links to story AND code AND test.

## Workflow

1. **Inventory**: Call `legacy_scan` to auto-discover items from codebase
2. **Link Stories**: For each legacy item, call `traceability_link` to connect to stories
3. **Link Code**: As code is written, link it to stories with `implements`
4. **Link Tests**: As tests are written, link them to stories with `tests`
5. **Check Coverage**: Call `traceability_coverage` to find gaps
6. **Validate Matrix**: Call `traceability_validate` for the full chain view
7. **Fix Orphans**: Address items with no downstream links

## Rules

- Every legacy item MUST have at least one `covers` link to a story
- Every story MUST have at least one `implements` link to code
- Every story SHOULD have at least one `tests` link to a test
- Use UUID refs (li-xxx, us-xxx, feat-xxx) in code comments for traceability
- Coverage target: ≥90% of legacy items fully traced before migration approval
