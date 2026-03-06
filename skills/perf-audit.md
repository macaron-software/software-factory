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

version: "1.1.0"

eval_cases:
  - id: lighthouse-full-audit
    prompt: "Run a full performance audit on http://localhost:8099 and give me the results."
    checks:
      - "regex:score|performance|lighthouse|suggest|accessib"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - Calls perf_audit_lighthouse with url=http://localhost:8099
      - Reports the actual performance score (0-100) from the tool return value
      - Lists at least 2 actionable improvement suggestions from the tool output
      - Does NOT ask the user for more information
      - Does NOT show only the tool invocation — shows what the tool returned
  - id: mobile-audit
    prompt: "Check if http://localhost:8099 is fast on mobile (Moto G4, fast-3g)."
    checks:
      - "regex:mobile|LCP|CLS|INP|threshold|device"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - Calls perf_emulate_mobile first with device=Moto G4 and network=fast-3g
      - Then calls perf_audit_lighthouse on http://localhost:8099
      - Reports LCP/CLS/INP values from the returned audit results
      - Compares values against Google Web Vitals thresholds (LCP<2.5s, CLS<0.1, INP<200ms)
      - Does NOT ask for a URL — it was provided in the prompt
  - id: slow-page-debug
    prompt: "http://localhost:8099 is taking 8 seconds to load. Diagnose why using trace tools."
    checks:
      - "regex:resource|network|trace|insight|fix|slow"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - Calls perf_trace_start with url=http://localhost:8099
      - Calls perf_trace_stop to retrieve trace results
      - Calls perf_analyze_insight for the worst insight from the trace
      - Calls perf_network_slow to find slow requests
      - Reports which specific resource is slowest and gives a concrete fix
      - Does NOT ask for clarification — the URL is in the prompt
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
