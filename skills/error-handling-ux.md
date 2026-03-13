# Error Handling UX — Empathetic Feedback

## Purpose
Design error states that reassure users, explain what happened in human terms, and provide clear next steps. Never blame the user. Never show technical jargon.

## Empathetic Message Framework

### Tone Principles
- **Acknowledge** the frustration: "On sait, c'est frustrant"
- **Explain** simply: what happened (not why technically)
- **Reassure**: their data is safe, the action can be retried
- **Guide**: one clear next step (retry button, alternative action)

### Message Templates by Scenario

#### Network Disconnection
```
Title: Connexion perdue
Body: Pas de panique, vos modifications sont sauvegardées localement.
      On réessaie automatiquement dès que la connexion revient.
Action: [Réessayer maintenant]
Icon: wifi-off (Feather/SF Symbols/Material)
Style: Warning banner (yellow/amber), not modal
```

#### Server Error (500)
```
Title: Oups, quelque chose n'a pas fonctionné
Body: Notre équipe est déjà prévenue.
      Vos données sont en sécurité.
Action: [Réessayer] [Retour à l'accueil]
Icon: alert-triangle
Style: Error banner (red/destructive), dismissible
```

#### Timeout
```
Title: La réponse prend plus de temps que prévu
Body: Le serveur est un peu lent en ce moment.
      On réessaie dans quelques secondes...
Action: [Réessayer] [Annuler]
Icon: clock
Progress: indeterminate spinner
Style: Info banner with auto-retry countdown
```

#### Offline Mode Active
```
Title: Mode hors ligne
Body: Vous pouvez continuer à travailler.
      Tout sera synchronisé quand vous serez reconnecté.
Action: (none — passive notification)
Icon: cloud-off
Style: Subtle top banner, persistent until online
```

#### Connection Restored
```
Title: Connexion rétablie
Body: Synchronisation en cours...
Action: (auto-dismiss after 3s)
Icon: wifi / check-circle
Style: Success banner (green), auto-dismiss
Animation: slide-down, then slide-up after sync
```

#### 404 / Not Found
```
Title: Page introuvable
Body: Ce contenu a peut-être été déplacé ou supprimé.
Action: [Retour] [Accueil] [Rechercher]
Icon: search
Style: Full page with illustration, not banner
```

#### Rate Limited (429)
```
Title: Doucement !
Body: Trop de requêtes en peu de temps.
      Réessayez dans {retryAfter} secondes.
Action: [Réessayer dans {countdown}s] (disabled until countdown)
Icon: zap
Style: Warning banner with countdown
```

#### Form Validation (Client-Side)
```
Title: (inline, no title)
Body: Ce champ est requis / Format invalide — attendu: email@exemple.com
Style: Inline under field, aria-describedby linked
Color: var(--color-error) from design tokens
Animation: gentle shake (prefers-reduced-motion: no animation)
```

## Component Patterns

### Error Banner (React/Next.js)
```tsx
interface ErrorBannerProps {
  type: 'error' | 'warning' | 'info' | 'success';
  title: string;
  message: string;
  action?: { label: string; onClick: () => void };
  autoDismiss?: number; // ms, 0 = persistent
}

function ErrorBanner({ type, title, message, action, autoDismiss }: ErrorBannerProps) {
  return (
    <div role="alert" aria-live="assertive" className={`banner banner--${type}`}>
      <Icon name={iconMap[type]} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      {action && (
        <button onClick={action.onClick} className="banner__action">
          {action.label}
        </button>
      )}
    </div>
  );
}
```

### iOS Error View (SwiftUI)
```swift
struct ErrorStateView: View {
  let title: String
  let message: String
  let retryAction: (() -> Void)?

  var body: some View {
    VStack(spacing: 16) {
      Image(systemName: "exclamationmark.triangle")
        .font(.system(size: 48))
        .foregroundStyle(.secondary)
        .accessibilityHidden(true)
      Text(title)
        .font(.headline)
      Text(message)
        .font(.subheadline)
        .foregroundStyle(.secondary)
        .multilineTextAlignment(.center)
      if let retryAction {
        Button("Réessayer", action: retryAction)
          .buttonStyle(.borderedProminent)
      }
    }
    .padding(32)
    .accessibilityElement(children: .combine)
  }
}
```

### Android Error State (Compose)
```kotlin
@Composable
fun ErrorState(
  title: String,
  message: String,
  onRetry: (() -> Unit)? = null
) {
  Column(
    modifier = Modifier.fillMaxWidth().padding(32.dp),
    horizontalAlignment = Alignment.CenterHorizontally,
    verticalArrangement = Arrangement.spacedBy(16.dp)
  ) {
    Icon(
      Icons.Outlined.Warning,
      contentDescription = null, // decorative
      modifier = Modifier.size(48.dp),
      tint = MaterialTheme.colorScheme.onSurfaceVariant
    )
    Text(title, style = MaterialTheme.typography.headlineSmall)
    Text(message, style = MaterialTheme.typography.bodyMedium,
         color = MaterialTheme.colorScheme.onSurfaceVariant,
         textAlign = TextAlign.Center)
    onRetry?.let {
      Button(onClick = it) { Text("Réessayer") }
    }
  }
}
```

## Loading States

### Skeleton Screens (preferred over spinners)
```css
.skeleton {
  background: linear-gradient(90deg,
    var(--color-surface-secondary) 25%,
    var(--color-surface-tertiary) 50%,
    var(--color-surface-secondary) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; opacity: 0.7; }
}
```

### Progressive Loading
1. Show skeleton immediately (0ms)
2. Show cached/stale data if available (0-100ms)
3. Start network request
4. Blend fresh data in (no flash) when received
5. If error after 10s: show error banner OVER skeleton/stale data (don't remove content)

## Accessibility for Error States
- `role="alert"` + `aria-live="assertive"` for errors
- `role="status"` + `aria-live="polite"` for info/success
- Never use color alone to indicate error state (add icon + text)
- Error messages must be linked to inputs via `aria-describedby`
- Screen readers must announce connectivity changes
- `prefers-reduced-motion`: disable shake/slide animations

## Rules
- NEVER show: stack traces, HTTP codes, raw JSON, technical IDs
- NEVER blame the user: "Erreur de votre part" → "Quelque chose n'a pas fonctionné"
- ALWAYS provide a way out: retry, go back, contact support
- ALWAYS preserve user input during errors (no form reset)
- ALWAYS use design tokens for error colors (var(--color-error), var(--color-warning))
- ALWAYS announce errors to screen readers (aria-live)
- Retry button must show loading state while retrying
- Error banners: max 2 visible at once, stack newest on top
- Auto-dismiss success banners after 3-5s, never auto-dismiss errors
