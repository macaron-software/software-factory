---
name: token-validation
description: >
  Guides the agent through validating that CSS/SCSS files use design tokens instead
  of hardcoded values. Use this skill when scanning files for magic numbers, hex colors,
  and pixel values that should reference design system tokens. Produces a detailed
  compliance report.
metadata:
  category: design
  triggers:
    - "when user asks to validate token usage in a file"
    - "when scanning for hardcoded CSS values"
    - "when checking design system compliance"
    - "when user asks about magic numbers in CSS"
    - "when auditing a stylesheet for token violations"
---

# Token Validation

This skill enables the agent to scan CSS/SCSS files for hardcoded values that should
be design tokens, producing a compliance report with specific line numbers and
suggested token replacements.

## Use this skill when

- Validating a specific file or set of files for token compliance
- PR review — checking new CSS for hardcoded values
- Migrating legacy CSS to use design tokens
- Enforcing design system adoption
- Pre-release compliance check

## Do not use this skill when

- Defining or creating tokens (use design-tokens)
- Auditing against Figma specs (use figma-design-sync)
- Creating visual components (use design-system-implementation)

## Instructions

### Validation Rules

#### Rule 1: No Hardcoded Colors

```css
/* ❌ VIOLATION */
.card {
  background: #f8fafc;
}
.text {
  color: rgb(15, 23, 42);
}

/* ✅ CORRECT */
.card {
  background: var(--surface-secondary);
}
.text {
  color: var(--text-primary);
}
```

**Exception**: `transparent`, `inherit`, `currentColor`, `none` are allowed.

#### Rule 2: No Hardcoded Spacing

```css
/* ❌ VIOLATION */
.card {
  padding: 16px;
  margin-bottom: 24px;
  gap: 12px;
}

/* ✅ CORRECT */
.card {
  padding: var(--space-4);
  margin-bottom: var(--space-6);
  gap: var(--space-3);
}
```

**Exception**: `0`, `1px` (for borders), `100%`, `auto` are allowed.

#### Rule 3: No Hardcoded Font Sizes

```css
/* ❌ VIOLATION */
h1 {
  font-size: 2.25rem;
}
p {
  font-size: 14px;
}

/* ✅ CORRECT */
h1 {
  font-size: var(--text-4xl);
}
p {
  font-size: var(--text-sm);
}
```

#### Rule 4: No Hardcoded Border Radius

```css
/* ❌ VIOLATION */
.card {
  border-radius: 8px;
}
.avatar {
  border-radius: 50%;
}

/* ✅ CORRECT */
.card {
  border-radius: var(--radius-md);
}
.avatar {
  border-radius: var(--radius-full);
}
```

**Exception**: `border-radius: 50%` can map to `var(--radius-full)`.

#### Rule 5: No Hardcoded Shadows

```css
/* ❌ VIOLATION */
.card {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* ✅ CORRECT */
.card {
  box-shadow: var(--shadow-md);
}
```

#### Rule 6: No Hardcoded Font Weights

```css
/* ❌ VIOLATION */
.title {
  font-weight: 700;
}

/* ✅ CORRECT */
.title {
  font-weight: var(--font-bold);
}
```

### Validation Script

```typescript
import fs from "fs";

interface Violation {
  line: number;
  property: string;
  value: string;
  suggestedToken: string;
  severity: "error" | "warning";
}

const PATTERNS = [
  {
    name: "Hardcoded color (hex)",
    pattern: /(color|background|border-color|fill|stroke):\s*#[0-9a-fA-F]{3,8}/,
    severity: "error" as const,
  },
  {
    name: "Hardcoded color (rgb/hsl)",
    pattern: /(color|background):\s*(rgb|hsl)a?\(/,
    severity: "error" as const,
  },
  {
    name: "Hardcoded spacing",
    pattern: /(padding|margin|gap|top|right|bottom|left):\s*\d+px/,
    severity: "error" as const,
  },
  {
    name: "Hardcoded font-size",
    pattern: /font-size:\s*\d+(px|rem)/,
    severity: "error" as const,
  },
  {
    name: "Hardcoded border-radius",
    pattern: /border-radius:\s*\d+px/,
    severity: "warning" as const,
  },
  {
    name: "Hardcoded font-weight (number)",
    pattern: /font-weight:\s*\d{3}/,
    severity: "warning" as const,
  },
];

function validateFile(filePath: string): Violation[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.split("\n");
  const violations: Violation[] = [];

  lines.forEach((line, index) => {
    // Skip lines that already use var()
    if (line.includes("var(--")) return;
    // Skip comments
    if (line.trim().startsWith("//") || line.trim().startsWith("/*")) return;

    for (const rule of PATTERNS) {
      if (rule.pattern.test(line)) {
        violations.push({
          line: index + 1,
          property: line.trim(),
          value: line.trim(),
          suggestedToken: "See token mapping",
          severity: rule.severity,
        });
      }
    }
  });

  return violations;
}
```

### Token Mapping Reference

| Hardcoded Value     | Suggested Token        |
| ------------------- | ---------------------- |
| `0px` → `4px`       | `var(--space-1)`       |
| `8px`               | `var(--space-2)`       |
| `12px`              | `var(--space-3)`       |
| `16px`              | `var(--space-4)`       |
| `24px`              | `var(--space-6)`       |
| `32px`              | `var(--space-8)`       |
| `48px`              | `var(--space-12)`      |
| `#3b82f6`           | `var(--color-primary)` |
| `#ef4444`           | `var(--color-error)`   |
| `#10b981`           | `var(--color-success)` |
| `0.875rem` / `14px` | `var(--text-sm)`       |
| `1rem` / `16px`     | `var(--text-base)`     |
| `1.25rem` / `20px`  | `var(--text-xl)`       |
| `4px` radius        | `var(--radius-sm)`     |
| `8px` radius        | `var(--radius-md)`     |
| `12px` radius       | `var(--radius-lg)`     |
| `700` weight        | `var(--font-bold)`     |
| `600` weight        | `var(--font-semibold)` |

## Output Format

```
## Token Validation Report: [filename]
### Summary
- Total declarations scanned: X
- Violations found: X (Y errors, Z warnings)
- Token compliance: XX%

### Violations
| Line | Severity | Property | Current Value | Suggested Token |
|------|----------|----------|---------------|-----------------|
| 12 | 🔴 Error | background | #f8fafc | var(--surface-secondary) |
| 23 | 🔴 Error | padding | 16px | var(--space-4) |
| 45 | 🟡 Warning | border-radius | 8px | var(--radius-md) |
| 67 | 🟡 Warning | font-weight | 700 | var(--font-bold) |

### Auto-fixable: X of Y violations
```

## Anti-patterns

- **NEVER** flag `0`, `100%`, `auto`, `inherit`, `transparent` as violations
- **NEVER** flag values inside `var()` calls
- **NEVER** flag values in comments
- **NEVER** suggest wrong token mappings — verify the scale first
- **NEVER** auto-fix without review — some hardcoded values are intentional
- **NEVER** ignore shorthand properties (e.g., `padding: 16px 24px` has two violations)
