# Solaris Design System — Tokenization

## Objectif
Maîtriser le système de tokens CSS du Design System Solaris : variables custom, theming, responsive breakpoints, et intégration Angular.

## Tokens CSS — Variables Custom

### Couleurs
```css
/* Couleurs primaires */
--sol-color-primary: #003DA5;        /* Bleu primaire */
--sol-color-primary-light: #3366CC;
--sol-color-primary-dark: #002B75;
--sol-color-secondary: #FFCD00;      /* Jaune secondaire */
--sol-color-accent: #E5007D;         /* Rose accent */

/* Couleurs sémantiques */
--sol-color-success: #00A550;
--sol-color-warning: #FF9900;
--sol-color-error: #D9534F;
--sol-color-info: #3366CC;

/* Neutres */
--sol-color-text: #1A1A1A;
--sol-color-text-secondary: #666666;
--sol-color-border: #CCCCCC;
--sol-color-background: #FFFFFF;
--sol-color-surface: #F5F5F5;
```

### Typographie
```css
--sol-font-family: 'System Sans', 'Helvetica Neue', Arial, sans-serif;
--sol-font-size-xs: 0.75rem;    /* 12px */
--sol-font-size-sm: 0.875rem;   /* 14px */
--sol-font-size-md: 1rem;       /* 16px — base */
--sol-font-size-lg: 1.25rem;    /* 20px */
--sol-font-size-xl: 1.5rem;     /* 24px */
--sol-font-size-2xl: 2rem;      /* 32px */
--sol-font-size-3xl: 2.5rem;    /* 40px */

--sol-font-weight-regular: 400;
--sol-font-weight-medium: 500;
--sol-font-weight-semibold: 600;
--sol-font-weight-bold: 700;

--sol-line-height-tight: 1.2;
--sol-line-height-normal: 1.5;
--sol-line-height-relaxed: 1.75;
```

### Espacements
```css
--sol-space-2xs: 0.25rem;   /* 4px */
--sol-space-xs: 0.5rem;     /* 8px */
--sol-space-sm: 0.75rem;    /* 12px */
--sol-space-md: 1rem;       /* 16px */
--sol-space-lg: 1.5rem;     /* 24px */
--sol-space-xl: 2rem;       /* 32px */
--sol-space-2xl: 3rem;      /* 48px */
--sol-space-3xl: 4rem;      /* 64px */
```

### Bordures et ombres
```css
--sol-radius-sm: 4px;
--sol-radius-md: 8px;
--sol-radius-lg: 12px;
--sol-radius-full: 9999px;

--sol-shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--sol-shadow-md: 0 4px 6px rgba(0,0,0,0.1);
--sol-shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
--sol-shadow-xl: 0 20px 25px rgba(0,0,0,0.15);
```

### Breakpoints responsive
```css
--sol-breakpoint-sm: 640px;
--sol-breakpoint-md: 768px;
--sol-breakpoint-lg: 1024px;
--sol-breakpoint-xl: 1280px;
--sol-breakpoint-2xl: 1536px;
```

## Intégration Angular

### Import tokens dans le projet
```typescript
// angular.json — styles globaux
"styles": [
  "node_modules/@solaris/tokens/css/tokens.css",
  "src/styles.scss"
]
```

### Utilisation dans les composants
```typescript
@Component({
  selector: 'app-card',
  template: `<div class="card"><ng-content></ng-content></div>`,
  styles: [`
    .card {
      padding: var(--sol-space-lg);
      border-radius: var(--sol-radius-md);
      box-shadow: var(--sol-shadow-md);
      background: var(--sol-color-background);
      border: 1px solid var(--sol-color-border);
    }
  `]
})
export class CardComponent {}
```

### Theming — Mode sombre
```css
[data-theme="dark"] {
  --sol-color-text: #F5F5F5;
  --sol-color-text-secondary: #AAAAAA;
  --sol-color-background: #1A1A1A;
  --sol-color-surface: #2D2D2D;
  --sol-color-border: #444444;
}
```

## Règles d'utilisation

1. **Toujours utiliser les tokens** — jamais de valeurs CSS en dur (pas de `color: #003DA5`, utiliser `color: var(--sol-color-primary)`)
2. **Préférer les tokens sémantiques** — `--sol-color-error` plutôt que `--sol-color-danger` ou une couleur directe
3. **Responsive avec les breakpoints tokens** — utiliser `@media (min-width: var(--sol-breakpoint-md))` ou les mixins SCSS Solaris
4. **Espacements cohérents** — utiliser l'échelle de spacing, pas de valeurs arbitraires
5. **Typographie** — toujours System Sans, jamais de font personnalisée sans validation Design

## Validation

Utiliser `solaris_grep` pour vérifier l'absence de valeurs CSS en dur :
```bash
# Chercher des couleurs hex non-tokenisées
solaris_grep pattern="#[0-9a-fA-F]{6}" file_type="css"

# Vérifier l'utilisation des tokens
solaris_grep pattern="var\(--sol-" file_type="css"
```

Utiliser `solaris_stats` pour voir le taux de couverture des tokens dans le projet.
