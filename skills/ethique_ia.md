# Éthique IA — Skill Prompt

## Objectif
Auditer les systèmes IA pour les biais, l'explicabilité, la conformité AI Act et l'éthique.

## Framework d'audit IA

### 1. Classification AI Act (Titre III)
| Niveau | Exemples | Obligations |
|--------|----------|-------------|
| **Inacceptable** | Scoring social, manip subliminale | INTERDIT |
| **Haut risque** | Recrutement IA, crédit scoring, santé | Conformité complète |
| **Limité** | Chatbot, deepfake | Transparence |
| **Minimal** | Spam filter, recommandation | Aucune spécifique |

### 2. Détection de biais
- [ ] **Données d'entraînement** : représentatives de la population cible ?
- [ ] **Disparate Impact** (4/5 rule) : taux sélection groupe défavorisé ≥ 80% du groupe favorisé ?
- [ ] **Equal Opportunity** : TPR égal entre groupes démographiques ?
- [ ] **Demographic Parity** : taux de décision positive similaire entre groupes ?
- [ ] **Calibration** : confiance du modèle reflète la réalité pour tous les groupes ?
- [ ] Variables protégées : genre, origine, âge, handicap, religion — pas en features directes ?
- [ ] Proxy variables : code postal ≈ origine, prénom ≈ genre — identifiés et mitigés ?

### 3. Explicabilité
- [ ] **SHAP values** : contribution de chaque feature à la prédiction ?
- [ ] **LIME** : explication locale pour cas individuels ?
- [ ] **Feature importance** : top features documentées et validées métier ?
- [ ] **Counterfactual** : "que changer pour obtenir un résultat différent ?" ?
- [ ] Explication en langage naturel fournie à l'utilisateur ?

### 4. Transparence
- [ ] Utilisateur informé qu'il interagit avec une IA ?
- [ ] Décisions automatisées signalées (Art. 22 RGPD) ?
- [ ] Droit d'obtenir une intervention humaine ?
- [ ] Documentation technique : model card publiée ?

### 5. Supervision humaine (HITL)
- [ ] Décisions à fort impact : revue humaine obligatoire ?
- [ ] Override possible par un humain ?
- [ ] Alertes en cas de comportement anormal du modèle ?
- [ ] Monitoring des drifts (data drift, concept drift) ?

### 6. Robustesse & Sécurité
- [ ] Adversarial testing : modèle résiste aux inputs malicieux ?
- [ ] Prompt injection (pour LLMs) : protections en place ?
- [ ] Rate limiting sur les APIs IA ?
- [ ] Fallback si modèle indisponible ?

## Métriques clés
| Métrique | Cible | Description |
|----------|-------|-------------|
| Disparate Impact Ratio | ≥ 0.8 | 4/5 rule |
| Equal Opportunity Diff | < 0.1 | TPR gap |
| Explainability Coverage | 100% | % décisions explicables |
| HITL Rate | 100% haut risque | % avec supervision |
| Drift Detection | < 24h | Temps détection anomalie |

## Anti-patterns IA
- Modèle déployé sans évaluation des biais
- "L'IA a décidé" sans recours humain
- Données d'entraînement non documentées
- Fine-tuning sur données biaisées sans correction
- LLM en production sans content filtering
- Décision automatisée sans information utilisateur
- Pas de monitoring post-déploiement
- "C'est juste un prototype" déployé en prod

## Template model card
```
## Model Card — [Nom du modèle]
**Version:** X.Y | **Date:** YYYY-MM-DD | **Classification AI Act:** [niveau]

### Intended Use
- **Cas d'usage prévu:** ...
- **Utilisateurs cibles:** ...
- **Cas d'usage hors scope:** ...

### Training Data
- **Source:** ...
- **Taille:** ...
- **Représentativité:** ...
- **Biais connus:** ...

### Evaluation
| Groupe | Precision | Recall | F1 | Disparate Impact |
|--------|-----------|--------|----|------------------|

### Limitations
- ...

### Ethical Considerations
- ...
```
