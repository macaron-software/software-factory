---
name: ux-best-practices
description: >
  Guides the agent through UX best practices for web applications. Use this skill
  when implementing loading states, error states, empty states, form UX, keyboard
  navigation, touch targets, progressive disclosure, and microcopy. Ensures every
  user-facing state is intentionally designed.
metadata:
  category: design
  triggers:
    - "when user asks about loading or error states"
    - "when implementing form validation UX"
    - "when user mentions empty states or zero-data views"
    - "when improving user experience of a feature"
    - "when user asks about touch targets or mobile UX"
---

# UX Best Practices

This skill enables the agent to implement polished user experience patterns for every
state a user encounters — loading, error, empty, form interactions, keyboard navigation,
touch interfaces, and microcopy.

## Use this skill when

- Implementing loading states (skeleton screens, spinners)
- Designing error recovery flows (retry, fallback)
- Creating empty states (first-time, no results, error)
- Building forms with inline validation
- Ensuring keyboard accessibility
- Optimizing for touch/mobile interfaces
- Writing microcopy (button labels, hints, error messages)

## Do not use this skill when

- Creating visual designs from scratch (use frontend-design)
- Conducting a full UX audit (use ux-audit)
- Testing user flows (use e2e-browser-testing)

## Instructions

### Loading States

#### Skeleton Screens (preferred for content)

```html
<div class="card card--skeleton" aria-busy="true" aria-label="Loading content">
  <div class="skeleton skeleton--avatar"></div>
  <div class="skeleton skeleton--text" style="width: 60%"></div>
  <div class="skeleton skeleton--text" style="width: 80%"></div>
  <div class="skeleton skeleton--text" style="width: 45%"></div>
</div>

<style>
  .skeleton {
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: var(--radius-sm);
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  .skeleton--avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
  }
  .skeleton--text {
    height: 16px;
    margin: 8px 0;
  }
</style>
```

#### Spinner (for actions/transitions)

```typescript
function LoadingButton({ isLoading, children, ...props }: LoadingButtonProps) {
  return (
    <button disabled={isLoading} {...props}>
      {isLoading ? (
        <>
          <Spinner size="sm" aria-hidden="true" />
          <span className="sr-only">Loading...</span>
        </>
      ) : children}
    </button>
  );
}
```

#### Loading Guidelines

- Use **skeleton screens** for initial page/content loads
- Use **spinners** for action feedback (save, submit)
- Use **progress bars** for operations with known duration
- Show loading within **300ms** — don't flash for fast operations
- Always provide `aria-busy="true"` during loading

### Error States

```typescript
// Three types of error states
function ErrorState({ type, onRetry }: ErrorProps) {
  switch (type) {
    case 'network':
      return (
        <div role="alert" className="error-state">
          <Icon name="wifi-off" />
          <h3>Connection lost</h3>
          <p>Check your internet connection and try again.</p>
          <Button onClick={onRetry}>Retry</Button>
        </div>
      );
    case 'server':
      return (
        <div role="alert" className="error-state">
          <Icon name="server-error" />
          <h3>Something went wrong</h3>
          <p>We're working on fixing this. Please try again in a moment.</p>
          <Button onClick={onRetry}>Try Again</Button>
        </div>
      );
    case 'not-found':
      return (
        <div className="error-state">
          <Icon name="search-off" />
          <h3>Page not found</h3>
          <p>The page you're looking for doesn't exist or has been moved.</p>
          <Button href="/">Go Home</Button>
        </div>
      );
  }
}
```

### Empty States

```typescript
function EmptyState({ context }: { context: 'first-time' | 'no-results' | 'filtered' }) {
  switch (context) {
    case 'first-time':
      return (
        <div className="empty-state">
          <Illustration name="getting-started" />
          <h3>No projects yet</h3>
          <p>Create your first project to get started.</p>
          <Button variant="primary">Create Project</Button>
        </div>
      );
    case 'no-results':
      return (
        <div className="empty-state">
          <Icon name="search" />
          <h3>No results found</h3>
          <p>Try adjusting your search or filters.</p>
          <Button variant="ghost" onClick={clearFilters}>Clear Filters</Button>
        </div>
      );
    case 'filtered':
      return (
        <div className="empty-state">
          <Icon name="filter" />
          <h3>No matching items</h3>
          <p>No items match the current filter criteria.</p>
        </div>
      );
  }
}
```

### Form UX

