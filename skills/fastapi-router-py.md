---
name: fastapi-router-py
version: 1.0.0
description: Create FastAPI routers with CRUD operations, authentication dependencies,
  and proper response models. Use when building REST API endpoints, creating new routes,
  implementing CRUD operations, or add...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - 'building rest api endpoints, creating new routes, implementing crud operations, '
eval_cases:
- id: fastapi-router-py-approach
  prompt: How should I approach fastapi router py for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fastapi router py
  tags:
  - fastapi
- id: fastapi-router-py-best-practices
  prompt: What are the key best practices and pitfalls for fastapi router py?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fastapi router py
  tags:
  - fastapi
  - best-practices
- id: fastapi-router-py-antipatterns
  prompt: What are the most common mistakes to avoid with fastapi router py?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - fastapi
  - antipatterns
---
# fastapi-router-py

# FastAPI Router

Create FastAPI routers following established patterns with proper authentication, response models, and HTTP status codes.

## Quick Start

Copy the template from assets/template.py and replace placeholders:
- `{{ResourceName}}` → PascalCase name (e.g., `Project`)
- `{{resource_name}}` → snake_case name (e.g., `project`)
- `{{resource_plural}}` → plural form (e.g., `projects`)

## Authentication Patterns

```python
# Optional auth - returns None if not authenticated
current_user: Optional[User] = Depends(get_current_user)

# Required auth - raises 401 if not authenticated
current_user: User = Depends(get_current_user_required)
```

## Response Models

```python
@router.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: str) -> Item:
    ...

@router.get("/items", response_model=list[Item])
async def list_items() -> list[Item]:
    ...
```

## HTTP Status Codes

```python
@router.post("/items", status_code=status.HTTP_201_CREATED)
@router.delete("/items/{id}", status_code=status.HTTP_204_NO_CONTENT)
```

## Integration Steps

1. Create router in `src/backend/app/routers/`
2. Mount in `src/backend/app/main.py`
3. Create corresponding Pydantic models
4. Create service layer if needed
5. Add frontend API functions

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
