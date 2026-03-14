---
name: design-system-components
version: "1.0.0"
description: >
  Complete SF design system reference: 60 components (component.gallery), atomic design
  hierarchy, full token system (color/font/spacing/padding/radius/shadow), Feather SVG
  icons, accessibility patterns, semantic HTML rules. No emoji in UI — Feather icons only.
metadata:
  category: design
  source: "https://component.gallery + https://feathericons.com (MIT)"
  integrated_by: "macaron-software/software-factory"
  triggers:
    - "when creating or reviewing a UI component"
    - "when building a design system"
    - "when implementing tokens, colors, fonts, spacing"
    - "when writing HTML/CSS for a component"
    - "when reviewing frontend code for design system compliance"
    - "when an icon is needed"
    - "when generating tokens.css or themes.css"
    - "when auditing for emoji or hardcoded values"
    - "when implementing atomic design"
    - "when scaffolding a frontend project"
---

# Design System Components — SF Reference

Source: https://component.gallery (60 components, 95 design systems, 2676 examples)
Icons: https://feathericons.com (287 icons, MIT, 24×24 grid)
Methodology: Atomic Design (Brad Frost)

---

## RULE ZERO — NO EMOJI IN UI

**VETO**: Any emoji (😀🔔✅❌⚠️) in UI labels, headings, buttons, notifications.
**USE**: SVG Feather icons instead (see Icon System section below).
**Exception**: user-generated content, emoji pickers only.

---

## 1. ATOMIC DESIGN HIERARCHY

```
Atoms        → smallest reusable units: Button, Badge, Icon, Label, Input, Spinner
Molecules    → groups of atoms: FormField (Label + Input + Error), SearchBar (Input + Button)
Organisms    → groups of molecules: Header (Logo + Nav + SearchBar), Card (Image + Heading + CTA)
Templates    → page-level wireframes (layout without content)
Pages        → templates with real content (final rendered state)
```

### Atom Inventory (SF standard)

| Atom | HTML | Notes |
|------|------|-------|
| Button | `<button type="button\|submit\|reset">` | Never `<div>`, never `<a href="#">` |
| Link | `<a href="...">` | Never `<button>` for navigation |
| Icon | `<svg aria-hidden="true">` | Feather only, decorative=aria-hidden |
| Label | `<label for="id">` | Always linked to input |
| Badge | `<span class="badge">` | Inline, semantic text |
| Spinner | `<svg role="status" aria-label="Loading">` | See spinner template below |
| Skeleton | `<div class="skeleton" aria-hidden="true">` | Shape placeholder |
| Separator | `<hr>` or `role="separator"` | Not just visual margin |
| Stack | `<div class="stack">` | Spacing utility wrapper |
| Visually hidden | `<span class="sr-only">` | Screen-reader only text |

---

## 2. COMPLETE COMPONENT CATALOGUE

### Navigation & Structure

#### Accordion (= Collapse / Disclosure / Details)
```html
<h2>
  <button type="button" aria-expanded="false" aria-controls="panel-1">
    Section title
    <svg aria-hidden="true" focusable="false" class="feather feather-chevron-down">
      <use href="/icons/feather-sprite.svg#chevron-down"/>
    </svg>
  </button>
</h2>
<div id="panel-1" hidden>
  <p>Content</p>
</div>
```
- `aria-expanded` toggles true/false on click
- CSS: `button[aria-expanded='true'] .feather-chevron-down { transform: rotate(180deg) }`
- Alternative: native `<details>/<summary>` (no JS, but less control)
- ⚠️ Do NOT use accordion for critical/essential content (it hides it)

#### Breadcrumb
```html
<nav aria-label="Breadcrumb">
  <ol>
    <li><a href="/">Home</a></li>
    <li><a href="/products">Products</a></li>
    <li><span aria-current="page">Current Page</span></li>
  </ol>
</nav>
```

#### Navigation (= Nav / Menu)
```html
<nav aria-label="Main navigation">
  <ul role="list">
    <li><a href="/dashboard" aria-current="page">Dashboard</a></li>
    <li><a href="/projects">Projects</a></li>
  </ul>
</nav>
```

