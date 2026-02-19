---
name: ux-ppz-patterns
description: >
  Guides the agent through UX patterns specific to the Popinz (PPZ) platform. Use this
  skill when implementing user experience flows, interaction patterns, and feedback
  mechanisms within the PPZ ecosystem. Covers PPZ-specific navigation, modals (popins),
  form flows, notification patterns, and the PPZ interaction language.
metadata:
  category: design
  triggers:
    - "when implementing UX patterns for the PPZ platform"
    - "when working with PPZ modals/popins"
    - "when designing PPZ navigation flows"
    - "when implementing PPZ notification patterns"
    - "when user asks about PPZ user experience"
---

# PPZ UX Patterns (Popinz)

This skill enables the agent to implement UX patterns specific to the Popinz platform,
including its modal/popin system, navigation flows, form patterns, and feedback mechanisms.

## Use this skill when

- Implementing user flows in the PPZ platform
- Working with PPZ popin (modal) system
- Building PPZ form workflows
- Implementing PPZ notification/toast patterns
- Designing PPZ navigation and routing

## Do not use this skill when

- Working on non-PPZ projects (use ux-best-practices)
- Building PPZ visual components (use ui-ppz-design-system)
- Doing general accessibility audits (use accessibility-audit)

## Instructions

### PPZ Popin (Modal) System

The PPZ platform centers around "popins" — modal-like components that are the primary
interaction pattern. The name "Popinz" comes from this core concept.

```php
<?php
function ppz_popin(array $props): string {
    $id = htmlspecialchars($props['id']);
    $title = htmlspecialchars($props['title'] ?? '');
    $size = $props['size'] ?? 'md'; // sm, md, lg, xl, full
    $content = $props['content'] ?? '';
    $closable = $props['closable'] ?? true;

    $closeBtn = $closable ? <<<HTML
    <button class="ppz-popin__close" aria-label="Close" data-ppz-close>
        <span aria-hidden="true">&times;</span>
    </button>
    HTML : '';

    return <<<HTML
    <dialog class="ppz-popin ppz-popin--{$size}" id="{$id}" aria-labelledby="{$id}-title">
        <div class="ppz-popin__header">
            <h2 class="ppz-popin__title" id="{$id}-title">{$title}</h2>
            {$closeBtn}
        </div>
        <div class="ppz-popin__body">
            {$content}
        </div>
        <div class="ppz-popin__footer" id="{$id}-footer">
        </div>
    </dialog>
    HTML;
}
?>
```

```css
.ppz-popin {
  border: none;
  border-radius: var(--ppz-radius-lg);
  box-shadow: var(--ppz-shadow-lg);
  padding: 0;
  max-height: 90vh;
  overflow: hidden;
}

.ppz-popin--sm { width: min(400px, 90vw); }
.ppz-popin--md { width: min(560px, 90vw); }
.ppz-popin--lg { width: min(720px, 90vw); }
.ppz-popin--xl { width: min(960px, 90vw); }
.ppz-popin--full { width: 90vw; height: 90vh; }

.ppz-popin__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ppz-space-4) var(--ppz-space-6);
  border-bottom: 1px solid var(--ppz-color-border);
}

.ppz-popin__body {
  padding: var(--ppz-space-6);
  overflow-y: auto;
  max-height: 60vh;
}

.ppz-popin__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--ppz-space-3);
  padding: var(--ppz-space-4) var(--ppz-space-6);
  border-top: 1px solid var(--ppz-color-border);
}

.ppz-popin::backdrop {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}
```

#### Popin JavaScript Controller

```javascript
class PpzPopin {
  constructor(dialogEl) {
    this.dialog = dialogEl;
    this.previousFocus = null;

    // Close on backdrop click
    this.dialog.addEventListener('click', (e) => {
      if (e.target === this.dialog) this.close();
    });

    // Close on Escape
    this.dialog.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.close();
    });

    // Close button
    this.dialog.querySelector('[data-ppz-close]')?.addEventListener('click', () => {
      this.close();
    });
  }

  open() {
    this.previousFocus = document.activeElement;
    this.dialog.showModal();
    // Focus first focusable element
    const firstFocusable = this.dialog.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    firstFocusable?.focus();
  }

  close() {
    this.dialog.close();
    this.previousFocus?.focus(); // Return focus to trigger
  }
}
```

### PPZ Navigation Patterns

#### Breadcrumb Trail

```php
<?php
function ppz_breadcrumbs(array $items): string {
    $html = '<nav class="ppz-breadcrumbs" aria-label="Breadcrumb"><ol class="ppz-breadcrumbs__list">';
    $lastIndex = count($items) - 1;

    foreach ($items as $i => $item) {
        $isLast = ($i === $lastIndex);
        $name = htmlspecialchars($item['name']);

        if ($isLast) {
            $html .= "<li class=\"ppz-breadcrumbs__item\" aria-current=\"page\">{$name}</li>";
        } else {
            $href = htmlspecialchars($item['href']);
            $html .= "<li class=\"ppz-breadcrumbs__item\"><a href=\"{$href}\" class=\"ppz-breadcrumbs__link\">{$name}</a></li>";
        }
    }

    $html .= '</ol></nav>';
    return $html;
}
?>
```

