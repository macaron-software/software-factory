---
name: ui-saas-design-system
description: >
  Guides the agent through implementing the SaasApp (SAAS) PHP design system. Use this
  skill when building or modifying components that follow SAAS conventions — BEM naming
  with .saas-* prefix, CSS tokens with --saas-* prefix, atomic design principles, and
  PHP template patterns. Domain-specific to the SAAS ecosystem.
metadata:
  category: design
  triggers:
    - "when user asks to implement a SAAS component"
    - "when working with .saas-* CSS classes"
    - "when using --saas-* CSS tokens"
    - "when building SaasApp UI components"
    - "when user mentions SAAS design system"
---

# SAAS Design System (SaasApp)

This skill enables the agent to implement UI components following the SaasApp (SAAS) design
system conventions — BEM naming, CSS custom properties, atomic design, and PHP templates.

## Use this skill when

- Building new SAAS components
- Modifying existing .saas-\* styled components
- Working with --saas-\* CSS tokens
- Implementing PHP templates for SAAS components
- Auditing SAAS code for convention compliance

## Do not use this skill when

- Working on non-SAAS projects
- Creating React/Vue/Angular components (use design-system-implementation)
- Doing general accessibility audits (use accessibility-audit)

## Instructions

### BEM Naming Convention

SAAS follows strict BEM with `.saas-` prefix:

```css
/* Block */
.saas-card {
}

/* Element (double underscore) */
.saas-card__header {
}
.saas-card__body {
}
.saas-card__footer {
}
.saas-card__title {
}
.saas-card__action {
}

/* Modifier (double hyphen) */
.saas-card--elevated {
}
.saas-card--compact {
}
.saas-card--featured {
}
.saas-card__title--large {
}
```

#### Naming Rules

```
.saas-{block}
.saas-{block}__{element}
.saas-{block}--{modifier}
.saas-{block}__{element}--{modifier}
```

- Block names: lowercase, single hyphen for multi-word (`saas-user-card`)
- Element names: lowercase, single hyphen for multi-word (`saas-card__action-bar`)
- Modifier names: lowercase, single hyphen for multi-word (`saas-card--full-width`)
- **Never nest blocks**: `.saas-card .saas-button` ✅ `.saas-card__button` only if it's truly an element of card

### SAAS Token System

```css
:root {
  /* Colors */
  --saas-color-primary: #6366f1;
  --saas-color-primary-light: #818cf8;
  --saas-color-primary-dark: #4f46e5;
  --saas-color-secondary: #06b6d4;
  --saas-color-accent: #f59e0b;

  --saas-color-success: #10b981;
  --saas-color-warning: #f59e0b;
  --saas-color-error: #ef4444;
  --saas-color-info: #3b82f6;

  --saas-color-bg: #ffffff;
  --saas-color-bg-alt: #f8fafc;
  --saas-color-surface: #ffffff;
  --saas-color-surface-raised: #f1f5f9;

  --saas-color-text: #1e293b;
  --saas-color-text-secondary: #64748b;
  --saas-color-text-muted: #94a3b8;
  --saas-color-text-inverse: #ffffff;

  --saas-color-border: #e2e8f0;
  --saas-color-border-strong: #cbd5e1;

  /* Spacing (4px base grid) */
  --saas-space-1: 0.25rem; /* 4px */
  --saas-space-2: 0.5rem; /* 8px */
  --saas-space-3: 0.75rem; /* 12px */
  --saas-space-4: 1rem; /* 16px */
  --saas-space-5: 1.25rem; /* 20px */
  --saas-space-6: 1.5rem; /* 24px */
  --saas-space-8: 2rem; /* 32px */
  --saas-space-10: 2.5rem; /* 40px */
  --saas-space-12: 3rem; /* 48px */
  --saas-space-16: 4rem; /* 64px */

  /* Typography */
  --saas-font-family: "Inter", -apple-system, sans-serif;
  --saas-font-mono: "JetBrains Mono", monospace;

  --saas-text-xs: 0.75rem;
  --saas-text-sm: 0.875rem;
  --saas-text-base: 1rem;
  --saas-text-lg: 1.125rem;
  --saas-text-xl: 1.25rem;
  --saas-text-2xl: 1.5rem;
  --saas-text-3xl: 1.875rem;

  --saas-font-normal: 400;
  --saas-font-medium: 500;
  --saas-font-semibold: 600;
  --saas-font-bold: 700;

  /* Border Radius */
  --saas-radius-sm: 0.25rem;
  --saas-radius-md: 0.5rem;
  --saas-radius-lg: 0.75rem;
  --saas-radius-xl: 1rem;
  --saas-radius-full: 9999px;

  /* Shadows */
  --saas-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --saas-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --saas-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);

  /* Transitions */
  --saas-transition-fast: 150ms ease;
  --saas-transition-normal: 250ms ease;
  --saas-transition-slow: 350ms ease;
}
```

### Atomic Design in SAAS

#### Atoms