#### Pagination
```html
<nav aria-label="Pagination">
  <a href="?page=1" aria-label="Page 1">1</a>
  <a href="?page=2" aria-label="Page 2" aria-current="page">2</a>
  <a href="?page=3" aria-label="Page 3">3</a>
</nav>
```

#### Tabs
```html
<div role="tablist" aria-label="Settings sections">
  <button role="tab" aria-selected="true" aria-controls="panel-1" id="tab-1">General</button>
  <button role="tab" aria-selected="false" aria-controls="panel-2" id="tab-2">Security</button>
</div>
<div id="panel-1" role="tabpanel" aria-labelledby="tab-1">...</div>
<div id="panel-2" role="tabpanel" aria-labelledby="tab-2" hidden>...</div>
```
- Keyboard: Tab moves focus in/out of tablist; ← → cycles between tabs
- CSS: `.tab[aria-selected='true'] { color: var(--color-brand); border-bottom: 2px solid var(--color-brand) }`

#### Tree View
```html
<ul role="tree" aria-label="File explorer">
  <li role="treeitem" aria-expanded="false">
    <span>src/</span>
    <ul role="group" hidden>
      <li role="treeitem"><span>main.ts</span></li>
    </ul>
  </li>
</ul>
```

---

### Buttons & Actions

#### Button (Primary / Secondary / Destructive / Icon)
```html
<!-- Primary CTA -->
<button type="button" class="btn btn--primary">Save changes</button>

<!-- Secondary -->
<button type="button" class="btn btn--secondary">Cancel</button>

<!-- Destructive -->
<button type="button" class="btn btn--danger">Delete account</button>

<!-- Icon-only: MUST have accessible label -->
<button type="button" aria-label="Close dialog">
  <svg aria-hidden="true" class="feather feather-x"><use href="/icons/feather-sprite.svg#x"/></svg>
</button>

<!-- Icon + text: icon is decorative -->
<button type="button" class="btn btn--primary">
  <svg aria-hidden="true" class="feather feather-plus"><use href="/icons/feather-sprite.svg#plus"/></svg>
  Add item
</button>
```
- NEVER: `cursor: pointer` on `<button>` (pointer is for links, not buttons)
- Always specify `type` attribute
- Min touch target: 44×44px (CSS: `min-height: 44px; min-width: 44px`)

#### Button Group (= Toolbar / Segmented Control)
```html
<div role="toolbar" aria-label="Text formatting">
  <button type="button" aria-pressed="true">Bold</button>
  <button type="button" aria-pressed="false">Italic</button>
</div>
```

---

### Forms & Inputs

#### Text Input
```html
<div class="field">
  <label for="email">Email address</label>
  <input type="email" id="email" name="email" autocomplete="email"
         aria-describedby="email-hint email-error">
  <p id="email-hint" class="hint">We'll never share your email.</p>
  <p id="email-error" class="error" role="alert" hidden>Enter a valid email address.</p>
</div>
```

#### Select (= Dropdown)
```html
<div class="field">
  <label for="country">Country</label>
  <select id="country" name="country" autocomplete="country">
    <option value="">Select a country</option>
    <option value="fr">France</option>
    <option value="uk">United Kingdom</option>
  </select>
</div>
```
- Use native `<select>` for simple cases — custom dropdowns add accessibility burden
- Custom select: use `role="combobox"` + `role="listbox"` + `role="option"` ARIA pattern

#### Checkbox
```html
<fieldset>
  <legend>Notifications</legend>
  <label><input type="checkbox" name="email" checked> Email</label>
  <label><input type="checkbox" name="sms"> SMS</label>
</fieldset>
```

#### Radio Group
```html
<fieldset>
  <legend>Plan</legend>
  <label><input type="radio" name="plan" value="free"> Free</label>
  <label><input type="radio" name="plan" value="pro"> Pro</label>
</fieldset>
```

#### Toggle (= Switch)
```html
<button type="button" role="switch" aria-checked="false" aria-label="Enable notifications">
  <span aria-hidden="true"><!-- visual toggle track/thumb --></span>
</button>
```

#### Textarea
```html
<label for="message">Message</label>
<textarea id="message" name="message" rows="4" aria-describedby="message-count"></textarea>
<span id="message-count" aria-live="polite">0/500 characters</span>
```

