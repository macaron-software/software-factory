---
name: design-tokens
description: >
  Guides the agent through design system token architecture and usage. Use this skill
  when defining, auditing, or implementing CSS custom properties for spacing, colors,
  typography, border-radius, shadows, and breakpoints. Covers token hierarchy, naming
  conventions, and how to audit for hardcoded values.
metadata:
  category: design
  triggers:
    - "when user asks about design tokens"
    - "when defining CSS custom properties for a design system"
    - "when auditing code for hardcoded values"
    - "when user mentions spacing scale or color palette"
    - "when setting up theme tokens"
---

# Design Tokens

This skill enables the agent to define, implement, and audit design system tokens —
the single source of truth for spacing, colors, typography, borders, shadows, and
responsive breakpoints.

## Use this skill when

- Defining a new design system's token architecture
- Implementing CSS custom properties
- Auditing code for hardcoded values that should be tokens
- Setting up dark/light theme tokens
- Reviewing token naming conventions
- Migrating from hardcoded values to tokens

## Do not use this skill when

- Implementing specific components (use design-system-implementation)
- Auditing against Figma specs (use figma-design-sync)
- Validating specific files (use token-validation)

## Instructions

### Token Hierarchy

Tokens are organized in three layers:

```
Global Tokens → Semantic Tokens → Component Tokens
  (raw values)    (purpose)         (scoped)
```

#### Layer 1: Global Tokens (Primitives)

```css
:root {
  /* Colors — raw palette */
  --color-blue-50: #eff6ff;
  --color-blue-100: #dbeafe;
  --color-blue-200: #bfdbfe;
  --color-blue-300: #93c5fd;
  --color-blue-400: #60a5fa;
  --color-blue-500: #3b82f6;
  --color-blue-600: #2563eb;
  --color-blue-700: #1d4ed8;
  --color-blue-800: #1e40af;
  --color-blue-900: #1e3a8a;

  --color-gray-50: #f8fafc;
  --color-gray-100: #f1f5f9;
  --color-gray-200: #e2e8f0;
  --color-gray-300: #cbd5e1;
  --color-gray-400: #94a3b8;
  --color-gray-500: #64748b;
  --color-gray-600: #475569;
  --color-gray-700: #334155;
  --color-gray-800: #1e293b;
  --color-gray-900: #0f172a;

  /* Spacing — 4px base unit */
  --space-0: 0;
  --space-px: 1px;
  --space-0-5: 0.125rem;  /* 2px */
  --space-1: 0.25rem;     /* 4px */
  --space-1-5: 0.375rem;  /* 6px */
  --space-2: 0.5rem;      /* 8px */
  --space-3: 0.75rem;     /* 12px */
  --space-4: 1rem;        /* 16px */
  --space-5: 1.25rem;     /* 20px */
  --space-6: 1.5rem;      /* 24px */
  --space-8: 2rem;        /* 32px */
  --space-10: 2.5rem;     /* 40px */
  --space-12: 3rem;       /* 48px */
  --space-16: 4rem;       /* 64px */
  --space-20: 5rem;       /* 80px */
  --space-24: 6rem;       /* 96px */

  /* Typography scale */
  --text-xs: 0.75rem;     /* 12px */
  --text-sm: 0.875rem;    /* 14px */
  --text-base: 1rem;      /* 16px */
  --text-lg: 1.125rem;    /* 18px */
  --text-xl: 1.25rem;     /* 20px */
  --text-2xl: 1.5rem;     /* 24px */
  --text-3xl: 1.875rem;   /* 30px */
  --text-4xl: 2.25rem;    /* 36px */
  --text-5xl: 3rem;       /* 48px */

  /* Font weights */
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;
  --font-extrabold: 800;

  /* Line heights */
  --leading-none: 1;
  --leading-tight: 1.25;
  --leading-snug: 1.375;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  --leading-loose: 2;

  /* Border radius */
  --radius-none: 0;
  --radius-sm: 0.25rem;   /* 4px */
  --radius-md: 0.5rem;    /* 8px */
  --radius-lg: 0.75rem;   /* 12px */
  --radius-xl: 1rem;      /* 16px */
  --radius-2xl: 1.5rem;   /* 24px */
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);

  /* Breakpoints (for reference — used in media queries) */
  /* --breakpoint-sm: 640px */
  /* --breakpoint-md: 768px */
  /* --breakpoint-lg: 1024px */
  /* --breakpoint-xl: 1280px */
  /* --breakpoint-2xl: 1536px */
}
```