```css
/* saas-button atom */
.saas-button {
  display: inline-flex;
  align-items: center;
  gap: var(--saas-space-2);
  padding: var(--saas-space-2) var(--saas-space-4);
  font-family: var(--saas-font-family);
  font-size: var(--saas-text-sm);
  font-weight: var(--saas-font-semibold);
  border: none;
  border-radius: var(--saas-radius-md);
  cursor: pointer;
  transition: all var(--saas-transition-fast);
}

.saas-button--primary {
  background: var(--saas-color-primary);
  color: var(--saas-color-text-inverse);
}

.saas-button--primary:hover {
  background: var(--saas-color-primary-dark);
}

.saas-button--secondary {
  background: transparent;
  color: var(--saas-color-primary);
  border: 1px solid var(--saas-color-primary);
}

.saas-button--sm {
  padding: var(--saas-space-1) var(--saas-space-3);
  font-size: var(--saas-text-xs);
}

.saas-button--lg {
  padding: var(--saas-space-3) var(--saas-space-6);
  font-size: var(--saas-text-base);
}

.saas-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

```php
<!-- saas-button.php atom template -->
<?php
function saas_button(array $props): string {
    $variant = $props['variant'] ?? 'primary';
    $size = $props['size'] ?? 'md';
    $text = htmlspecialchars($props['text'] ?? '');
    $type = $props['type'] ?? 'button';
    $disabled = isset($props['disabled']) ? ' disabled' : '';
    $icon = $props['icon'] ?? '';

    $classes = "saas-button saas-button--{$variant}";
    if ($size !== 'md') {
        $classes .= " saas-button--{$size}";
    }

    $iconHtml = $icon ? '<span class="saas-button__icon">' . $icon . '</span>' : '';

    return <<<HTML
    <button type="{$type}" class="{$classes}"{$disabled}>
        {$iconHtml}
        <span class="saas-button__label">{$text}</span>
    </button>
    HTML;
}
?>
```

#### Molecules

```php
<!-- saas-search-bar.php molecule -->
<?php
function saas_search_bar(array $props): string {
    $placeholder = htmlspecialchars($props['placeholder'] ?? 'Rechercher...');
    $action = htmlspecialchars($props['action'] ?? '/search');

    return <<<HTML
    <form class="saas-search-bar" action="{$action}" method="GET" role="search">
        <div class="saas-search-bar__input-wrapper">
            <span class="saas-search-bar__icon" aria-hidden="true">🔍</span>
            <input
                class="saas-search-bar__input saas-input"
                type="search"
                name="q"
                placeholder="{$placeholder}"
                aria-label="Search"
            />
        </div>
        {$this->saas_button(['variant' => 'primary', 'size' => 'sm', 'text' => 'Search', 'type' => 'submit'])}
    </form>
    HTML;
}
?>
```

```css
.saas-search-bar {
  display: flex;
  align-items: center;
  gap: var(--saas-space-2);
}

.saas-search-bar__input-wrapper {
  position: relative;
  flex: 1;
}

.saas-search-bar__icon {
  position: absolute;
  left: var(--saas-space-3);
  top: 50%;
  transform: translateY(-50%);
}

.saas-search-bar__input {
  padding-left: var(--saas-space-10);
}
```

#### Organisms

```php
<!-- saas-header.php organism -->
<?php
function saas_header(array $props): string {
    $logo = $props['logo'] ?? '';
    $user = $props['user'] ?? null;

    return <<<HTML
    <header class="saas-header" role="banner">
        <div class="saas-header__container">
            <a class="saas-header__logo" href="/" aria-label="Home">
                {$logo}
            </a>
            <nav class="saas-header__nav" aria-label="Main navigation">
                {$this->saas_nav_links($props['links'] ?? [])}
            </nav>
            <div class="saas-header__actions">
                {$this->saas_search_bar(['placeholder' => 'Search...'])}
                {$user ? $this->saas_user_menu($user) : $this->saas_button(['text' => 'Sign In', 'variant' => 'secondary'])}
            </div>
        </div>
    </header>
    HTML;
}
?>
```

### Dark Theme

```css
[data-saas-theme="dark"] {
  --saas-color-bg: #0f172a;
  --saas-color-bg-alt: #1e293b;
  --saas-color-surface: #1e293b;
  --saas-color-surface-raised: #334155;
  --saas-color-text: #f1f5f9;
  --saas-color-text-secondary: #94a3b8;
  --saas-color-text-muted: #64748b;
  --saas-color-border: #334155;
  --saas-color-border-strong: #475569;
}
```

### File Organization

```
saas/
├── tokens/
│   ├── _colors.css
│   ├── _spacing.css
│   ├── _typography.css
│   └── _index.css          # imports all tokens
├── atoms/
│   ├── saas-button.css
│   ├── saas-button.php
│   ├── saas-input.css
│   ├── saas-input.php
│   ├── saas-badge.css
│   └── saas-badge.php
├── molecules/
│   ├── saas-search-bar.css
│   ├── saas-search-bar.php
│   ├── saas-card.css
│   └── saas-card.php
├── organisms/
│   ├── saas-header.css
│   ├── saas-header.php
│   └── saas-footer.php
└── saas.css                  # main entry point
```

## Output Format

```
## SAAS Component: [Name]
- BEM class: .saas-[block]
- Tokens used: [list]
- Template: [php file path]
- Stylesheet: [css file path]
- States: [default, hover, focus, disabled, ...]
- Responsive: [breakpoints]
```

## Anti-patterns

- **NEVER** use CSS classes without the `saas-` prefix in SAAS components
- **NEVER** use CSS tokens without the `--saas-` prefix
- **NEVER** nest BEM elements (`.saas-card__header__title` is WRONG → use `.saas-card__title`)
- **NEVER** use inline styles in PHP templates
- **NEVER** hardcode colors, spacing, or font sizes — use `--saas-*` tokens
- **NEVER** mix SAAS and non-SAAS styling conventions in the same component
- **NEVER** skip the `htmlspecialchars()` call for user-provided text in PHP
- **NEVER** forget ARIA attributes in PHP templates