#### File Input (= Dropzone)
```html
<label for="upload" class="dropzone">
  <svg aria-hidden="true" class="feather feather-upload"><use href="/icons/feather-sprite.svg#upload"/></svg>
  Drop files here or <span class="link">browse</span>
  <input type="file" id="upload" name="upload" accept=".pdf,.png" hidden>
</label>
```

#### Search
```html
<form role="search">
  <label for="search" class="sr-only">Search</label>
  <input type="search" id="search" name="q" placeholder="Search...">
  <button type="submit" aria-label="Submit search">
    <svg aria-hidden="true" class="feather feather-search"><use href="/icons/feather-sprite.svg#search"/></svg>
  </button>
</form>
```

#### Date Picker
```html
<!-- Native: use type="date" for max accessibility -->
<label for="dob">Date of birth</label>
<input type="date" id="dob" name="dob" min="1900-01-01" max="2025-12-31">
<!-- Custom: use role="dialog" + aria-label on calendar widget -->
```

---

### Feedback & Status

#### Alert (= Notification / Banner / Callout)
```html
<!-- Static alert -->
<div role="alert" class="alert alert--error">
  <svg aria-hidden="true" class="feather feather-alert-circle"><use href="/icons/feather-sprite.svg#alert-circle"/></svg>
  <p>Something went wrong. <a href="#">Try again</a>.</p>
</div>

<!-- Dynamic (appears after action): use role="alert" aria-live="assertive" -->
<!-- Info/success: use role="status" aria-live="polite" -->
```
Alert variants and icons (Feather):
- `error` → `alert-circle` (red)
- `warning` → `alert-triangle` (amber)
- `success` → `check-circle` (green)
- `info` → `info` (blue)

#### Toast (= Snackbar)
```html
<div role="status" aria-live="polite" class="toast-container">
  <!-- Injected by JS -->
  <div class="toast toast--success">
    <svg aria-hidden="true" class="feather feather-check"><use href="/icons/feather-sprite.svg#check"/></svg>
    Changes saved
    <button type="button" aria-label="Dismiss" class="toast__close">
      <svg aria-hidden="true" class="feather feather-x"><use href="/icons/feather-sprite.svg#x"/></svg>
    </button>
  </div>
</div>
```
- Auto-dismiss: 4–6s for non-critical; persist for errors
- Position: bottom-right (desktop), bottom-center (mobile)
- `role="alert"` for errors; `role="status"` for success/info

#### Spinner (= Loader)
```html
<div role="status" aria-label="Loading">
  <svg class="spinner" viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="12" cy="12" r="10" fill="none"
            stroke="currentColor" stroke-width="2"
            stroke-dasharray="60" stroke-dashoffset="60">
      <animateTransform attributeName="transform" type="rotate"
                        from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
    </circle>
  </svg>
  <span class="sr-only">Loading…</span>
</div>
```
- Always include screen-reader text
- Use alongside skeleton screens for >1s loads
- NEVER use an emoji as spinner (❌ "Loading... ⏳")

#### Skeleton Loader
```html
<div aria-busy="true" aria-label="Loading content">
  <div class="skeleton skeleton--text" style="width: 60%"></div>
  <div class="skeleton skeleton--text" style="width: 40%"></div>
  <div class="skeleton skeleton--rect" style="height: 200px"></div>
</div>
```
- CSS: `background: linear-gradient(90deg, var(--color-gray-100) 25%, var(--color-gray-200) 50%, var(--color-gray-100) 75%)`
- Shimmer animation is an exception to the "no gradient" rule (functional, not decorative)
- Set `aria-busy="true"` on parent; remove + add content when loaded

#### Progress Bar
```html
<div role="progressbar" aria-valuenow="40" aria-valuemin="0" aria-valuemax="100"
     aria-label="Upload progress" style="--progress: 40%">
  <div class="progress__fill"></div>
  <span class="sr-only">40% complete</span>
</div>
```

#### Progress Steps (= Stepper)
```html
<ol class="steps" aria-label="Checkout steps">
  <li aria-current="step">Cart</li>
  <li>Shipping</li>
  <li>Payment</li>
  <li>Confirm</li>
</ol>
```

---

### Overlay & Disclosure

