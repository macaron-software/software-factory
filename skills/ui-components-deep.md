# UI Components & Design Tokens — Deep Skill
# Source: component.gallery (60 components, 95 design systems, 2676 examples)

## WHEN TO ACTIVATE
Creating UI components, reviewing component implementations, building design systems,
writing CSS/HTML/templates, or any frontend development work.

## ATOMIC DESIGN LEVELS
- **Atoms**: Button, Badge, Icon, Label, Link, Input, Separator, Spacer, Toggle, Heading, Image
- **Molecules**: Accordion, Alert, Avatar, Breadcrumb, Card, Combobox, DatePicker, Drawer,
  Dropdown, EmptyState, Fieldset, FileUpload, Pagination, Popover, ProgressBar,
  ProgressTracker, Radio, Rating, Search, SegmentedControl, Select, Skeleton,
  Slider, Spinner, Stepper, Tabs, Toast, Tooltip
- **Organisms**: Carousel, DataTable, Footer, Form, Header, Hero, Modal, Navigation,
  RichTextEditor, TreeView, VideoPlayer

## ICON SYSTEM
RULE: SVG Feather icons ONLY. No emoji. No FontAwesome. No Material Icons.
```html
<!-- CORRECT -->
<svg class="icon" width="16" height="16"><use href="/icons/feather-sprite.svg#check"/></svg>
<!-- NEVER -->
<span>✅</span>  <!-- NO emoji -->
<i class="fa fa-check"></i>  <!-- NO FontAwesome -->
```

## 60 COMPONENTS — Implementation Rules

### Navigation Components
1. **Breadcrumb** — `<nav aria-label="Breadcrumb"><ol>` with `aria-current="page"` on last item
2. **Navigation** — `<nav>` landmark with `aria-label`. Mobile: hamburger with disclosure pattern
3. **Pagination** — `<nav aria-label="Pagination">`. Show current/total. Keyboard: Tab between links
4. **Skip Link** — First focusable element. `<a href="#main-content" class="skip-link">`
5. **Tabs** — `role="tablist"` + `role="tab"` + `role="tabpanel"`. Arrow keys between tabs. Tab into panel

### Input Components
6. **Button** — Semantic `<button>`. Never `<div onclick>`. `aria-pressed` for toggles. Min 44x44px
7. **Checkbox** — `<input type="checkbox">` + `<label>`. Tri-state: `aria-checked="mixed"`
8. **Combobox** — Input + listbox. `aria-expanded`, `aria-activedescendant`. Filter on type
9. **Color Picker** — Composed of: input + preview + palette. Label required
10. **Date Input** — 3 fields (day/month/year) or single with pattern. Localized format
11. **Date Picker** — Calendar grid. `role="grid"`. Arrow keys navigate days. Month/year controls
12. **File Upload** — `<input type="file">` or drag-drop zone. Show file name, size, progress, cancel
13. **Radio** — `<fieldset>` + `<legend>` + `<input type="radio">`. Arrow keys within group
14. **Search** — `<input type="search">` inside `<form role="search">`. Clear button. Autocomplete
15. **Segmented Control** — Visually a button group, semantically a radio group. `role="radiogroup"`
16. **Select** — `<select>` native or custom listbox. Custom: `role="listbox"` + `role="option"`
17. **Slider** — `<input type="range">` or `role="slider"`. `aria-valuenow/min/max`. Keyboard: arrows
18. **Stepper** — +/- buttons + numeric display. `role="spinbutton"`. Arrow keys increment/decrement
19. **Text Input** — `<input>` with `<label>`. Error: `aria-invalid="true"` + `aria-describedby` error msg
20. **Textarea** — `<textarea>` with `<label>`. Auto-resize. Character count if max
21. **Toggle/Switch** — `role="switch"` + `aria-checked`. Space/Enter to toggle

### Display Components
22. **Accordion** — `<button aria-expanded>` + `<div role="region">`. One or multi-open
23. **Alert** — `role="alert"` for urgent, `role="status"` for updates. Auto-announced by SR
24. **Avatar** — `<img>` with `alt="User name"` or initials in `<span aria-label="User name">`
25. **Badge** — Inline `<span>`. For status: use color + text (not color alone — a11y)
26. **Card** — `<article>` or `<div>`. Clickable card: single `<a>` wrapping or `::after` pseudo
27. **Carousel** — `role="region" aria-roledescription="carousel"`. Pause/play. Not auto-advancing
28. **Empty State** — Illustration + message + CTA. Guide user to next action
29. **Heading** — Proper hierarchy: h1 > h2 > h3. Never skip levels. One h1 per page
30. **Hero** — Full-width banner. Ensure text contrast over images. `role="img"` + `aria-label` on decorative bg
31. **Icon** — SVG Feather only. `aria-hidden="true"` if decorative. `aria-label` if meaningful
32. **Image** — Always `alt`. Decorative: `alt=""` + `role="presentation"`. Lazy load below fold
33. **List** — Semantic `<ul>/<ol>/<dl>`. For interactive: `role="listbox"` or `role="list"`
34. **Quote** — `<blockquote>` + `<cite>` for source
35. **Separator** — `<hr>` or `role="separator"`. `aria-orientation` for vertical
36. **Spacer** — CSS-only. Never use for layout (use grid/flex gap)
37. **Table** — `<table>` with `<caption>`, `<thead>/<tbody>`, `<th scope>`. Sortable: `aria-sort`
38. **Tree View** — `role="tree"` + `role="treeitem"`. `aria-expanded`. Arrow keys navigate
39. **Video Player** — `<video>` with captions track. Controls keyboard accessible

