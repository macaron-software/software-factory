---
name: ux-saas-patterns
description: >
  Guides the agent through UX patterns specific to the SaasApp (SAAS) platform. Use this
  skill when implementing user experience flows, interaction patterns, and feedback
  mechanisms within the SAAS ecosystem. Covers SAAS-specific navigation, modals (popins),
  form flows, notification patterns, and the SAAS interaction language.
metadata:
  category: design
  triggers:
    - "when implementing UX patterns for the SAAS platform"
    - "when working with SAAS modals/popins"
    - "when designing SAAS navigation flows"
    - "when implementing SAAS notification patterns"
    - "when user asks about SAAS user experience"
---

# SAAS UX Patterns (SaasApp)

This skill enables the agent to implement UX patterns specific to the SaasApp platform,
including its modal/popin system, navigation flows, form patterns, and feedback mechanisms.

## Use this skill when

- Implementing user flows in the SAAS platform
- Working with SAAS popin (modal) system
- Building SAAS form workflows
- Implementing SAAS notification/toast patterns
- Designing SAAS navigation and routing

## Do not use this skill when

- Working on non-SAAS projects (use ux-best-practices)
- Building SAAS visual components (use ui-saas-design-system)
- Doing general accessibility audits (use accessibility-audit)

## Instructions

### SAAS Popin (Modal) System

The SAAS platform centers around "popins" — modal-like components that are the primary
interaction pattern. The name "SaasApp" comes from this core concept.

```php
<?php
function saas_popin(array $props): string {
    $id = htmlspecialchars($props['id']);
    $title = htmlspecialchars($props['title'] ?? '');
    $size = $props['size'] ?? 'md'; // sm, md, lg, xl, full
    $content = $props['content'] ?? '';
    $closable = $props['closable'] ?? true;

    $closeBtn = $closable ? <<<HTML
    <button class="saas-popin__close" aria-label="Close" data-saas-close>
        <span aria-hidden="true">&times;</span>
    </button>
    HTML : '';

    return <<<HTML
    <dialog class="saas-popin saas-popin--{$size}" id="{$id}" aria-labelledby="{$id}-title">
        <div class="saas-popin__header">
            <h2 class="saas-popin__title" id="{$id}-title">{$title}</h2>
            {$closeBtn}
        </div>
        <div class="saas-popin__body">
            {$content}
        </div>
        <div class="saas-popin__footer" id="{$id}-footer">
        </div>
    </dialog>
    HTML;
}
?>
```