#### Modal (= Dialog)
```html
<dialog id="confirm-dialog" aria-labelledby="dialog-title" aria-describedby="dialog-desc">
  <h2 id="dialog-title">Delete project?</h2>
  <p id="dialog-desc">This action cannot be undone.</p>
  <div class="dialog__actions">
    <button type="button" class="btn btn--danger" autofocus>Delete</button>
    <button type="button" class="btn btn--secondary">Cancel</button>
  </div>
</dialog>
```
- Use native `<dialog>` element (JS: `dialog.showModal()` / `dialog.close()`)
- Focus management: first focusable element (or close button) on open
- Focus trap: Tab cycles within dialog only
- Close: Escape key, close button, backdrop click (optional)
- `aria-modal="true"` if not using native `<dialog>`

#### Drawer (= Tray / Sheet / Flyout)
- Same as Modal but positioned at edge of screen
- `role="dialog"` + `aria-label` + focus trap + Escape to close

#### Popover
```html
<button type="button" aria-expanded="false" aria-controls="menu-popup" id="menu-trigger">
  Options
</button>
<div id="menu-popup" role="menu" aria-labelledby="menu-trigger" hidden>
  <button type="button" role="menuitem">Edit</button>
  <button type="button" role="menuitem">Duplicate</button>
  <button type="button" role="menuitem" class="danger">Delete</button>
</div>
```

#### Tooltip / Toggletip
```html
<!-- Hover tooltip (non-interactive) -->
<button type="button" aria-describedby="tip-1">
  <svg aria-hidden="true" class="feather feather-info"><use href="/icons/feather-sprite.svg#info"/></svg>
  <span class="sr-only">More info</span>
</button>
<div id="tip-1" role="tooltip" hidden>
  This field is required for billing.
</div>
```
- Tooltip: triggered by hover/focus; non-interactive content only
- Toggletip: triggered by click; can contain interactive elements (use popover pattern)

---

### Display & Content

#### Badge (= Tag / Label / Chip)
```html
<span class="badge badge--success">Active</span>
<span class="badge badge--warning">Pending</span>
<span class="badge badge--error">Failed</span>
```
- Never use emoji (✅ ⚠️ ❌) — use CSS `::before` with background-color or Feather icon
- Avoid color as only differentiator (WCAG 1.4.1)

#### Avatar
```html
<!-- With image -->
<img src="/avatar/user-1.jpg" alt="Alice Martin" width="40" height="40"
     class="avatar" style="border-radius: 50%">

<!-- Fallback initials -->
<span class="avatar" aria-label="Alice Martin">AM</span>
```

#### Card (= Tile)
```html
<article class="card">
  <img src="..." alt="[descriptive alt text]" class="card__image">
  <div class="card__body">
    <h3 class="card__title"><a href="...">Article title</a></h3>
    <p class="card__desc">Summary text...</p>
  </div>
  <footer class="card__footer">
    <time datetime="2024-01-15">Jan 15, 2024</time>
  </footer>
</article>
```

#### Table (= Data Table)
```html
<table>
  <caption class="sr-only">Project list</caption>
  <thead>
    <tr>
      <th scope="col">Name</th>
      <th scope="col" aria-sort="ascending">Status</th>
      <th scope="col">Actions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Trainr</td>
      <td><span class="badge badge--success">Active</span></td>
      <td>
        <button type="button" aria-label="Edit Trainr">
          <svg aria-hidden="true" class="feather feather-edit-2"><use href="/icons/feather-sprite.svg#edit-2"/></svg>
        </button>
      </td>
    </tr>
  </tbody>
</table>
```

#### Empty State
```html
<div class="empty-state" role="status">
  <svg aria-hidden="true" class="feather feather-inbox" style="width:48px;height:48px">
    <use href="/icons/feather-sprite.svg#inbox"/>
  </svg>
  <h3>No projects yet</h3>
  <p>Get started by creating your first project.</p>
  <button type="button" class="btn btn--primary">
    <svg aria-hidden="true" class="feather feather-plus"><use href="/icons/feather-sprite.svg#plus"/></svg>
    New project
  </button>
</div>
```

---

## 3. ICON SYSTEM — FEATHER ICONS

**Source**: https://feathericons.com | MIT License | v4.29.0
**287 icons**, 24×24 grid, stroke-based, no fill.