### Feedback Components
40. **Modal/Dialog** — `role="dialog"` + `aria-modal="true"`. Focus trap. Esc to close. Return focus
41. **Drawer** — Side panel. Same a11y as dialog. `inert` on background content
42. **Popover** — Triggered by click (not hover). `aria-haspopup`. Can contain interactive elements
43. **Progress Bar** — `role="progressbar"` + `aria-valuenow/min/max`. Or `aria-busy` for indeterminate
44. **Progress Tracker** — Stepper with statuses. `aria-current="step"` on current. Completed: checkmark
45. **Rating** — Group of radio buttons or readonly display. `aria-label="Rating: 4 out of 5"`
46. **Skeleton** — Grey shimmer placeholders matching content layout. `aria-busy="true"` on container
47. **Spinner** — `role="status"` + `aria-label="Loading"`. Visually: CSS animation, no GIF
48. **Toast** — `role="status"` or `role="alert"`. Auto-dismiss with timer. Action button optional
49. **Tooltip** — `role="tooltip"` + `aria-describedby`. Appears on hover AND focus. Esc to dismiss
50. **Visually Hidden** — `.sr-only` class. `clip: rect(0 0 0 0)` + `position: absolute`

### Layout Components
51. **Footer** — `<footer>` landmark. Links, copyright, legal
52. **Form** — `<form>` with `action`. Fieldset grouping. Submit button. Validation on submit
53. **Header** — `<header>` landmark. Site name, nav, search, user menu
54. **Fieldset** — `<fieldset>` + `<legend>`. Group related inputs

## DESIGN TOKENS — SF Platform Standard

### Colors (Dark Theme — WCAG AA compliant)
```css
--bg-primary: #0f0a1a;    --bg-secondary: #1a1425;   --bg-card: #201a2e;
--purple: #a855f7;         --purple-light: #c084fc;    --purple-dark: #7c3aed;
--success: #10b981;        --warning: #f59e0b;         --error: #ef4444;
--info: #3b82f6;           --text-primary: #f8f8ff;    --text-secondary: #a0a0b8;
--text-muted: #6b7280;     --border: #2a2040;          --border-hover: #3d3555;
```

### Typography
```css
--font-family: 'JetBrains Mono', monospace;
--font-size-xs: 0.75rem;   --font-size-sm: 0.875rem;  --font-size-base: 1rem;
--font-size-lg: 1.125rem;  --font-size-xl: 1.25rem;   --font-size-2xl: 1.5rem;
--font-size-3xl: 1.875rem; --line-height: 1.6;
--font-weight-normal: 400; --font-weight-medium: 500;  --font-weight-bold: 700;
```

### Spacing & Padding
```css
--space-xs: 0.25rem;  --space-sm: 0.5rem;  --space-md: 1rem;
--space-lg: 1.5rem;   --space-xl: 2rem;    --space-2xl: 3rem;
--pad-xs: 0.25rem;    --pad-sm: 0.5rem;    --pad-md: 0.75rem 1rem;
--pad-lg: 1rem 1.5rem; --pad-xl: 1.5rem 2rem;
```

### Border Radius
```css
--radius-sm: 0.25rem; --radius-md: 0.5rem; --radius-lg: 0.75rem;
--radius-xl: 1rem;    --radius-full: 9999px;
```

### Shadows & Animations
```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
--shadow-md: 0 4px 12px rgba(0,0,0,0.4);
--shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
--transition-fast: 150ms ease;   --transition-base: 300ms ease;
--transition-slow: 500ms ease;   --shimmer-duration: 1.5s;
```

### Z-Index Scale
```css
--z-dropdown: 100; --z-sticky: 200; --z-modal: 300; --z-toast: 400; --z-tooltip: 500;
```

## SKELETON LOADING PATTERN
Every component with `has_skeleton=1` MUST have a skeleton variant:
```html
<div class="sk" aria-busy="true">
  <div class="sk-line lg"></div>
  <div class="sk-line md"></div>
  <div class="sk-line sm"></div>
</div>
```
CSS: `.sk` shimmer gradient 1.5s infinite. `.sk-loaded` fade-in 0.3s.
Skeleton shape MUST match content layout (not generic spinner).

## ANTI-PATTERNS
- `<div>` with click handler instead of `<button>` — inaccessible
- Emoji as icons — inconsistent cross-platform, no a11y control
- `!important` in component CSS — specificity war
- Hardcoded hex colors instead of CSS variables — unmaintainable
- `linear-gradient` for decorative backgrounds — adversarial CODE_SLOP
- Fixed pixel sizes instead of rem — breaks zoom/a11y
- z-index: 9999 — use token scale
- Inline styles — use CSS classes