### PPZ Toast/Notification System

```php
<?php
function ppz_toast(array $props): string {
    $type = $props['type'] ?? 'info'; // success, warning, error, info
    $message = htmlspecialchars($props['message']);
    $dismissable = $props['dismissable'] ?? true;
    $duration = $props['duration'] ?? 5000;

    $dismissBtn = $dismissable ? '<button class="ppz-toast__dismiss" aria-label="Dismiss">&times;</button>' : '';

    return <<<HTML
    <div class="ppz-toast ppz-toast--{$type}" role="status" aria-live="polite" data-ppz-duration="{$duration}">
        <span class="ppz-toast__icon" aria-hidden="true"></span>
        <p class="ppz-toast__message">{$message}</p>
        {$dismissBtn}
    </div>
    HTML;
}
?>
```

### PPZ Form Flows

#### Multi-Step Form (Wizard)

```php
<?php
function ppz_wizard(array $props): string {
    $steps = $props['steps'] ?? [];
    $currentStep = $props['current'] ?? 0;

    $progressHtml = '<div class="ppz-wizard__progress" role="progressbar" aria-valuenow="' . ($currentStep + 1) . '" aria-valuemin="1" aria-valuemax="' . count($steps) . '">';
    foreach ($steps as $i => $step) {
        $state = $i < $currentStep ? 'completed' : ($i === $currentStep ? 'active' : 'pending');
        $name = htmlspecialchars($step['name']);
        $progressHtml .= "<div class=\"ppz-wizard__step ppz-wizard__step--{$state}\">{$name}</div>";
    }
    $progressHtml .= '</div>';

    return <<<HTML
    <div class="ppz-wizard">
        {$progressHtml}
        <div class="ppz-wizard__content">
            {$steps[$currentStep]['content']}
        </div>
        <div class="ppz-wizard__actions">
            {$currentStep > 0 ? ppz_button(['text' => 'Previous', 'variant' => 'secondary']) : ''}
            {$currentStep < count($steps) - 1
                ? ppz_button(['text' => 'Next', 'variant' => 'primary'])
                : ppz_button(['text' => 'Submit', 'variant' => 'primary'])}
        </div>
    </div>
    HTML;
}
?>
```

### PPZ Interaction Patterns

| Pattern | PPZ Implementation | Trigger |
|---------|-------------------|---------|
| Create item | Open popin with form | Click "+" or "New" button |
| Edit item | Open popin with pre-filled form | Click edit icon or row |
| Delete item | Confirm popin → toast on success | Click delete → confirm |
| View details | Open popin or navigate to detail page | Click item row/card |
| Bulk actions | Select via checkboxes → action bar appears | Check items |
| Search | Instant filter (debounced) or search popin | Type in search bar |
| Notify | Toast (auto-dismiss) for info, persistent for errors | After action |

### PPZ Loading Patterns

```php
<?php
// Skeleton loader for PPZ cards
function ppz_card_skeleton(): string {
    return <<<HTML
    <div class="ppz-card ppz-card--skeleton" aria-busy="true" aria-label="Loading">
        <div class="ppz-skeleton ppz-skeleton--rect" style="height: 200px"></div>
        <div class="ppz-card__body">
            <div class="ppz-skeleton ppz-skeleton--text" style="width: 70%"></div>
            <div class="ppz-skeleton ppz-skeleton--text" style="width: 90%"></div>
            <div class="ppz-skeleton ppz-skeleton--text" style="width: 50%"></div>
        </div>
    </div>
    HTML;
}
?>
```

## Output Format

```
## PPZ UX Pattern: [Pattern Name]
- Type: [popin/form/navigation/notification/loading]
- Trigger: [What initiates this pattern]
- Flow: [Step by step user flow]
- Feedback: [How user knows it worked]
- Error handling: [What happens on failure]
- Accessibility: [ARIA, keyboard, screen reader notes]
```

## Anti-patterns

- **NEVER** use browser `alert()`, `confirm()`, or `prompt()` — use PPZ popins and toasts
- **NEVER** open multiple popins stacked — close current before opening another
- **NEVER** forget to return focus after closing a popin
- **NEVER** auto-dismiss error toasts — errors must be manually dismissed
- **NEVER** use page reloads for form submissions — use AJAX + toast feedback
- **NEVER** skip the loading state between action and result
- **NEVER** forget keyboard support in PPZ interactive components
- **NEVER** use generic "Error" messages — be specific about what went wrong
