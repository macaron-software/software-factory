---
name: pydantic-models-py
version: 1.0.0
description: Create Pydantic models following the multi-model pattern with Base, Create,
  Update, Response, and InDB variants. Use when defining API request/response schemas,
  database models, or data validation ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - defining api request/response schemas, database models, or data validation
eval_cases:
- id: pydantic-models-py-approach
  prompt: How should I approach pydantic models py for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on pydantic models py
  tags:
  - pydantic
- id: pydantic-models-py-best-practices
  prompt: What are the key best practices and pitfalls for pydantic models py?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for pydantic models py
  tags:
  - pydantic
  - best-practices
- id: pydantic-models-py-antipatterns
  prompt: What are the most common mistakes to avoid with pydantic models py?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - pydantic
  - antipatterns
---
# pydantic-models-py

# Pydantic Models

Create Pydantic models following the multi-model pattern for clean API contracts.

## Quick Start

Copy the template from assets/template.py and replace placeholders:
- `{{ResourceName}}` → PascalCase name (e.g., `Project`)
- `{{resource_name}}` → snake_case name (e.g., `project`)

## Multi-Model Pattern

| Model | Purpose |
|-------|---------|
| `Base` | Common fields shared across models |
| `Create` | Request body for creation (required fields) |
| `Update` | Request body for updates (all optional) |
| `Response` | API response with all fields |
| `InDB` | Database document with `doc_type` |

## camelCase Aliases

```python
class MyModel(BaseModel):
    workspace_id: str = Field(..., alias="workspaceId")
    created_at: datetime = Field(..., alias="createdAt")
    
    class Config:
        populate_by_name = True  # Accept both snake_case and camelCase
```

## Optional Update Fields

```python
class MyUpdate(BaseModel):
    """All fields optional for PATCH requests."""
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
```

## Database Document

```python
class MyInDB(MyResponse):
    """Adds doc_type for Cosmos DB queries."""
    doc_type: str = "my_resource"
```

## Integration Steps

1. Create models in `src/backend/app/models/`
2. Export from `src/backend/app/models/__init__.py`
3. Add corresponding TypeScript types

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
