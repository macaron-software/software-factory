---
name: browser-exploration
description: >
  Enables the agent to explore web interfaces using a headless browser.
  Uses agent-browser (Rust CLI + Playwright/Chromium) to snapshot accessibility
  trees, click, fill forms, navigate, and screenshot — without scripted tests.
  Use this skill for exploration, validation, and UI-based research tasks.
metadata:
  category: research
  tools:
    - browser_snapshot
    - browser_click
    - browser_fill
    - browser_navigate
    - browser_get_text
    - browser_screenshot
    - browser_wait
  triggers:
    - "when user asks to explore a web interface"
    - "when verifying a deployed app visually"
    - "when navigating a third-party UI without an API"
    - "when checking if a feature is visible or accessible on a page"
    - "when doing UI-based research or competitive analysis"
    - "when user asks to check a URL for content or errors"
---

# Browser Exploration

This skill enables the agent to navigate and explore web interfaces using a headless
browser. It is **not** for writing tests (use `e2e-browser-testing` for that) — it is
for exploration, validation, and UI-based information gathering.

## Use this skill when

- Verifying a deployed feature is visible and functional
- Exploring a third-party web app (Jira, GitHub, dashboards) without an API
- Checking accessibility or page structure of a live URL
- Taking screenshots to document UI state
- Extracting visible text or content from a page
- Navigating multi-step flows to reach a specific state

## Do not use this skill when

- Writing Playwright tests (use `e2e-browser-testing`)
- Fetching raw HTML from a URL (use `web_fetch`)
- Testing an API endpoint (use `e2e-api-testing`)

## Core Concept: Snapshot-First Navigation

The **snapshot** is the agent's view of the page. It returns an accessibility tree
where every interactive element has a stable `@ref`:

```
browser_snapshot(url="https://example.com")
→
[1] heading "Example Domain"
[button] @e1 "More information..."
[link] @e2 "More information" href="/about"
[input] @e3 placeholder="Search..."
```

Always start with a snapshot. Use `@refs` for all subsequent interactions — they
are more stable and semantically correct than CSS selectors.

## Instructions

### Basic Exploration Loop

```
1. browser_snapshot(url=<url>)          → get accessibility tree + @refs
2. browser_click(selector="@e3")        → click, returns new snapshot automatically
3. browser_fill(selector="@e5", value="hello")  → fill input, returns snapshot
4. browser_screenshot()                 → capture current state
5. browser_navigate(url=<other_url>)    → go to another page
```

### Pattern: Explore a Login Flow

```
snapshot → find email input @ref → fill email
→ find password input @ref → fill password
→ find submit button @ref → click
→ wait for dashboard text → snapshot → screenshot
```

### Pattern: Extract Content from a Page

```
snapshot(url=<url>) → read snapshot for text content
# OR for specific element:
browser_get_text(selector="@e5")
# OR for full page text:
browser_get_text()  # returns snapshot (accessibility tree)
```

### Pattern: Verify a Deployed Feature

```
snapshot(url="http://staging.myapp.com/dashboard")
→ check snapshot contains expected elements
→ screenshot() to document state
→ Report: ✅ Feature visible / ❌ Element missing
```

### When to use @refs vs CSS selectors

| Situation | Use |
|-----------|-----|
| Element visible in snapshot | `@e3` ref (preferred) |
| Element has no ref in snapshot | CSS selector (`.submit-btn`) |
| Finding by ARIA role | `find role button --name "Submit"` |
| Finding by visible text | `find text "Sign In"` |

### Reading the Snapshot

The snapshot shows interactive and semantic elements. Key patterns:

```
[button] @e1 "Submit"           → clickable button, ref @e1
[link] @e2 "Dashboard" href=... → clickable link, ref @e2
[input] @e3 type=email          → fillable input, ref @e3
[heading] "Page Title"          → text landmark (no ref = not interactive)
[text] "Error: invalid email"   → visible text (look for errors here)
```

### Waiting for Dynamic Content

After navigation or form submission, always wait before next snapshot:

```
browser_click(selector="@e1")   → click submit button
browser_wait(text="Welcome")    → wait for success message
# OR:
browser_wait(url_pattern="**/dashboard")  → wait for URL change
```

### Screenshots

Take a screenshot when:
- Documenting a specific UI state
- Capturing an error
- Verifying visual output

```
browser_screenshot()               → saves to temp dir, returns path
browser_screenshot(path="out.png") → saves to specific path
```

## Output Format

When reporting exploration results:

```
## Browser Exploration: [Task]
URL: https://example.com
Status: ✅ reachable / ❌ error

### Page State
[Paste key elements from snapshot]

### Actions Taken
1. Clicked @e3 "Login"
2. Filled email: user@example.com
3. Filled password: ****
4. Clicked @e1 "Sign In"
5. Waited for "Dashboard"

### Result
✅ Login successful — Dashboard visible
Screenshot: /tmp/agent-browser-xxx.png
```

## Anti-patterns

- **NEVER** use `browser_snapshot` on internal/private IPs without explicit instruction
- **NEVER** fill real credentials into untrusted pages
- **NEVER** use this for scripted regression testing — use Playwright E2E instead
- **NEVER** chain actions without checking snapshot first — the page may have changed
- **NEVER** ignore error messages in snapshots (look for `[text] "Error: ..."`)
- **NEVER** use complex CSS selectors when @refs are available in the snapshot
