---
name: ui-ppz-design-system
description: >
  Guides the agent through implementing the Popinz (PPZ) PHP design system. Use this
  skill when building or modifying components that follow PPZ conventions — BEM naming
  with .ppz-* prefix, CSS tokens with --ppz-* prefix, atomic design principles, and
  PHP template patterns. Domain-specific to the PPZ ecosystem.
metadata:
  category: design
  triggers:
    - "when user asks to implement a PPZ component"
    - "when working with .ppz-* CSS classes"
    - "when using --ppz-* CSS tokens"
    - "when building Popinz UI components"
    - "when user mentions PPZ design system"
---

# PPZ Design System (Popinz)

This skill enables the agent to implement UI components following the Popinz (PPZ) design
system conventions — BEM naming, CSS custom properties, atomic design, and PHP templates.

## Use this skill when

- Building new PPZ components
- Modifying existing .ppz-\* styled components
- Working with --ppz-\* CSS tokens
- Implementing PHP templates for PPZ components
- Auditing PPZ code for convention compliance

## Do not use this skill when

- Working on non-PPZ projects
- Creating React/Vue/Angular components (use design-system-implementation)
- Doing general accessibility audits (use accessibility-audit)

## Instructions

### BEM Naming Convention

PPZ follows strict BEM with `.ppz-` prefix:

```css
/* Block */
.ppz-card {
}

/* Element (double underscore) */
.ppz-card__header {
}
.ppz-card__body {
}
.ppz-card__footer {
}
.ppz-card__title {
}
.ppz-card__action {
}

/* Modifier (double hyphen) */
.ppz-card--elevated {
}
.ppz-card--compact {
}
.ppz-card--featured {
}
.ppz-card__title--large {
}
```

#### Naming Rules

```
.ppz-{block}
.ppz-{block}__{element}
.ppz-{block}--{modifier}
.ppz-{block}__{element}--{modifier}
```

- Block names: lowercase, single hyphen for multi-word (`ppz-user-card`)
- Element names: lowercase, single hyphen for multi-word (`ppz-card__action-bar`)
- Modifier names: lowercase, single hyphen for multi-word (`ppz-card--full-width`)
- **Never nest blocks**: `.ppz-card .ppz-button` ✅ `.ppz-card__button` only if it's truly an element of card

### PPZ Token System

```css
:root {
  /* Colors */
  --ppz-color-primary: #6366f1;
  --ppz-color-primary-light: #818cf8;
  --ppz-color-primary-dark: #4f46e5;
  --ppz-color-secondary: #06b6d4;
  --ppz-color-accent: #f59e0b;

  --ppz-color-success: #10b981;
  --ppz-color-warning: #f59e0b;
  --ppz-color-error: #ef4444;
  --ppz-color-info: #3b82f6;

  --ppz-color-bg: #ffffff;
  --ppz-color-bg-alt: #f8fafc;
  --ppz-color-surface: #ffffff;
  --ppz-color-surface-raised: #f1f5f9;

  --ppz-color-text: #1e293b;
  --ppz-color-text-secondary: #64748b;
  --ppz-color-text-muted: #94a3b8;
  --ppz-color-text-inverse: #ffffff;

  --ppz-color-border: #e2e8f0;
  --ppz-color-border-strong: #cbd5e1;

  /* Spacing (4px base grid) */
  --ppz-space-1: 0.25rem; /* 4px */
  --ppz-space-2: 0.5rem; /* 8px */
  --ppz-space-3: 0.75rem; /* 12px */
  --ppz-space-4: 1rem; /* 16px */
  --ppz-space-5: 1.25rem; /* 20px */
  --ppz-space-6: 1.5rem; /* 24px */
  --ppz-space-8: 2rem; /* 32px */
  --ppz-space-10: 2.5rem; /* 40px */
  --ppz-space-12: 3rem; /* 48px */
  --ppz-space-16: 4rem; /* 64px */

  /* Typography */
  --ppz-font-family: "Inter", -apple-system, sans-serif;
  --ppz-font-mono: "JetBrains Mono", monospace;

  --ppz-text-xs: 0.75rem;
  --ppz-text-sm: 0.875rem;
  --ppz-text-base: 1rem;
  --ppz-text-lg: 1.125rem;
  --ppz-text-xl: 1.25rem;
  --ppz-text-2xl: 1.5rem;
  --ppz-text-3xl: 1.875rem;

  --ppz-font-normal: 400;
  --ppz-font-medium: 500;
  --ppz-font-semibold: 600;
  --ppz-font-bold: 700;

  /* Border Radius */
  --ppz-radius-sm: 0.25rem;
  --ppz-radius-md: 0.5rem;
  --ppz-radius-lg: 0.75rem;
  --ppz-radius-xl: 1rem;
  --ppz-radius-full: 9999px;

  /* Shadows */
  --ppz-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --ppz-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --ppz-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);

  /* Transitions */
  --ppz-transition-fast: 150ms ease;
  --ppz-transition-normal: 250ms ease;
  --ppz-transition-slow: 350ms ease;
}
```

### Atomic Design in PPZ

#### Atoms

