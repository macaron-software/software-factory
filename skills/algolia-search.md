---
name: algolia-search
version: 1.0.0
description: 'Expert patterns for Algolia search implementation, indexing strategies,
  React InstantSearch, and relevance tuning Use when: adding search to, algolia, instantsearch,
  search api, search functionality.'
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - adding search to, algolia, instantsearch, search api, search functionality
eval_cases:
- id: algolia-search-approach
  prompt: How should I approach algolia search for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on algolia search
  tags:
  - algolia
- id: algolia-search-best-practices
  prompt: What are the key best practices and pitfalls for algolia search?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for algolia search
  tags:
  - algolia
  - best-practices
- id: algolia-search-antipatterns
  prompt: What are the most common mistakes to avoid with algolia search?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - algolia
  - antipatterns
---
# algolia-search

# Algolia Search Integration

## Patterns

### React InstantSearch with Hooks

Modern React InstantSearch setup using hooks for type-ahead search.

Uses react-instantsearch-hooks-web package with algoliasearch client.
Widgets are components that can be customized with classnames.

Key hooks:
- useSearchBox: Search input handling
- useHits: Access search results
- useRefinementList: Facet filtering
- usePagination: Result pagination
- useInstantSearch: Full state access


### Next.js Server-Side Rendering

SSR integration for Next.js with react-instantsearch-nextjs package.

Use <InstantSearchNext> instead of <InstantSearch> for SSR.
Supports both Pages Router and App Router (experimental).

Key considerations:
- Set dynamic = 'force-dynamic' for fresh results
- Handle URL synchronization with routing prop
- Use getServerState for initial state


### Data Synchronization and Indexing

Indexing strategies for keeping Algolia in sync with your data.

Three main approaches:
1. Full Reindexing - Replace entire index (expensive)
2. Full Record Updates - Replace individual records
3. Partial Updates - Update specific attributes only

Best practices:
- Batch records (ideal: 10MB, 1K-10K records per batch)
- Use incremental updates when possible
- partialUpdateObjects for attribute-only changes
- Avoid deleteBy (computationally expensive)


## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | critical | See docs |
| Issue | high | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
