# Sécurité — Software Factory

> **Status:** 🚧 À compléter (phase Discovery — audit obligatoire avant MVP)

## ⚠️ Audit de sécurité requis

Ce fichier DOIT être complété AVANT de passer en phase MVP.

## Surfaces d'attaque

| Surface | Risque | Vecteur possible | Protection |
|---------|--------|-----------------|------------|
| API | — | — | Auth JWT / API Key |
| DB | — | Injection SQL | ORM + validation |
| Auth | — | Brute force | Rate limit + MFA |
| Données | — | Data leak | Chiffrement at rest |

## Vecteurs d'attaque identifiés

- [ ] Injection (SQL, LDAP, XSS)
- [ ] Authentification cassée
- [ ] Exposition de données sensibles
- [ ] Mauvaise configuration sécurité
- [ ] Composants vulnérables (CVE watch)

## Règles obligatoires

### Auth
- [ ] Tous les endpoints authentifiés sauf liste blanche explicite
- [ ] Tokens expirables (JWT max 1h, refresh 7j)
- [ ] Pas de secrets dans le code (env vars uniquement)

### Validation des inputs
- [ ] Validation côté serveur pour TOUS les inputs
- [ ] Sanitisation avant persistance
- [ ] Taille maximale définie pour chaque champ

### Accès aux données
- [ ] Principe du moindre privilège
- [ ] Isolation par tenant/utilisateur
- [ ] Audit log pour les accès sensibles

### Protection backend
- [ ] Rate limiting sur les endpoints publics
- [ ] CORS strict (liste blanche)
- [ ] Headers sécurité (CSP, HSTS, X-Frame-Options)
- [ ] Pas d'erreurs techniques exposées en prod

## Score sécurité initial

- [ ] Audit OWASP Top 10 réalisé
- [ ] Pas de CVE critique sur les dépendances
- [ ] Revue de code sécurité faite

---
*Généré par Software Factory — OBLIGATOIRE avant passage MVP*
