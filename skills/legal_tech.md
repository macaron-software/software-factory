# Droit du Numérique — Skill Prompt

## Objectif

Auditer la conformité juridique d'un service numérique au droit européen et français.

## Cadre réglementaire

### 1. DSA — Digital Services Act (Règlement 2022/2065)

- [ ] Modération de contenu : mécanisme de signalement accessible ?
- [ ] Transparence algorithmique : recommandations explicables ?
- [ ] Rapports de transparence publiés ?
- [ ] Point de contact unique désigné ?
- [ ] Dark patterns interdits (Art. 25) : pas de manipulation UI ?

### 2. DMA — Digital Markets Act (Règlement 2022/1925)

- [ ] Interopérabilité si gatekeeper ?
- [ ] Pas de self-preferencing ?
- [ ] Portabilité des données utilisateur ?

### 3. AI Act (Règlement 2024/1689)

- [ ] Classification du risque : inacceptable / haut / limité / minimal ?
- [ ] Si haut risque : conformité évaluation, registre EU, monitoring ?
- [ ] Si limité : obligations de transparence (chatbot = dire que c'est une IA) ?
- [ ] Interdictions : scoring social, reconnaissance faciale temps réel, manipulation ?

### 4. ePrivacy (Directive 2002/58/CE + CNIL)

- [ ] Cookies : bandeau conforme (refuser aussi facile qu'accepter) ?
- [ ] Traceurs : pas de dépôt avant consentement (sauf exemptés) ?
- [ ] Liste des cookies documentée et à jour ?
- [ ] Durée de vie cookies < 13 mois ?

### 5. LCEN (Loi pour la Confiance dans l'Économie Numérique)

- [ ] Mentions légales complètes : éditeur, hébergeur, directeur publication ?
- [ ] Statut hébergeur vs éditeur clarifié ?
- [ ] Notification de retrait LCEN implémentée ?

### 6. Propriété intellectuelle

- [ ] Licences open source respectées (MIT, Apache, GPL — compatibilité) ?
- [ ] Code tiers : licence vérifiée, attribution présente ?
- [ ] Assets (images, fonts, icons) : droits acquis ?
- [ ] Pas de scraping de contenu protégé ?

### 7. Accessibilité (obligation légale)

- [ ] Déclaration d'accessibilité publiée ?
- [ ] Schéma pluriannuel de mise en accessibilité ?
- [ ] Conformité RGAA 4.1 (obligatoire secteur public + privé > 250M€ CA) ?
- [ ] Directive EAA (European Accessibility Act) : applicable juin 2025 ?

### 8. CGU/CGV

- [ ] Clauses abusives identifiées et supprimées ?
- [ ] Droit de rétractation (14j e-commerce) ?
- [ ] Information précontractuelle complète (prix, caractéristiques, délais) ?
- [ ] Médiation consommateur mentionnée ?
- [ ] Tribunal compétent et loi applicable ?

## Template de rapport juridique

```
## Audit Juridique Numérique — [Produit]
**Date:** YYYY-MM-DD
**Juriste:** Étienne Vasseur

### Conformité par réglementation
| Réglementation | Statut | Non-conformités | Risque |
|----------------|--------|-----------------|--------|
| RGPD           | ✅/⚠️/❌ |                 | €/pénal |
| DSA            | ✅/⚠️/❌ |                 | % CA   |
| AI Act         | ✅/⚠️/❌ |                 | €/ban  |
| ePrivacy       | ✅/⚠️/❌ |                 | CNIL   |
| LCEN           | ✅/⚠️/❌ |                 | pénal  |
| CGU            | ✅/⚠️/❌ |                 | civil  |
| Accessibilité  | ✅/⚠️/❌ |                 | amende |

### Actions correctives prioritaires
1. [Critique] ...
2. [Haute] ...
3. [Moyenne] ...
```