### Install
```bash
npm install feather-icons
# or CDN: https://unpkg.com/feather-icons/dist/feather-sprite.svg
```

### Base CSS
```css
.feather {
  width: 1em;           /* scales with font-size */
  height: 1em;
  stroke: currentColor; /* inherits text color */
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  fill: none;
  flex-shrink: 0;       /* don't shrink in flex containers */
  vertical-align: middle;
}

/* Size variants */
.feather--sm { width: 16px; height: 16px; }
.feather--md { width: 20px; height: 20px; }  /* default */
.feather--lg { width: 24px; height: 24px; }
.feather--xl { width: 32px; height: 32px; }
```

### SVG Sprite Usage (recommended)
```html
<!-- Include once in <body> or as external reference -->
<svg xmlns="http://www.w3.org/2000/svg" hidden>
  <defs><!-- sprite content --></defs>
</svg>

<!-- Usage -->
<svg class="feather feather-[name]" aria-hidden="true" focusable="false">
  <use href="/assets/feather-sprite.svg#[icon-name]"/>
</svg>
```

### Accessibility Rules
```html
<!-- Decorative icon (next to text): aria-hidden -->
<button>
  <svg aria-hidden="true" focusable="false" class="feather feather-save">
    <use href="feather-sprite.svg#save"/>
  </svg>
  Save
</button>

<!-- Standalone icon (no visible text): needs label -->
<button aria-label="Close">
  <svg aria-hidden="true" focusable="false" class="feather feather-x">
    <use href="feather-sprite.svg#x"/>
  </svg>
</button>

<!-- Never: emoji or text symbols as icons -->
<!-- ❌ BAD: <button>💾 Save</button>  -->
<!-- ❌ BAD: <span>⚠️</span>            -->
```

### Key Icons Catalogue (SF usage)

| Use case | Feather name | Notes |
|----------|-------------|-------|
| Close / dismiss | `x` | Modal, toast, drawer |
| Alert / error | `alert-circle` | Notifications, form errors |
| Warning | `alert-triangle` | Caution states |
| Success / check | `check-circle` | Completion, success toast |
| Info | `info` | Help, informational |
| Add / create | `plus` | Buttons, empty state CTA |
| Edit | `edit-2` | Table actions |
| Delete | `trash-2` | Destructive action |
| Save | `save` | Form submit hint |
| Search | `search` | Search input |
| Settings | `settings` | Config pages |
| User | `user` | Profile, avatar fallback |
| Users | `users` | Team, members |
| Home | `home` | Navigation |
| Dashboard | `grid` | Dashboard nav |
| Files | `file-text` | Documents |
| Folder | `folder` | Directory |
| Upload | `upload` | File input |
| Download | `download` | Export |
| External link | `external-link` | Opens new tab |
| Copy | `copy` | Clipboard |
| Refresh / retry | `refresh-cw` | Retry, sync |
| Offline | `wifi-off` | Network error state |
| Loading | Use Spinner SVG | Not a Feather icon |
| Back | `arrow-left` | Navigation |
| Forward | `arrow-right` | Next step |
| Expand / more | `chevron-down` | Accordion, select |
| Collapse | `chevron-up` | Collapse state |
| Menu | `menu` | Hamburger |
| Notification | `bell` | Alert bell |
| Notification off | `bell-off` | Muted |
| Calendar | `calendar` | Date picker |
| Clock | `clock` | Time, history |
| Lock | `lock` | Security, protected |
| Eye | `eye` | Show password |
| Eye off | `eye-off` | Hide password |
| Star | `star` | Favorite, rating |
| Heart | `heart` | Like |
| Share | `share-2` | Share action |
| Filter | `filter` | Filter list |
| Sort | `bar-chart-2` | Sort indicator |
| Drag | `move` | Draggable item |
| Ellipsis | `more-horizontal` | Context menu trigger |
| Log out | `log-out` | Logout button |
| Log in | `log-in` | Login button |
| Mail | `mail` | Email |
| Phone | `phone` | Contact |
| Code | `code` | Developer mode |
| Terminal | `terminal` | CLI/shell |
| GitHub | `github` | Repo link |
| Globe | `globe` | Website, language |
| AI / Bot | `cpu` | AI/LLM indicator |
| Checkmark | `check` | Inline success |

