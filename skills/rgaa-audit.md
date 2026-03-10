# Audit RGAA 4.1 — Référentiel Général d'Amélioration de l'Accessibilité

## Objectif
Mener un audit de conformité RGAA 4.1 niveau AA sur les applications web. Identifier les non-conformités, proposer des remédiations concrètes, et vérifier les corrections.

## Référentiel RGAA 4.1

### 13 Thématiques — 106 Critères

| # | Thématique | Critères | Points clés |
|---|-----------|----------|------------|
| 1 | Images | 9 critères | alt pertinent, images décoratives masquées, CAPTCHA alternatif |
| 2 | Cadres | 2 critères | title sur iframe, pertinence du titre |
| 3 | Couleurs | 3 critères | contraste 4.5:1 (texte), 3:1 (grands textes), info pas uniquement par couleur |
| 4 | Multimédia | 13 critères | sous-titres, audiodescription, contrôles clavier |
| 5 | Tableaux | 8 critères | en-têtes th, scope, caption, résumé |
| 6 | Liens | 5 critères | intitulé explicite, pas de "cliquez ici", distinction visuelle |
| 7 | Scripts | 12 critères | navigation clavier, changements de contexte, messages d'erreur |
| 8 | Éléments obligatoires | 9 critères | lang, title, structure HTML valide |
| 9 | Structuration | 4 critères | listes sémantiques, headings hiérarchiques (h1→h6) |
| 10 | Présentation | 14 critères | pas de tableau de mise en page, responsive, zoom 200% |
| 11 | Formulaires | 13 critères | labels, regroupement fieldset/legend, erreurs explicites |
| 12 | Navigation | 11 critères | menu nav, skip links, plan du site, fil d'Ariane |
| 13 | Consultation | 3 critères | pas de time limit, pas de flash, contenu accessible |

## Méthodologie d'audit

### Phase 1 : Échantillonnage
Sélectionner les pages représentatives :
- Page d'accueil
- Page de connexion / inscription
- Formulaire principal (demande, commande)
- Page de résultats (liste, tableau)
- Page de contenu (article, aide)
- Processus complet (tunnel de conversion)

### Phase 2 : Tests automatiques
```
# Utiliser Playwright pour les captures et tests navigateur
playwright_test → exécuter les scénarios de navigation clavier
screenshot → capturer les états visuels (focus, hover, error)

# Vérifier les composants Solaris
solaris_validation → conformité DS
solaris_wcag(pattern="...") → patterns ARIA par composant
```

### Phase 3 : Tests manuels

#### Navigation clavier (obligatoire)
- [ ] Tab : parcourt tous les éléments interactifs dans l'ordre logique
- [ ] Shift+Tab : retour en arrière
- [ ] Enter : active bouton/lien
- [ ] Space : active checkbox/button, scroll page
- [ ] Escape : ferme modale/dropdown/tooltip
- [ ] Flèches : navigation dans tabs, radio groups, menus
- [ ] Focus visible sur chaque élément (outline `:focus-visible`)

#### Lecteur d'écran (NVDA/VoiceOver)
- [ ] Tous les contenus significatifs sont vocalisés
- [ ] Les images ont des alt pertinents (ou sont masquées si décoratives)
- [ ] Les formulaires : labels lus, erreurs annoncées, groupes identifiés
- [ ] Les changements dynamiques annoncés via `aria-live`
- [ ] La navigation est cohérente (headings, landmarks, skip links)

#### Contrastes
- [ ] Texte courant : ratio >= 4.5:1
- [ ] Grand texte (>=24px ou >=18.5px bold) : ratio >= 3:1
- [ ] Éléments graphiques informatifs : ratio >= 3:1
- [ ] Focus indicator : ratio >= 3:1

### Phase 4 : Rapport d'audit

Pour chaque non-conformité :
```
| Critère | Page | Description | Impact | Remédiation |
|---------|------|-------------|--------|-------------|
| 1.1 | /login | Image sans alt | Majeur | Ajouter alt="Logo entreprise" |
| 3.2 | /form | Contraste 2.8:1 | Majeur | Utiliser var(--sol-color-text) |
| 11.1 | /form | Input sans label | Critique | Ajouter <label for="email"> |
```

## Niveaux de conformité

| Niveau | Signification | Exigence |
|--------|--------------|-------------------|
| A | Minimum vital | Obligatoire |
| AA | Standard | **Obligatoire** |
| AAA | Optimal | Recommandé pour les services publics |

## Critères les plus fréquemment en erreur

1. **Images sans alt** (critère 1.1) — ~30% des audits
2. **Contrastes insuffisants** (critère 3.2) — ~25%
3. **Labels manquants** (critère 11.1) — ~25%
4. **Navigation clavier incomplète** (critère 7.1) — ~20%
5. **Headings non hiérarchiques** (critère 9.1) — ~15%
6. **Focus non visible** (critère 7.2) — ~15%
7. **Liens non explicites** (critère 6.1) — ~10%

## Outils de vérification

| Outil | Usage | Intégration |
|-------|-------|-------------|
| axe-core | Tests automatiques | Playwright `@axe-core/playwright` |
| Lighthouse | Audit performance + a11y | Chrome DevTools MCP |
| WAVE | Évaluation visuelle | Extension navigateur |
| Colour Contrast Analyser | Contrastes | Application desktop |
| NVDA / VoiceOver | Lecteur d'écran | Test manuel obligatoire |

## Cadre légal

- **Loi n° 2005-102** du 11 février 2005 — égalité des droits et des chances
- **Décret n° 2019-768** du 24 juillet 2019 — RGAA obligatoire services publics
- **Directive européenne 2016/2102** — accessibilité sites web et apps mobiles
- **Sanction** : amende jusqu'à 20 000 € par service non conforme (art. 47 loi 2005)

Tout opérateur de service public est soumis à l'obligation RGAA sur **tous** ses sites et applications.
