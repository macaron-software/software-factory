---
name: zustand-store-ts
version: 1.0.0
description: Create Zustand stores with TypeScript, subscribeWithSelector middleware,
  and proper state/action separation. Use when building React state management, creating
  global stores, or implementing reacti...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building react state management, creating global stores, or implementing reacti
eval_cases:
- id: zustand-store-ts-approach
  prompt: How should I approach zustand store ts for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on zustand store ts
  tags:
  - zustand
- id: zustand-store-ts-best-practices
  prompt: What are the key best practices and pitfalls for zustand store ts?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for zustand store ts
  tags:
  - zustand
  - best-practices
- id: zustand-store-ts-antipatterns
  prompt: What are the most common mistakes to avoid with zustand store ts?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - zustand
  - antipatterns
---
# zustand-store-ts

# Zustand Store

Create Zustand stores following established patterns with proper TypeScript types and middleware.

## Quick Start

Copy the template from assets/template.ts and replace placeholders:
- `{{StoreName}}` → PascalCase store name (e.g., `Project`)
- `{{description}}` → Brief description for JSDoc

## Always Use subscribeWithSelector

```typescript
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export const useMyStore = create<MyStore>()(
  subscribeWithSelector((set, get) => ({
    // state and actions
  }))
);
```

## Separate State and Actions

```typescript
export interface MyState {
  items: Item[];
  isLoading: boolean;
}

export interface MyActions {
  addItem: (item: Item) => void;
  loadItems: () => Promise<void>;
}

export type MyStore = MyState & MyActions;
```

## Use Individual Selectors

```typescript
// Good - only re-renders when `items` changes
const items = useMyStore((state) => state.items);

// Avoid - re-renders on any state change
const { items, isLoading } = useMyStore();
```

## Subscribe Outside React

```typescript
useMyStore.subscribe(
  (state) => state.selectedId,
  (selectedId) => console.log('Selected:', selectedId)
);
```

## Integration Steps

1. Create store in `src/frontend/src/store/`
2. Export from `src/frontend/src/store/index.ts`
3. Add tests in `src/frontend/src/store/*.test.ts`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