#### Layer 2: Semantic Tokens

```css
:root {
  /* Surface colors */
  --surface-primary: var(--color-white);
  --surface-secondary: var(--color-gray-50);
  --surface-tertiary: var(--color-gray-100);

  /* Text colors */
  --text-primary: var(--color-gray-900);
  --text-secondary: var(--color-gray-600);
  --text-tertiary: var(--color-gray-400);
  --text-inverse: var(--color-white);

  /* Interactive colors */
  --interactive-primary: var(--color-blue-500);
  --interactive-primary-hover: var(--color-blue-600);
  --interactive-primary-active: var(--color-blue-700);

  /* Feedback colors */
  --color-success: var(--color-green-500);
  --color-warning: var(--color-amber-500);
  --color-error: var(--color-red-500);
  --color-info: var(--color-blue-500);

  /* Border */
  --border-default: var(--color-gray-200);
  --border-strong: var(--color-gray-300);
}
```

#### Layer 3: Component Tokens

```css
/* Scoped to a specific component */
.btn {
  --btn-padding-x: var(--space-4);
  --btn-padding-y: var(--space-2);
  --btn-radius: var(--radius-md);
  --btn-font-size: var(--text-sm);
  --btn-font-weight: var(--font-semibold);
}

.card {
  --card-padding: var(--space-6);
  --card-radius: var(--radius-lg);
  --card-shadow: var(--shadow-md);
  --card-border: var(--border-default);
}
```

### Auditing for Hardcoded Values

Search patterns to find violations:

```bash
# Hardcoded colors (hex, rgb, hsl)
grep -rn '#[0-9a-fA-F]\{3,8\}' --include='*.css' --include='*.scss'
grep -rn 'rgb\(.*\)' --include='*.css' --include='*.scss'

# Hardcoded spacing (pixel values in padding/margin/gap)
grep -rn 'padding:.*[0-9]px' --include='*.css' --include='*.scss'
grep -rn 'margin:.*[0-9]px' --include='*.css' --include='*.scss'
grep -rn 'gap:.*[0-9]px' --include='*.css' --include='*.scss'

# Hardcoded font sizes
grep -rn 'font-size:.*[0-9]px' --include='*.css' --include='*.scss'
grep -rn 'font-size:.*[0-9]rem' --include='*.css' --include='*.scss'

# Hardcoded border-radius
grep -rn 'border-radius:.*[0-9]px' --include='*.css' --include='*.scss'
```

### Naming Convention

```
--{category}-{property}-{variant}

Examples:
--color-primary-500
--space-4
--text-sm
--radius-md
--shadow-lg
--font-bold
--leading-normal
```

### Theme Switching

```css
/* Dark theme overrides semantic tokens only */
[data-theme='dark'] {
  --surface-primary: var(--color-gray-900);
  --surface-secondary: var(--color-gray-800);
  --text-primary: var(--color-gray-50);
  --text-secondary: var(--color-gray-300);
  --border-default: var(--color-gray-700);
}
```

## Output Format

```
## Token Audit: [File/Component]
### Hardcoded Values Found: X
| Line | Property | Value | Suggested Token |
|------|----------|-------|-----------------|
| 42 | padding | 16px | var(--space-4) |
| 58 | color | #3b82f6 | var(--color-primary) |

### Token Coverage: XX%
- Total declarations: X
- Using tokens: X
- Hardcoded: X
```

## Anti-patterns

- **NEVER** use hardcoded values when a token exists
- **NEVER** create one-off tokens for a single use — use the scale
- **NEVER** skip the semantic layer — components should not reference global tokens directly
- **NEVER** use `!important` to override tokens — fix the cascade
- **NEVER** define tokens in component files — keep them in a central tokens file
- **NEVER** create tokens with pixel values in their names (e.g., `--padding-16px`)
- **NEVER** use arbitrary spacing values — stick to the 4px grid (or the defined scale)
