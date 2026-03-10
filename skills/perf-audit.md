---
# SOURCE: Inspired by chrome-devtools-mcp (Apache-2.0)
# https://github.com/ChromeDevTools/chrome-devtools-mcp
#
# WHY THIS SKILL:
#   SF agents that build or deploy web apps had no way to measure real performance.
#   Without this skill, an agent that deploys a feature doesn't know if it broke
#   LCP, introduced render-blocking resources, or caused JS errors.
#   This skill gives agents the same perf tooling a developer has in Chrome DevTools.
#
# WHAT WE BUILD ON:
#   - chrome-devtools-mcp for Lighthouse, CDP traces, Core Web Vitals, network, console
#   - NOT playwright-mcp (automation) — different tool for different job
#   - Google's Web Vitals thresholds as the scoring standard (LCP/CLS/INP)
#
# ROLES: reviewer, qa, dev, architect
#   - reviewer/qa: run audits as acceptance criteria on deployed features
#   - dev: debug perf regressions during development
#   - architect: validate perf budget compliance across projects

name: perf-audit
description: >
  Performance audit skill using Chrome DevTools MCP. Runs Lighthouse audits,
  captures Core Web Vitals (LCP/CLS/INP), profiles network and console errors.
  Activate when: reviewing a deployed feature, validating perf budgets,
  debugging a slow page, or running perf acceptance criteria.

version: "1.3.0"

eval_cases:
  - id: interpret-lighthouse-results
    prompt: |
      You just ran perf_audit_lighthouse on http://localhost:8099 and got this result:
      {
        "performance": 62, "accessibility": 88, "best-practices": 75, "seo": 91,
        "opportunities": [
          {"id": "render-blocking-resources", "score": 0.3, "savings_ms": 1850,
           "details": "3 CSS files block first paint: /static/main.css (420ms), /vendor/bootstrap.css (380ms), /fonts/inter.css (290ms)"},
          {"id": "unused-javascript", "score": 0.4, "savings_ms": 920,
           "details": "/static/app.js is 1.4MB (only 180KB used on this page)"},
          {"id": "unoptimized-images", "score": 0.5, "savings_ms": 680,
           "details": "hero.jpg is 2.8MB (could be 210KB as WebP)"}
        ],
        "console_errors": ["TypeError: Cannot read property 'user' of undefined (app.js:142)"]
      }
      Summarize the audit and give me the top 3 fixes ranked by impact.
    checks:
      - "regex:62|performance|render.block|bootstrap|app\\.js|WebP|hero"
      - "length_min:120"
      - "no_placeholder"
    expectations:
      - States performance score is 62/100 (Amber)
      - Lists render-blocking resources as #1 fix (1850ms savings — 3 CSS files)
      - Lists unused JS as #2 fix (app.js 1.4MB → trim to used 180KB)
      - Lists image optimization as #3 fix (hero.jpg 2.8MB → WebP 210KB)
      - Flags the console error TypeError in app.js:142
      - Does NOT ask for more info — all data is in the prompt

  - id: interpret-mobile-cwv
    prompt: |
      The perf_emulate_mobile and perf_audit_lighthouse tools have already been executed.
      Below are the collected results — do NOT run any tools, just interpret and recommend:

      Mobile audit complete (Moto G4 / fast-3g). Core Web Vitals from perf_audit_lighthouse:
      LCP: 5.2s (threshold: < 2.5s)
      CLS: 0.08 (threshold: < 0.1)
      INP: 420ms (threshold: < 200ms)
      Performance score: 41/100
      Top issue: "LCP element is hero.jpg — 2.8MB unoptimized image loaded eagerly"
      Are these results acceptable? What should be fixed first?
    checks:
      - "regex:5\\.2|LCP|Poor|41|hero\\.jpg|420|INP"
      - "length_min:120"
      - "no_placeholder"
    expectations:
      - States LCP 5.2s is ❌ Poor (> 4s threshold)
      - States CLS 0.08 is ✅ Good (< 0.1)
      - States INP 420ms is ❌ Poor (> 200ms threshold)
      - Identifies hero.jpg as the primary LCP fix (compress + lazy-load or WebP)
      - Says performance score 41/100 is unacceptable (below 80 budget)
      - Does NOT just restate the numbers — provides actionable recommendation

  - id: diagnose-slow-trace
    prompt: |
      You ran perf_trace_start + perf_trace_stop on http://localhost:8099. Trace results:
      LCP: 7.8s, CLS: 0.02, INP: 95ms
      Insights detected:
        - "render-blocking-resource": /static/vendor.js (2.1MB, blocks for 3.4s)
        - "long-animation-frame": dashboard_graph.js at line 445 (200ms frame)
      perf_network_slow results (threshold 1000ms):
        - GET /api/dashboard/stats — 4.1s (no cache headers, called on every render)
        - GET /api/users/me — 1.3s
      What is the root cause and what is the single most impactful fix?
    checks:
      - "regex:vendor\\.js|4\\.1s|/api/dashboard|cache|3\\.4s|root.cause"
      - "length_min:120"
      - "no_placeholder"
    expectations:
      - Identifies LCP=7.8s as ❌ Poor (root cause = vendor.js blocking 3.4s)
      - Names /api/dashboard/stats 4.1s as the most impactful network fix
      - Recommends adding cache headers or memoization to /api/dashboard/stats
      - Recommends splitting or lazy-loading vendor.js (2.1MB)
      - Gives concrete fix for the worst insight (render-blocking vendor.js)
      - Does NOT ask for clarification