```css
.saas-popin {
  border: none;
  border-radius: var(--saas-radius-lg);
  box-shadow: var(--saas-shadow-lg);
  padding: 0;
  max-height: 90vh;
  overflow: hidden;
}

.saas-popin--sm {
  width: min(400px, 90vw);
}
.saas-popin--md {
  width: min(560px, 90vw);
}
.saas-popin--lg {
  width: min(720px, 90vw);
}
.saas-popin--xl {
  width: min(960px, 90vw);
}
.saas-popin--full {
  width: 90vw;
  height: 90vh;
}

.saas-popin__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--saas-space-4) var(--saas-space-6);
  border-bottom: 1px solid var(--saas-color-border);
}

.saas-popin__body {
  padding: var(--saas-space-6);
  overflow-y: auto;
  max-height: 60vh;
}

.saas-popin__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--saas-space-3);
  padding: var(--saas-space-4) var(--saas-space-6);
  border-top: 1px solid var(--saas-color-border);
}

.saas-popin::backdrop {
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
    this.dialog.addEventListener("click", (e) => {
      if (e.target === this.dialog) this.close();
    });

    // Close on Escape
    this.dialog.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this.close();
    });

    // Close button
    this.dialog.querySelector("[data-saas-close]")?.addEventListener("click", () => {
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

### SAAS Navigation Patterns

#### Breadcrumb Trail

```php
<?php
function saas_breadcrumbs(array $items): string {
    $html = '<nav class="saas-breadcrumbs" aria-label="Breadcrumb"><ol class="saas-breadcrumbs__list">';
    $lastIndex = count($items) - 1;

    foreach ($items as $i => $item) {
        $isLast = ($i === $lastIndex);
        $name = htmlspecialchars($item['name']);

        if ($isLast) {
            $html .= "<li class=\"saas-breadcrumbs__item\" aria-current=\"page\">{$name}</li>";
        } else {
            $href = htmlspecialchars($item['href']);
            $html .= "<li class=\"saas-breadcrumbs__item\"><a href=\"{$href}\" class=\"saas-breadcrumbs__link\">{$name}</a></li>";
        }
    }

    $html .= '</ol></nav>';
    return $html;
}
?>
```

### SAAS Toast/Notification System

```php
<?php
function saas_toast(array $props): string {
    $type = $props['type'] ?? 'info'; // success, warning, error, info
    $message = htmlspecialchars($props['message']);
    $dismissable = $props['dismissable'] ?? true;
    $duration = $props['duration'] ?? 5000;

    $dismissBtn = $dismissable ? '<button class="saas-toast__dismiss" aria-label="Dismiss">&times;</button>' : '';

    return <<<HTML
    <div class="saas-toast saas-toast--{$type}" role="status" aria-live="polite" data-saas-duration="{$duration}">
        <span class="saas-toast__icon" aria-hidden="true"></span>
        <p class="saas-toast__message">{$message}</p>
        {$dismissBtn}
    </div>
    HTML;
}
?>
```

### SAAS Form Flows

#### Multi-Step Form (Wizard)

```php
<?php
function saas_wizard(array $props): string {
    $steps = $props['steps'] ?? [];
    $currentStep = $props['current'] ?? 0;

    $progressHtml = '<div class="saas-wizard__progress" role="progressbar" aria-valuenow="' . ($currentStep + 1) . '" aria-valuemin="1" aria-valuemax="' . count($steps) . '">';
    foreach ($steps as $i => $step) {
        $state = $i < $currentStep ? 'completed' : ($i === $currentStep ? 'active' : 'pending');
        $name = htmlspecialchars($step['name']);
        $progressHtml .= "<div class=\"saas-wizard__step saas-wizard__step--{$state}\">{$name}</div>";
    }
    $progressHtml .= '</div>';

    return <<<HTML
    <div class="saas-wizard">
        {$progressHtml}
        <div class="saas-wizard__content">
            {$steps[$currentStep]['content']}
        </div>
        <div class="saas-wizard__actions">
            {$currentStep > 0 ? saas_button(['text' => 'Previous', 'variant' => 'secondary']) : ''}
            {$currentStep < count($steps) - 1
                ? saas_button(['text' => 'Next', 'variant' => 'primary'])
                : saas_button(['text' => 'Submit', 'variant' => 'primary'])}
        </div>
    </div>
    HTML;
}
?>
```

### SAAS Interaction Patterns

| Pattern      | SAAS Implementation                                   | Trigger                   |
| ------------ | ---------------------------------------------------- | ------------------------- |
| Create item  | Open popin with form                                 | Click "+" or "New" button |
| Edit item    | Open popin with pre-filled form                      | Click edit icon or row    |
| Delete item  | Confirm popin → toast on success                     | Click delete → confirm    |
| View details | Open popin or navigate to detail page                | Click item row/card       |
| Bulk actions | Select via checkboxes → action bar appears           | Check items               |
| Search       | Instant filter (debounced) or search popin           | Type in search bar        |
| Notify       | Toast (auto-dismiss) for info, persistent for errors | After action              |

### SAAS Loading Patterns

```php
<?php
// Skeleton loader for SAAS cards
function saas_card_skeleton(): string {
    return <<<HTML
    <div class="saas-card saas-card--skeleton" aria-busy="true" aria-label="Loading">
        <div class="saas-skeleton saas-skeleton--rect" style="height: 200px"></div>
        <div class="saas-card__body">
            <div class="saas-skeleton saas-skeleton--text" style="width: 70%"></div>
            <div class="saas-skeleton saas-skeleton--text" style="width: 90%"></div>
            <div class="saas-skeleton saas-skeleton--text" style="width: 50%"></div>
        </div>
    </div>
    HTML;
}
?>
```

## Output Format

```
## SAAS UX Pattern: [Pattern Name]
- Type: [popin/form/navigation/notification/loading]
- Trigger: [What initiates this pattern]
- Flow: [Step by step user flow]
- Feedback: [How user knows it worked]
- Error handling: [What happens on failure]
- Accessibility: [ARIA, keyboard, screen reader notes]
```

## Anti-patterns

- **NEVER** use browser `alert()`, `confirm()`, or `prompt()` — use SAAS popins and toasts
- **NEVER** open multiple popins stacked — close current before opening another
- **NEVER** forget to return focus after closing a popin
- **NEVER** auto-dismiss error toasts — errors must be manually dismissed
- **NEVER** use page reloads for form submissions — use AJAX + toast feedback
- **NEVER** skip the loading state between action and result
- **NEVER** forget keyboard support in SAAS interactive components
- **NEVER** use generic "Error" messages — be specific about what went wrong