```css
/* ppz-button atom */
.ppz-button {
  display: inline-flex;
  align-items: center;
  gap: var(--ppz-space-2);
  padding: var(--ppz-space-2) var(--ppz-space-4);
  font-family: var(--ppz-font-family);
  font-size: var(--ppz-text-sm);
  font-weight: var(--ppz-font-semibold);
  border: none;
  border-radius: var(--ppz-radius-md);
  cursor: pointer;
  transition: all var(--ppz-transition-fast);
}

.ppz-button--primary {
  background: var(--ppz-color-primary);
  color: var(--ppz-color-text-inverse);
}

.ppz-button--primary:hover {
  background: var(--ppz-color-primary-dark);
}

.ppz-button--secondary {
  background: transparent;
  color: var(--ppz-color-primary);
  border: 1px solid var(--ppz-color-primary);
}

.ppz-button--sm {
  padding: var(--ppz-space-1) var(--ppz-space-3);
  font-size: var(--ppz-text-xs);
}

.ppz-button--lg {
  padding: var(--ppz-space-3) var(--ppz-space-6);
  font-size: var(--ppz-text-base);
}

.ppz-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

```php
<!-- ppz-button.php atom template -->
<?php
function ppz_button(array $props): string {
    $variant = $props['variant'] ?? 'primary';
    $size = $props['size'] ?? 'md';
    $text = htmlspecialchars($props['text'] ?? '');
    $type = $props['type'] ?? 'button';
    $disabled = isset($props['disabled']) ? ' disabled' : '';
    $icon = $props['icon'] ?? '';

    $classes = "ppz-button ppz-button--{$variant}";
    if ($size !== 'md') {
        $classes .= " ppz-button--{$size}";
    }

    $iconHtml = $icon ? '<span class="ppz-button__icon">' . $icon . '</span>' : '';

    return <<<HTML
    <button type="{$type}" class="{$classes}"{$disabled}>
        {$iconHtml}
        <span class="ppz-button__label">{$text}</span>
    </button>
    HTML;
}
?>
```

#### Molecules

```php
<!-- ppz-search-bar.php molecule -->
<?php
function ppz_search_bar(array $props): string {
    $placeholder = htmlspecialchars($props['placeholder'] ?? 'Rechercher...');
    $action = htmlspecialchars($props['action'] ?? '/search');

    return <<<HTML
    <form class="ppz-search-bar" action="{$action}" method="GET" role="search">
        <div class="ppz-search-bar__input-wrapper">
            <span class="ppz-search-bar__icon" aria-hidden="true">🔍</span>
            <input
                class="ppz-search-bar__input ppz-input"
                type="search"
                name="q"
                placeholder="{$placeholder}"
                aria-label="Search"
            />
        </div>
        {$this->ppz_button(['variant' => 'primary', 'size' => 'sm', 'text' => 'Search', 'type' => 'submit'])}
    </form>
    HTML;
}
?>
```

```css
.ppz-search-bar {
  display: flex;
  align-items: center;
  gap: var(--ppz-space-2);
}

.ppz-search-bar__input-wrapper {
  position: relative;
  flex: 1;
}

.ppz-search-bar__icon {
  position: absolute;
  left: var(--ppz-space-3);
  top: 50%;
  transform: translateY(-50%);
}

.ppz-search-bar__input {
  padding-left: var(--ppz-space-10);
}
```

#### Organisms

```php
<!-- ppz-header.php organism -->
<?php
function ppz_header(array $props): string {
    $logo = $props['logo'] ?? '';
    $user = $props['user'] ?? null;

    return <<<HTML
    <header class="ppz-header" role="banner">
        <div class="ppz-header__container">
            <a class="ppz-header__logo" href="/" aria-label="Home">
                {$logo}
            </a>
            <nav class="ppz-header__nav" aria-label="Main navigation">
                {$this->ppz_nav_links($props['links'] ?? [])}
            </nav>
            <div class="ppz-header__actions">
                {$this->ppz_search_bar(['placeholder' => 'Search...'])}
                {$user ? $this->ppz_user_menu($user) : $this->ppz_button(['text' => 'Sign In', 'variant' => 'secondary'])}
            </div>
        </div>
    </header>
    HTML;
}
?>
```

### Dark Theme

```css
[data-ppz-theme="dark"] {
  --ppz-color-bg: #0f172a;
  --ppz-color-bg-alt: #1e293b;
  --ppz-color-surface: #1e293b;
  --ppz-color-surface-raised: #334155;
  --ppz-color-text: #f1f5f9;
  --ppz-color-text-secondary: #94a3b8;
  --ppz-color-text-muted: #64748b;
  --ppz-color-border: #334155;
  --ppz-color-border-strong: #475569;
}
```

### File Organization

```
ppz/
├── tokens/
│   ├── _colors.css
│   ├── _spacing.css
│   ├── _typography.css
│   └── _index.css          # imports all tokens
├── atoms/
│   ├── ppz-button.css
│   ├── ppz-button.php
│   ├── ppz-input.css
│   ├── ppz-input.php
│   ├── ppz-badge.css
│   └── ppz-badge.php
├── molecules/
│   ├── ppz-search-bar.css
│   ├── ppz-search-bar.php
│   ├── ppz-card.css
│   └── ppz-card.php
├── organisms/
│   ├── ppz-header.css
│   ├── ppz-header.php
│   └── ppz-footer.php
└── ppz.css                  # main entry point
```

## Output Format

```
## PPZ Component: [Name]
- BEM class: .ppz-[block]
- Tokens used: [list]
- Template: [php file path]
- Stylesheet: [css file path]
- States: [default, hover, focus, disabled, ...]
- Responsive: [breakpoints]
```

## Anti-patterns

- **NEVER** use CSS classes without the `ppz-` prefix in PPZ components
- **NEVER** use CSS tokens without the `--ppz-` prefix
- **NEVER** nest BEM elements (`.ppz-card__header__title` is WRONG → use `.ppz-card__title`)
- **NEVER** use inline styles in PHP templates
- **NEVER** hardcode colors, spacing, or font sizes — use `--ppz-*` tokens
- **NEVER** mix PPZ and non-PPZ styling conventions in the same component
- **NEVER** skip the `htmlspecialchars()` call for user-provided text in PHP
- **NEVER** forget ARIA attributes in PHP templates