```typescript
// Inline validation — validate on blur, clear on change
function EmailField() {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const [touched, setTouched] = useState(false);

  const validate = (email: string) => {
    if (!email) return 'Email is required';
    if (!email.includes('@')) return 'Enter a valid email address';
    return '';
  };

  return (
    <div className="form-field">
      <label htmlFor="email">Email address</label>
      <input
        id="email"
        type="email"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          if (touched) setError(''); // Clear error on change
        }}
        onBlur={() => {
          setTouched(true);
          setError(validate(value)); // Validate on blur
        }}
        aria-invalid={!!error}
        aria-describedby={error ? 'email-error' : undefined}
      />
      {error && (
        <span id="email-error" className="field-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
```

#### Form UX Rules

- Validate on **blur** (not on every keystroke)
- Clear errors **on change** (give immediate feedback)
- Show errors **inline** next to the field (not at top of form)
- Use `aria-invalid` and `role="alert"` for screen readers
- Disable submit button only when submitting (not for validation)
- Show password requirements **before** the user types

### Touch Targets

```css
/* Minimum 44×44px touch targets (WCAG 2.5.5) */
.btn,
.link,
.checkbox,
.radio,
input[type="checkbox"],
input[type="radio"] {
  min-width: 44px;
  min-height: 44px;
}

/* Use padding to expand small elements */
.small-icon-button {
  padding: 12px; /* Even if icon is 20px, total = 44px */
}

/* Spacing between touch targets: at least 8px */
.action-buttons {
  gap: var(--space-2); /* 8px minimum */
}
```

### Progressive Disclosure

```typescript
// Show advanced options only when needed
function SettingsForm() {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <form>
      {/* Primary settings always visible */}
      <Field label="Name" name="name" />
      <Field label="Email" name="email" />

      {/* Advanced settings hidden by default */}
      <button
        type="button"
        aria-expanded={showAdvanced}
        onClick={() => setShowAdvanced(!showAdvanced)}
      >
        {showAdvanced ? 'Hide' : 'Show'} advanced settings
      </button>

      {showAdvanced && (
        <fieldset>
          <legend>Advanced Settings</legend>
          <Field label="API Key" name="apiKey" />
          <Field label="Webhook URL" name="webhookUrl" />
        </fieldset>
      )}
    </form>
  );
}
```

### Microcopy Guidelines

| Context | ❌ Bad         | ✅ Good                                     |
| ------- | -------------- | ------------------------------------------- |
| Button  | Submit         | Save Changes                                |
| Button  | Click here     | Download Report                             |
| Error   | Error occurred | Unable to save — check your connection      |
| Empty   | No data        | No projects yet — create one to get started |
| Confirm | Are you sure?  | Delete "My Project"? This can't be undone.  |
| Loading | Loading...     | Loading your dashboard...                   |
| Success | Done           | Changes saved successfully                  |

## Output Format

For each UX pattern implemented:

```
## Pattern: [Name]
- State: [loading/error/empty/form/interaction]
- Accessibility: [aria attributes, keyboard support]
- Mobile: [touch target compliance, responsive]
- Microcopy: [button labels, messages]
```

## Component Gallery Knowledge Base

Use the MCP tools `component_gallery_list` and `component_gallery_get` to access battle-tested UI component patterns from 50+ Design Systems (Material, Carbon, Atlassian, Ant, etc.).

Available components: accordion, breadcrumbs, button, button-group, carousel, pagination, popover, quote, rating, rich-text-editor, tabs, tree-view.

Each component doc includes:
- Semantic HTML markup (2+ approaches)
- ARIA attributes and keyboard interactions
- CSS state hooks (aria-expanded, etc.)
- Usage guidelines and when NOT to use
- Accessibility footnotes

Example: `component_gallery_get("accordion")` → full markup + ARIA + CSS + usage notes

## Anti-patterns

- **NEVER** show a blank screen during loading — always show skeleton or spinner
- **NEVER** show error messages without a recovery action (retry, go back)
- **NEVER** show empty states without a CTA (create, import, explore)
- **NEVER** validate on every keystroke — validate on blur
- **NEVER** disable the submit button for validation — let users click and show errors
- **NEVER** use alert() or confirm() — use inline UI
- **NEVER** make touch targets smaller than 44×44px
- **NEVER** write vague microcopy ("Error", "Loading...", "Click here")
- **NEVER** hide critical information behind progressive disclosure
