# Green IT & Numérique Responsable — Skill Prompt

## Objectif

Auditer l'éco-conception d'un service numérique selon le RGESN et les bonnes pratiques Green IT.

## Checklist RGESN (Référentiel Général d'Éco-conception)

### 1. Stratégie (questionner le besoin)

- [ ] La feature répond-elle à un besoin réel utilisateur ?
- [ ] Peut-on faire plus simple (KISS) ?
- [ ] Existe-t-il une alternative moins impactante ?

### 2. Frontend

- [ ] Poids page < 1 Mo (idéal < 500 Ko) ?
- [ ] Images : format WebP/AVIF, responsive (srcset), lazy loading ?
- [ ] Pas de vidéo en autoplay ?
- [ ] JavaScript bundle < 200 Ko gzip ?
- [ ] Tree-shaking activé, pas de libs inutiles ?
- [ ] CSS : pas de frameworks lourds inutilisés ?
- [ ] Fonts : subset, woff2, < 3 variantes ?
- [ ] Animations : prefer-reduced-motion respecté ?
- [ ] Dark mode : réduit consommation OLED ?

### 3. Backend

- [ ] Requêtes SQL optimisées (pas de SELECT \*, pas de N+1) ?
- [ ] Index sur colonnes filtrées/triées ?
- [ ] Cache (Redis, CDN, HTTP cache headers) ?
- [ ] Compression (gzip/brotli) activée ?
- [ ] Pagination obligatoire sur les listes ?
- [ ] Pas de polling — SSE ou webhooks si temps réel ?
- [ ] Batch processing > traitement unitaire ?
- [ ] Timeout sur les requêtes externes ?

### 4. Infrastructure

- [ ] Auto-scaling DOWN (pas seulement up) ?
- [ ] Right-sizing VMs (pas de surdimensionnement) ?
- [ ] Région datacenter avec énergie renouvelable ?
- [ ] PUE datacenter < 1.4 ?
- [ ] Spot/preemptible instances pour les jobs batch ?
- [ ] Monitoring consommation (CPU, RAM, réseau, stockage) ?

### 5. Données

- [ ] Purge automatique des données obsolètes ?
- [ ] Compression des archives ?
- [ ] Pas de duplication inutile ?
- [ ] Logs : rotation + TTL ?
- [ ] Backups : rétention raisonnable ?

### 6. Réseau

- [ ] CDN pour les assets statiques ?
- [ ] HTTP/2 ou HTTP/3 ?
- [ ] Compression des réponses API ?
- [ ] Pas de sur-fetching (GraphQL fields ou sparse fieldsets) ?

## Outils de mesure

- **EcoIndex** : score A-G, eau, GES par page
- **Lighthouse** : performance score, bundle analysis
- **Website Carbon Calculator** : estimation CO2/visite
- **GreenIT Analysis** (extension) : requêtes, poids, DOM
- **Scaphandre** : consommation énergie serveur

## Métriques clés

| Métrique            | Cible         | Unité |
| ------------------- | ------------- | ----- |
| Poids page médian   | < 500 Ko      | Ko    |
| Requêtes HTTP/page  | < 25          | count |
| EcoIndex            | ≥ B (66+)     | score |
| CO2/visite          | < 0.5g        | gCO2e |
| Bundle JS           | < 200 Ko gzip | Ko    |
| Time to Interactive | < 3s          | sec   |

## Anti-patterns Green IT

- Image PNG 5 Mo non optimisée
- Polling toutes les secondes
- Import de lodash entier pour une seule fonction
- Vidéo HD autoplay en hero banner
- Google Fonts avec 12 variantes
- Analytics trackers multiples (GA + Hotjar + Segment + ...)
- Logs en mode DEBUG en production
- Microservices pour un CRUD simple
