---
name: design-system-implementation
description: >
  Guides the agent through implementing UI components from design system specifications.
  Use this skill when building components that must follow a design system's tokens,
  patterns, and composition rules. Covers spacing tokens, color tokens, typography,
  component composition (atoms → molecules → organisms), responsive breakpoints,
  theme support, and test attributes.
metadata:
  category: design
  triggers:
    - "when user asks to implement a design system component"
    - "when building components from Figma specs"
    - "when user mentions design tokens or spacing scale"
    - "when implementing dark/light theme support"
    - "when composing atoms into molecules or organisms"
---

# Design System Implementation

This skill enables the agent to implement UI components that strictly follow design system
specifications — tokens, composition patterns, responsive behavior, and theming.

## Use this skill when

- Building new components from design system specs
- Refactoring components to use design tokens instead of hardcoded values
- Implementing responsive breakpoints per the design system
- Adding dark/light theme support
- Composing smaller components into larger patterns
- Adding data-testid attributes for testing

## Do not use this skill when

- Creating visual designs from scratch (use frontend-design)
- Auditing Figma specs (use figma-design-sync or figma-component-audit)
- Testing components (use tdd-mastery or e2e-browser-testing)

## Instructions

### Token Architecture

Design systems define tokens at multiple levels:

```css
/* Global tokens — raw values */
:root {
  --color-blue-500: #3b82f6;
  --color-gray-100: #f1f5f9;
  --space-4: 1rem;
  --radius-md: 0.5rem;
  --font-size-sm: 0.875rem;
}

/* Semantic tokens — purpose-driven aliases */
:root {
  --color-primary: var(--color-blue-500);
  --color-surface: var(--color-gray-100);
  --spacing-component-padding: var(--space-4);
  --radius-card: var(--radius-md);
  --font-size-label: var(--font-size-sm);
}

/* Component tokens — scoped to a specific component */
.btn {
  --btn-padding-x: var(--space-4);
  --btn-padding-y: var(--space-2);
  --btn-radius: var(--radius-md);
  --btn-font-size: var(--font-size-sm);

  padding: var(--btn-padding-y) var(--btn-padding-x);
  border-radius: var(--btn-radius);
  font-size: var(--btn-font-size);
}
```

### Component Composition (Atomic Design)

#### Atoms — Smallest building blocks

```typescript
// atoms/Button.tsx
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'ghost';
  size: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}

export function Button({ variant, size, children, onClick, disabled }: ButtonProps) {
  return (
    <button
      className={`btn btn--${variant} btn--${size}`}
      onClick={onClick}
      disabled={disabled}
      data-testid="button"
    >
      {children}
    </button>
  );
}
```

#### Molecules — Combinations of atoms

```typescript
// molecules/SearchBar.tsx
import { Input } from '../atoms/Input';
import { Button } from '../atoms/Button';
import { Icon } from '../atoms/Icon';

interface SearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
}

export function SearchBar({ onSearch, placeholder = 'Search...' }: SearchBarProps) {
  const [query, setQuery] = useState('');

  return (
    <div className="search-bar" data-testid="search-bar">
      <Icon name="search" className="search-bar__icon" />
      <Input
        value={query}
        onChange={setQuery}
        placeholder={placeholder}
        data-testid="search-input"
      />
      <Button variant="primary" size="sm" onClick={() => onSearch(query)}>
        Search
      </Button>
    </div>
  );
}
```

#### Organisms — Complex UI sections

```typescript
// organisms/Header.tsx
import { Logo } from '../atoms/Logo';
import { NavLinks } from '../molecules/NavLinks';
import { SearchBar } from '../molecules/SearchBar';
import { UserMenu } from '../molecules/UserMenu';

export function Header({ user, onSearch }: HeaderProps) {
  return (
    <header className="header" data-testid="header">
      <Logo />
      <NavLinks />
      <SearchBar onSearch={onSearch} />
      <UserMenu user={user} />
    </header>
  );
}
```

### Responsive Breakpoints

```css
/* Define breakpoints as tokens */
:root {
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
}

/* Mobile-first approach */
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

@media (min-width: 768px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-6);
  }
}

@media (min-width: 1024px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-8);
  }
}
```

### Dark/Light Theme Support

```css
/* Light theme (default) */
:root {
  --color-bg: #ffffff;
  --color-text: #0f172a;
  --color-surface: #f8fafc;
  --color-border: #e2e8f0;
}

/* Dark theme */
[data-theme="dark"] {
  --color-bg: #0f172a;
  --color-text: #f1f5f9;
  --color-surface: #1e293b;
  --color-border: #334155;
}

/* Components automatically adapt */
.card {
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}
```

### data-testid Convention

```
data-testid="[component]-[element]"

Examples:
data-testid="header"
data-testid="header-logo"
data-testid="search-input"
data-testid="user-menu-dropdown"
data-testid="card-title"
data-testid="modal-close-btn"
```

### Component States

Every component must handle these states:

- **Default** — normal appearance
- **Hover** — cursor over (desktop)
- **Focus** — keyboard focus (with visible indicator)
- **Active/Pressed** — being clicked/tapped
- **Disabled** — not interactive (reduced opacity, `cursor: not-allowed`)
- **Loading** — spinner or skeleton
- **Error** — error styling and message

## Output Format

```
## Component: [Name]
- Tokens used: [list of tokens]
- Composition level: atom | molecule | organism
- Responsive: [breakpoints handled]
- Theme: light ✅ dark ✅
- States: default ✅ hover ✅ focus ✅ disabled ✅ loading ✅ error ✅
- Test IDs: [list]
```

## Component Gallery Knowledge Base

Use the MCP tools `component_gallery_list` and `component_gallery_get` to access reference implementations from the Component Gallery (50+ Design Systems cross-referenced).

When building a component, call `component_gallery_get("<name>")` first to get:
- Canonical HTML structure (semantic markup)
- Required ARIA attributes
- CSS state selectors (aria-expanded, aria-selected, etc.)
- Multi-design-system naming variants

Available: accordion, breadcrumbs, button, button-group, carousel, pagination, popover, quote, rating, rich-text-editor, tabs, tree-view.

## Anti-patterns

- **NEVER** use hardcoded values (px, hex colors) — always use tokens
- **NEVER** skip component states — every interactive element needs all states
- **NEVER** forget data-testid attributes — testing depends on them
- **NEVER** build desktop-first — always start mobile-first
- **NEVER** mix design system tokens with arbitrary values in the same component
- **NEVER** create atoms that depend on organisms — dependencies flow one way
- **NEVER** duplicate token values — import from the single source of truth
- **NEVER** ignore the design system's spacing scale — no "close enough" values
