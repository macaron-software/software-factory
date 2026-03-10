---
name: ui-design-standards
version: "1.0.0"
description: >
  Enforces mandatory UI design constraints for all frontend work: design tokens only
  (no hardcoded values), component-based architecture, Feather SVG icons (no emojis),
  and flat color backgrounds (no gradients). Use whenever writing, reviewing, or
  specifying any HTML/CSS/JSX interface code.
metadata:
  category: design
  triggers:
    - "when writing or reviewing any frontend HTML, CSS, or JSX"
    - "when implementing a UI component or page"
    - "when specifying frontend requirements or acceptance criteria"
    - "when doing a UI code review"
    - "when building or updating a design system"
eval_cases:
  - id: ui-standards-tokens
    prompt: "A developer asks: can I write `color: #3b82f6` directly in CSS? What should they do instead?"
    should_trigger: true
    checks:
      - "regex:var\\(--"
      - "regex:token|custom propert"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "Explains that hardcoded hex colors are forbidden, must use CSS custom properties (tokens)"
    tags: [tokens, css]
  - id: ui-standards-icons
    prompt: "A developer wants to add a warning icon to a form. They suggest using ⚠️. What is the correct approach?"
    should_trigger: true
    checks:
      - "regex:(?i)feather|svg"
      - "regex:(?i)emoji|unicode|emoticon"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "Rejects emoji, recommends Feather SVG icon with proper aria-label"
    tags: [icons, accessibility]
  - id: ui-standards-gradient
    prompt: "A designer wants a hero section with `background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)`. Is this acceptable?"
    should_trigger: true
    checks:
      - "regex:(?i)forbid|not allow|no gradient|flat|solid|token"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "Rejects gradient background, says backgrounds must use flat solid token colors"
    tags: [gradient, background]
---
# UI Design Standards

Mandatory constraints for all frontend work. No exceptions.

## The 4 Hard Rules

### 1. Design Tokens — Always

Every color, spacing, shadow, radius, font, and z-index **must** reference a CSS custom property (token). Never hardcode values.

```css
/* ❌ FORBIDDEN */
color: #3b82f6;
margin: 24px;
border-radius: 8px;
font-size: 14px;
box-shadow: 0 2px 8px rgba(0,0,0,0.1);

/* ✅ REQUIRED */
color: var(--color-primary);
margin: var(--space-6);
border-radius: var(--radius-md);
font-size: var(--text-sm);
box-shadow: var(--shadow-sm);
```

Token categories that must exist:
- `--color-*` — palette, semantic (primary, danger, success, warning, muted, surface, border)
- `--space-*` — spacing scale (1/2/3/4/6/8/12/16/24/32)
- `--text-*` — type scale (xs/sm/base/lg/xl/2xl/3xl/4xl)
- `--radius-*` — border-radius (sm/md/lg/full)
- `--shadow-*` — elevation levels (sm/md/lg)
- `--z-*` — z-index scale (base/dropdown/modal/toast)
- `--duration-*` / `--ease-*` — motion tokens

### 2. Components — No Yolo UI

Every repeated UI element must be a component. No one-off inline HTML blobs.

```jsx
/* ❌ FORBIDDEN — yolo inline HTML */
<div style="display:flex;align-items:center;gap:8px;padding:12px 16px;
  background:#f1f5f9;border-radius:8px;font-size:14px;color:#374151">
  ⚠️ Something went wrong
</div>

/* ✅ REQUIRED — named component using tokens */
<Alert variant="warning" icon="alert-triangle">
  Something went wrong
</Alert>
```

Minimum component set (must exist before building pages):
- `Button` — variants: primary/secondary/ghost/danger, sizes: sm/md/lg
- `Input`, `Select`, `Checkbox`, `Radio`, `Switch`
- `Alert` / `Toast` — variants: info/success/warning/error
- `Badge` — variants: neutral/primary/success/warning/danger
- `Card` — with optional header/footer
- `Modal` / `Dialog`
- `Icon` — wrapper for Feather SVG icons