---

# Performance Audit Skill

Audit deployed web apps for performance, accessibility, and runtime errors
using Chrome DevTools. Same tooling as a developer opening DevTools in Chrome.

---

## RULES

**MUST:**
- MUST call every tool listed in the workflow and **display the full returned data** in your response
- MUST use `http://localhost:8099` as default URL when none is specified in the request
- MUST report actual numbers from tool output (e.g. LCP=3.2s, score=74/100) — not hypothetical values
- MUST complete the entire workflow before presenting results

**NEVER:**
- NEVER ask the user for the URL — infer from context or use `http://localhost:8099`
- NEVER show only the tool invocation without showing what it returned
- NEVER write code or mock audit results instead of calling the tools
- NEVER say "I would call perf_audit_lighthouse" — just call it

---

## When to use this skill

- After deploying a feature: "does this page still meet our perf budget?"
- Before a release: acceptance criteria on LCP/CLS/INP scores
- Debugging a slow page: "what's making this page take 8 seconds to load?"
- Mobile performance check: "is this usable on 3G?"
- Monitoring: "did the last deploy introduce console errors?"

**Do NOT use this skill for:**
- Writing automated test scripts → use `e2e-browser-testing` skill
- Exploring page structure or clicking through a UI → use `browser-exploration` skill
- Fetching API data → use `web_fetch` or REST tools

---

## Google Web Vitals Thresholds (your scoring standard)

| Metric | Good ✅ | Needs Work ⚠️ | Poor ❌ |
|--------|---------|--------------|--------|
| **LCP** (Largest Contentful Paint) | < 2.5s | 2.5–4s | > 4s |
| **CLS** (Cumulative Layout Shift) | < 0.1 | 0.1–0.25 | > 0.25 |
| **INP** (Interaction to Next Paint) | < 200ms | 200–500ms | > 500ms |
| **FCP** (First Contentful Paint) | < 1.8s | 1.8–3s | > 3s |
| **TBT** (Total Blocking Time) | < 200ms | 200–600ms | > 600ms |

Lighthouse score ≥ 90 = Green, 50–89 = Amber, < 50 = Red.

---

## Tools reference

| Tool | When to use | Key params |
|------|------------|------------|
| `perf_audit_lighthouse` | Full audit (first step) | `url`, `categories` |
| `perf_emulate_mobile` | Before mobile audit | `device`, `network` |
| `perf_trace_start` | Profile a specific interaction | `url` |
| `perf_trace_stop` | Get CWV after interaction | — |
| `perf_analyze_insight` | Drill into a trace finding | `insight` |
| `perf_network_slow` | Find slow/failed requests | `url`, `threshold_ms` |
| `perf_console_errors` | Find runtime JS errors | `url`, `level` |