---

## 4. TOKEN SYSTEM — COMPLETE REFERENCE

### tokens.css (complete template)

```css
/* ================================================================
   TOKENS.CSS — SF Design System
   Source of truth for all design values.
   NEVER hardcode these values in component files.
   ================================================================ */

:root {

  /* ── COLOR PALETTE (primitives) ── */
  --color-white: #ffffff;
  --color-black: #0f172a;

  /* Brand */
  --color-brand-50:  #eff6ff;
  --color-brand-100: #dbeafe;
  --color-brand-200: #bfdbfe;
  --color-brand-300: #93c5fd;
  --color-brand-400: #60a5fa;
  --color-brand-500: #3b82f6;  /* primary brand */
  --color-brand-600: #2563eb;
  --color-brand-700: #1d4ed8;
  --color-brand-800: #1e40af;
  --color-brand-900: #1e3a8a;

  /* Gray (neutral) */
  --color-gray-50:  #f8fafc;
  --color-gray-100: #f1f5f9;
  --color-gray-200: #e2e8f0;
  --color-gray-300: #cbd5e1;
  --color-gray-400: #94a3b8;
  --color-gray-500: #64748b;
  --color-gray-600: #475569;
  --color-gray-700: #334155;
  --color-gray-800: #1e293b;
  --color-gray-900: #0f172a;

  /* Semantic: success */
  --color-success-50:  #f0fdf4;
  --color-success-500: #22c55e;
  --color-success-700: #15803d;

  /* Semantic: warning */
  --color-warning-50:  #fffbeb;
  --color-warning-500: #f59e0b;
  --color-warning-700: #b45309;

  /* Semantic: error / danger */
  --color-error-50:  #fef2f2;
  --color-error-500: #ef4444;
  --color-error-700: #b91c1c;

  /* Semantic: info */
  --color-info-50:  #eff6ff;
  --color-info-500: #3b82f6;
  --color-info-700: #1d4ed8;

  /* ── TYPOGRAPHY ── */

  /* Font families */
  --font-family-sans:  -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
  --font-family-serif: 'Georgia', 'Times New Roman', serif;
  --font-family-mono:  'JetBrains Mono', 'Fira Code', 'Consolas', monospace;

  /* Font sizes (type scale: 1.25 ratio) */
  --font-size-xs:   0.75rem;   /*  12px */
  --font-size-sm:   0.875rem;  /*  14px */
  --font-size-base: 1rem;      /*  16px — body default */
  --font-size-lg:   1.125rem;  /*  18px */
  --font-size-xl:   1.25rem;   /*  20px */
  --font-size-2xl:  1.5rem;    /*  24px */
  --font-size-3xl:  1.875rem;  /*  30px */
  --font-size-4xl:  2.25rem;   /*  36px */
  --font-size-5xl:  3rem;      /*  48px */
  --font-size-6xl:  3.75rem;   /*  60px */

  /* Font weights */
  --font-weight-light:    300;
  --font-weight-regular:  400;
  --font-weight-medium:   500;
  --font-weight-semibold: 600;
  --font-weight-bold:     700;
  --font-weight-extrabold: 800;

  /* Line heights */
  --line-height-none:    1;
  --line-height-tight:   1.25;
  --line-height-snug:    1.375;
  --line-height-normal:  1.5;   /* body text */
  --line-height-relaxed: 1.625;
  --line-height-loose:   2;

  /* Letter spacing */
  --letter-spacing-tight:   -0.025em;
  --letter-spacing-normal:   0;
  --letter-spacing-wide:     0.025em;
  --letter-spacing-wider:    0.05em;
  --letter-spacing-widest:   0.1em;

  /* ── SPACING (4px base unit) ── */
  --space-0:    0;
  --space-px:   1px;
  --space-0-5:  0.125rem;  /*  2px */
  --space-1:    0.25rem;   /*  4px */
  --space-1-5:  0.375rem;  /*  6px */
  --space-2:    0.5rem;    /*  8px */
  --space-2-5:  0.625rem;  /* 10px */
  --space-3:    0.75rem;   /* 12px */
  --space-3-5:  0.875rem;  /* 14px */
  --space-4:    1rem;      /* 16px */
  --space-5:    1.25rem;   /* 20px */
  --space-6:    1.5rem;    /* 24px */
  --space-7:    1.75rem;   /* 28px */
  --space-8:    2rem;      /* 32px */
  --space-10:   2.5rem;    /* 40px */
  --space-12:   3rem;      /* 48px */
  --space-14:   3.5rem;    /* 56px */
  --space-16:   4rem;      /* 64px */
  --space-20:   5rem;      /* 80px */
  --space-24:   6rem;      /* 96px */
  --space-32:   8rem;      /* 128px */

  /* ── BORDER RADIUS ── */
  --radius-none:   0;
  --radius-sm:     0.125rem;  /* 2px */
  --radius-base:   0.25rem;   /* 4px */
  --radius-md:     0.375rem;  /* 6px */
  --radius-lg:     0.5rem;    /* 8px */
  --radius-xl:     0.75rem;   /* 12px */
  --radius-2xl:    1rem;      /* 16px */
  --radius-3xl:    1.5rem;    /* 24px */
  --radius-full:   9999px;    /* pill / circle */

  /* ── SHADOWS ── */
  --shadow-sm:  0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md:  0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg:  0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl:  0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
  --shadow-2xl: 0 25px 50px -12px rgb(0 0 0 / 0.25);
  --shadow-inner: inset 0 2px 4px 0 rgb(0 0 0 / 0.05);
  --shadow-none: none;

  /* ── Z-INDEX ── */
  --z-base:     0;
  --z-raised:   10;
  --z-dropdown: 100;
  --z-sticky:   200;
  --z-overlay:  300;
  --z-modal:    400;
  --z-toast:    500;
  --z-tooltip:  600;

  /* ── BREAKPOINTS (use in media queries, not as CSS vars) ──
     sm:  640px  — small tablet
     md:  768px  — tablet portrait
     lg:  1024px — tablet landscape / small desktop
     xl:  1280px — desktop
     2xl: 1536px — wide desktop
  */

  /* ── TRANSITIONS ── */
  --duration-75:   75ms;
  --duration-100:  100ms;
  --duration-150:  150ms;
  --duration-200:  200ms;   /* default UI transition */
  --duration-300:  300ms;
  --duration-500:  500ms;
  --duration-700:  700ms;
  --ease-in:       cubic-bezier(0.4, 0, 1, 1);
  --ease-out:      cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out:   cubic-bezier(0.4, 0, 0.2, 1);
}
```

