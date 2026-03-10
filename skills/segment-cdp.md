---
name: segment-cdp
version: 1.0.0
description: Expert patterns for Segment Customer Data Platform including Analytics.js,
  server-side tracking, tracking plans with Protocols, identity resolution, destinations
  configuration, and data governance ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - when working on segment cdp
eval_cases:
- id: segment-cdp-approach
  prompt: How should I approach segment cdp for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on segment cdp
  tags:
  - segment
- id: segment-cdp-best-practices
  prompt: What are the key best practices and pitfalls for segment cdp?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for segment cdp
  tags:
  - segment
  - best-practices
- id: segment-cdp-antipatterns
  prompt: What are the most common mistakes to avoid with segment cdp?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - segment
  - antipatterns
---
# segment-cdp

# Segment CDP

## Patterns

### Analytics.js Browser Integration

Client-side tracking with Analytics.js. Include track, identify, page,
and group calls. Anonymous ID persists until identify merges with user.


### Server-Side Tracking with Node.js

High-performance server-side tracking using @segment/analytics-node.
Non-blocking with internal batching. Essential for backend events,
webhooks, and sensitive data.


### Tracking Plan Design

Design event schemas using Object + Action naming convention.
Define required properties, types, and validation rules.
Connect to Protocols for enforcement.


## Anti-Patterns

### ❌ Dynamic Event Names

### ❌ Tracking Properties as Events

### ❌ Missing Identify Before Track

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | medium | See docs |
| Issue | high | See docs |
| Issue | medium | See docs |
| Issue | high | See docs |
| Issue | low | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | high | See docs |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