---

## Workflow 1 — Full Audit (standard)

Use for: release gates, PR reviews, onboarding a new project.

```
1. perf_audit_lighthouse(url, categories=["performance","accessibility","best-practices","seo"])
   → Get scores for all 4 categories
   → Extract top 3 opportunities with biggest score impact

2. If performance score < 90:
   perf_network_slow(url, threshold_ms=500)
   → Identify slow resources, oversized assets, failed fetches

3. perf_console_errors(url, level="error")
   → Find JS errors that may degrade UX or block interactions

4. Report format (see below)
```

## Workflow 2 — Mobile Audit

Use for: features visible to end users on mobile devices.

```
1. perf_emulate_mobile(device="Moto G4", network="fast-3g")
   → Set realistic mobile constraints

2. perf_audit_lighthouse(url, categories=["performance","accessibility"])
   → Mobile Lighthouse scores (will be lower than desktop — that's expected)

3. perf_trace_start(url) → interact → perf_trace_stop()
   → Real CWV under mobile throttling

4. perf_analyze_insight(insight="LCP")  ← if LCP is worst metric
   → Specific fix suggestions for the worst Core Web Vital

5. Reset: perf_emulate_mobile(device="desktop")
```

## Workflow 3 — Debug Slow Page

Use for: "page takes 8 seconds to load, why?"

```
1. perf_trace_start(url)
   → Starts recording while page loads

2. perf_trace_stop()
   → Returns: LCP/CLS/INP values + timeline + insight names

3. For each insight in trace results:
   perf_analyze_insight(insight="<name from trace>")
   → Deep analysis + specific code/resource to fix

4. perf_network_slow(url, threshold_ms=1000)
   → Find API calls or assets taking > 1s

5. Synthesize: root cause + fix recommendation
```

---

## Output format

Always structure perf audit output as:

```markdown
## Performance Audit — <url>

### Scores
| Category | Score | Status |
|----------|-------|--------|
| Performance | 73/100 | ⚠️ Amber |
| Accessibility | 91/100 | ✅ Green |
| Best Practices | 83/100 | ⚠️ Amber |
| SEO | 95/100 | ✅ Green |

### Core Web Vitals
| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| LCP | 3.8s | < 2.5s | ❌ Poor |
| CLS | 0.05 | < 0.1 | ✅ Good |
| INP | 180ms | < 200ms | ✅ Good |

### Top Issues (by score impact)
1. **[HIGH] Render-blocking resources** (+12 score) — 3 CSS files blocking first paint
   Fix: Add `defer` to non-critical CSS, or inline critical CSS
2. **[MED] Oversized images** (+8 score) — hero.jpg is 2.4MB (should be <300KB)
   Fix: Convert to WebP, compress, add `loading="lazy"`
3. **[LOW] Missing meta description** (+3 score) — affects SEO
   Fix: Add `<meta name="description" content="...">` to <head>

### Console Errors
- TypeError: Cannot read property 'user' of undefined (app.js:142)

### Slow Requests
- /api/dashboard/stats — 2.3s (P95) → add DB index on created_at
```

---

## Perf budgets for SF projects

Default budgets to enforce on all SF-managed projects:

```yaml
perf_budget:
  lighthouse_performance: ">= 80"
  lighthouse_accessibility: ">= 90"
  lcp: "< 3.0s"
  cls: "< 0.1"
  inp: "< 300ms"
  bundle_size_js: "< 300KB (gzipped)"
  bundle_size_css: "< 50KB (gzipped)"
```

Override per project in `PRINCIPLES.md` → `## Performance Budget` section.

---

## Integration with TMA / auto-heal

When a perf regression is detected (Lighthouse perf < 80 after deploy):
1. Log as an incident cluster in `error_state.py` with type `perf_regression`
2. Trigger a TMA epic via `monitoring_create_tma_epic` tool
3. Attach the full audit report as epic context

This wires perf audits into the same auto-heal loop as runtime errors.
