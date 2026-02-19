---
name: frontend-design
description: >
  Guides the agent to create visually stunning, production-grade user interfaces with
  bold aesthetic direction. Use this skill when designing or implementing frontend pages,
  components, or layouts that need to look beautiful and feel polished. Emphasizes
  typography, color theory, motion design, and spatial composition over generic templates.
metadata:
  category: design
  triggers:
    - "when user asks to create a beautiful UI"
    - "when user wants a visually polished page or component"
    - "when designing a landing page or marketing site"
    - "when user asks for creative frontend design"
    - "when the task requires aesthetic decisions beyond basic layout"
---

# Frontend Design

This skill enables the agent to create visually stunning, production-grade frontend
interfaces. Every design decision is intentional — typography creates hierarchy, color
creates emotion, space creates rhythm, and motion creates delight.

## Use this skill when

- Creating new pages or layouts that need visual polish
- Designing landing pages, hero sections, marketing content
- Building component libraries with strong visual identity
- The user wants something that looks "premium" or "beautiful"
- Implementing creative UI concepts from scratch

## Do not use this skill when

- Implementing an existing design system's components (use design-system-implementation)
- Doing accessibility audits (use accessibility-audit)
- Writing tests (use testing skills)

## Instructions

### Core Principles

1. **Every pixel is intentional** — No default styles. Every margin, color, and font choice serves a purpose.
2. **Typography is the foundation** — Choose fonts that express personality. Set a modular scale. Headlines are bold statements, not just bigger text.
3. **Color creates emotion** — Build a deliberate palette. Use contrast for hierarchy. Don't scatter colors randomly.
4. **Space is a design element** — Generous whitespace is luxurious. Cramped layouts feel cheap.
5. **Motion creates delight** — Subtle animations make interfaces feel alive. Entrance animations, hover states, micro-interactions.

### Typography System

```css
/* Define a type scale — don't use arbitrary sizes */
:root {
  --font-display: 'Cal Sans', 'Inter', system-ui, sans-serif;
  --font-body: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* Modular scale (ratio: 1.25) */
  --text-xs: 0.75rem;    /* 12px */
  --text-sm: 0.875rem;   /* 14px */
  --text-base: 1rem;     /* 16px */
  --text-lg: 1.25rem;    /* 20px */
  --text-xl: 1.563rem;   /* 25px */
  --text-2xl: 1.953rem;  /* 31px */
  --text-3xl: 2.441rem;  /* 39px */
  --text-4xl: 3.052rem;  /* 49px */
  --text-5xl: 3.815rem;  /* 61px */

  /* Line heights */
  --leading-tight: 1.15;
  --leading-snug: 1.35;
  --leading-normal: 1.6;

  /* Letter spacing */
  --tracking-tight: -0.02em;
  --tracking-normal: 0;
  --tracking-wide: 0.05em;
}

h1 {
  font-family: var(--font-display);
  font-size: var(--text-5xl);
  font-weight: 800;
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
}
```

### Color Theory

```css
:root {
  /* Build from a single hue, then expand */
  --color-primary-50: #eff6ff;
  --color-primary-100: #dbeafe;
  --color-primary-500: #3b82f6;
  --color-primary-600: #2563eb;
  --color-primary-900: #1e3a5f;

  /* Semantic colors */
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;

  /* Surface hierarchy */
  --surface-base: #ffffff;
  --surface-raised: #f8fafc;
  --surface-overlay: rgba(0, 0, 0, 0.5);

  /* Text hierarchy */
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
}
```

### Spatial Composition

```css
:root {
  /* 4px base unit — all spacing derives from this */
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */
  --space-24: 6rem;    /* 96px */
  --space-32: 8rem;    /* 128px */
}

/* Use generous spacing for premium feel */
.hero {
  padding: var(--space-32) var(--space-8);
}

.section {
  padding: var(--space-24) var(--space-8);
}

.card {
  padding: var(--space-8);
  gap: var(--space-4);
}
```

### Motion Design

```css
/* Define motion tokens */
:root {
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
}

/* Entrance animation */
@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.card {
  animation: fade-up var(--duration-slow) var(--ease-out) both;
}

/* Stagger children */
.card:nth-child(1) { animation-delay: 0ms; }
.card:nth-child(2) { animation-delay: 100ms; }
.card:nth-child(3) { animation-delay: 200ms; }

/* Hover micro-interactions */
.card {
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
}

/* Button press effect */
.button:active {
  transform: scale(0.97);
}
```

### Hero Section Template

```html
<section class="hero">
  <div class="hero-content">
    <span class="hero-badge">✨ Now in Beta</span>
    <h1 class="hero-title">
      Build something<br>
      <span class="gradient-text">extraordinary</span>
    </h1>
    <p class="hero-subtitle">
      The developer platform that makes shipping delightful.
      Focus on what matters — we handle the rest.
    </p>
    <div class="hero-actions">
      <button class="btn btn-primary btn-lg">Get Started Free</button>
      <button class="btn btn-ghost btn-lg">See Demo →</button>
    </div>
  </div>
</section>

<style>
.gradient-text {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
</style>
```

### Design Checklist

Before shipping any design:
- [ ] Typography scale is consistent (no arbitrary sizes)
- [ ] Color palette has max 3-4 hues (not a rainbow)
- [ ] Spacing follows the scale (no magic numbers)
- [ ] Interactive elements have hover/focus/active states
- [ ] Responsive from 375px to 1920px
- [ ] Animations respect `prefers-reduced-motion`
- [ ] Contrast ratios meet WCAG AA (4.5:1 body, 3:1 large)

## Output Format

When creating a design, provide:
1. Visual concept (one sentence describing the aesthetic direction)
2. Token definitions (colors, typography, spacing)
3. HTML structure
4. CSS implementation
5. Responsive considerations

## Anti-patterns

- **NEVER** use default browser styles — every element should be intentionally styled
- **NEVER** use more than 2-3 font families — restraint is sophistication
- **NEVER** scatter colors without a palette — build from a system
- **NEVER** use `!important` — fix specificity instead
- **NEVER** forget dark mode — at minimum, ensure readability
- **NEVER** use generic stock-photo aesthetics — be bold and distinctive
- **NEVER** ignore `prefers-reduced-motion` — respect user preferences
- **NEVER** sacrifice readability for aesthetics — text must be readable
- **NEVER** use tiny text (below 14px for body) or low contrast for style