### themes.css (light / dark / high-contrast)

```css
/* Light (default) */
[data-theme="light"], :root {
  --bg-page:       var(--color-gray-50);
  --bg-surface:    var(--color-white);
  --bg-muted:      var(--color-gray-100);
  --text-primary:  var(--color-gray-900);
  --text-secondary: var(--color-gray-600);
  --text-muted:    var(--color-gray-400);
  --text-inverse:  var(--color-white);
  --border:        var(--color-gray-200);
  --border-focus:  var(--color-brand-500);
  --interactive:   var(--color-brand-600);
  --interactive-hover: var(--color-brand-700);
  --interactive-text: var(--color-white);
  --status-success: var(--color-success-700);
  --status-warning: var(--color-warning-700);
  --status-error:   var(--color-error-700);
  --status-info:    var(--color-info-700);
}

/* Dark */
[data-theme="dark"] {
  --bg-page:       var(--color-gray-900);
  --bg-surface:    var(--color-gray-800);
  --bg-muted:      var(--color-gray-700);
  --text-primary:  var(--color-gray-50);
  --text-secondary: var(--color-gray-400);
  --text-muted:    var(--color-gray-500);
  --text-inverse:  var(--color-gray-900);
  --border:        var(--color-gray-700);
  --border-focus:  var(--color-brand-400);
  --interactive:   var(--color-brand-400);
  --interactive-hover: var(--color-brand-300);
  --interactive-text: var(--color-gray-900);
  --status-success: var(--color-success-500);
  --status-warning: var(--color-warning-500);
  --status-error:   var(--color-error-500);
  --status-info:    var(--color-info-500);
}

/* High contrast */
[data-contrast="high"] {
  --bg-page:       #000000;
  --bg-surface:    #000000;
  --text-primary:  #ffffff;
  --text-secondary: #ffffff;
  --border:        #ffffff;
  --border-focus:  #ffff00;
  --interactive:   #ffff00;
  --interactive-text: #000000;
}

/* System preference (auto) */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) { /* apply dark only when no explicit theme set */
    /* same as [data-theme="dark"] */
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 5. COMPONENT PADDING & SIZING STANDARDS

Derived from analysis of 95 design systems (component.gallery):

```
Component           Height    Padding H    Padding V    Min-width
─────────────────────────────────────────────────────────────────
Button (sm)         32px      12px         6px          64px
Button (md)         40px      16px         10px         80px   ← default
Button (lg)         48px      20px         14px         96px
Input (sm)          32px      12px         6px          160px
Input (md)          40px      12px         10px         200px  ← default
Input (lg)          48px      16px         14px         240px
Select              40px      12px         10px         160px
Textarea            auto      12px         10px         200px
Badge               20px      6px          2px          32px
Tag/Chip            24px      8px          4px          40px
Avatar (sm)         24×24     —            —            24px
Avatar (md)         32×32     —            —            32px
Avatar (lg)         40×40     —            —            40px
Avatar (xl)         48×48     —            —            48px
Toast               44px+     12px         10px         280px
Modal (dialog)      auto      24px         24px         320px
Dropdown item       36px      12px         8px          160px
Table row           48px      16px         12px         —
Card                auto      16-24px      16-24px      240px
```

Touch target minimum: **44×44px** (iOS HIG) / **48×48dp** (Material 3)

---

## 6. ANTI-PATTERNS (VETO-LEVEL VIOLATIONS)

```
❌ <div onclick="...">         → use <button>
❌ <a href="#">action</a>      → use <button>
❌ <span> as button            → use <button>
❌ cursor: pointer on button   → pointer is for links
❌ Emoji in UI: ✅ ⚠️ ❌ 🔔    → use Feather SVG icons
❌ gradient backgrounds        → solid colors from tokens only
❌ inline styles               → use CSS classes/tokens
❌ hardcoded #colors           → use var(--color-*)
❌ hardcoded px spacing        → use var(--space-*)
❌ <img> without alt           → always provide alt text
❌ Icon-only button, no label  → add aria-label or sr-only text
❌ <input> without <label>     → always link label to input
❌ Modal without focus trap    → implement focus trap
❌ Toast without dismiss       → always provide close button
❌ role="button" on <div>      → use native <button>
❌ Color as only differentiator→ add text or icon
```

---

## 7. QUICK REFERENCE — COMPONENT → SEMANTIC ELEMENT

| Component | Element | Key ARIA |
|-----------|---------|---------|
| Button | `<button>` | `type`, `aria-label` if icon-only |
| Link | `<a href>` | `aria-current="page"` for active |
| Accordion | `<button>` in `<h*>` | `aria-expanded`, `aria-controls` |
| Tabs | `<button role="tab">` | `aria-selected`, `aria-controls` |
| Modal | `<dialog>` | `aria-labelledby`, `aria-describedby` |
| Alert | `<div role="alert">` | `aria-live="assertive"` if dynamic |
| Status | `<div role="status">` | `aria-live="polite"` |
| Spinner | `<svg role="status">` | `aria-label="Loading"` |
| Form | `<form>` | `novalidate` + custom validation |
| Fieldset | `<fieldset>` + `<legend>` | for checkbox/radio groups |
| Select | `<select>` | native preferred; custom = combobox |
| Toggle | `<button role="switch">` | `aria-checked` |
| Breadcrumb | `<nav aria-label="Breadcrumb">` + `<ol>` | `aria-current="page"` on last |
| Skip link | `<a href="#main">` | First focusable element on page |
| Table | `<table>` | `scope="col\|row"` on `<th>` |
| Progress | `<div role="progressbar">` | `aria-valuenow`, `aria-valuemin`, `aria-valuemax` |
| Navigation | `<nav aria-label="...">` | `<ul role="list">` inside |
| Tooltip | `<div role="tooltip">` | triggered by `aria-describedby` |
| Empty state | `<div role="status">` | descriptive heading + CTA |