### 3. Icons — Feather SVG Only

All icons must be Feather SVG icons (https://feathericons.com). No emoji, no unicode symbols, no other icon sets unless explicitly approved.

```html
<!-- ❌ FORBIDDEN — emoji as icon -->
<span>⚠️ Warning</span>
<button>🔍 Search</button>
<span>✅ Done</span>

<!-- ❌ FORBIDDEN — unicode symbols -->
<span>→ Next</span>
<span>× Close</span>

<!-- ✅ REQUIRED — Feather SVG inline -->
<button class="btn btn-primary">
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
  Search
</button>

<!-- Or via component -->
<Icon name="search" size={16} aria-hidden="true" />
<Icon name="alert-triangle" size={16} aria-hidden="true" />
<Icon name="check" size={16} aria-hidden="true" />
```

Feather icon names for common uses:
| Use case | Feather icon |
|----------|-------------|
| Success / done | `check`, `check-circle` |
| Warning | `alert-triangle` |
| Error | `alert-circle`, `x-circle` |
| Info | `info` |
| Close / dismiss | `x` |
| Search | `search` |
| Settings | `settings` |
| User | `user`, `users` |
| Edit | `edit-2`, `edit-3` |
| Delete | `trash-2` |
| Add | `plus`, `plus-circle` |
| External link | `external-link` |
| Arrow / chevron | `chevron-right`, `chevron-down`, `arrow-right` |
| Home | `home` |
| Bell / notification | `bell` |
| Menu | `menu` |
| Eye / visible | `eye`, `eye-off` |
| Copy | `copy` |
| Download | `download` |
| Upload | `upload` |
| Refresh | `refresh-cw` |
| Loading | `loader` (animate-spin) |
| Lock | `lock`, `unlock` |
| Mail | `mail` |
| Calendar | `calendar` |
| File | `file`, `file-text` |
| Chart | `bar-chart-2`, `trending-up` |

### 4. Backgrounds — Flat Colors Only

No CSS gradients on backgrounds. Period. Backgrounds use flat solid colors from the token palette.

```css
/* ❌ FORBIDDEN — gradient backgrounds */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
background: radial-gradient(circle, #f093fb 0%, #f5576c 100%);
background-image: linear-gradient(to right, var(--color-primary), var(--color-secondary));

/* ✅ REQUIRED — flat solid token colors */
background: var(--surface-base);
background: var(--surface-raised);
background: var(--color-primary);
background: var(--color-neutral-50);
```

Exception: gradients may be used on **text** (for decorative headings only) and on **small SVG illustrations**, never on containers or section backgrounds.

## Code Review Checklist

Before any frontend PR is approved, check:

- [ ] **Zero hardcoded hex colors** — all colors via `var(--color-*)`
- [ ] **Zero hardcoded spacing** — all spacing via `var(--space-*)` or utility classes
- [ ] **Zero inline styles** — no `style=""` attribute in HTML/JSX
- [ ] **Zero emojis** — no emoji chars in HTML/JSX content or labels
- [ ] **Feather icons only** — all icons are Feather SVGs or `<Icon name="...">` component
- [ ] **No gradient backgrounds** — backgrounds are flat token colors
- [ ] **All elements are components** — no one-off inline HTML for UI patterns

## Anti-Patterns (Hard Fails in AC)

| Anti-pattern | Why it fails |
|-------------|-------------|
| `color: #abc123` | Magic hex — breaks theming |
| `margin: 13px` | Magic number — not on scale |
| `<span>⚠️</span>` | Emoji icon — not accessible, not consistent |
| `<span>→</span>` | Unicode arrow — use Feather `arrow-right` |
| `background: linear-gradient(...)` | Gradient bg — not allowed |
| `style="padding: 24px"` | Inline style — blocks theming |
| `z-index: 9999` | Magic z-index — use `var(--z-modal)` |
| Duplicated div pattern | Missing component — extract to component |
