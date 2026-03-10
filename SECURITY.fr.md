<p align="center">
  <a href="SECURITY.md">English</a> |
  <a href="SECURITY.fr.md">Français</a> |
  <a href="SECURITY.zh-CN.md">中文</a> |
  <a href="SECURITY.es.md">Español</a> |
  <a href="SECURITY.ja.md">日本語</a> |
  <a href="SECURITY.pt.md">Português</a> |
  <a href="SECURITY.de.md">Deutsch</a> |
  <a href="SECURITY.ko.md">한국어</a>
</p>

# Politique de Securite

## Versions Supportees

| Version | Supportee |
|---------|-----------|
| 2.2.x   | Oui       |
| 2.1.x   | Oui       |
| < 2.1   | Non       |

## Signaler une Vulnerabilite

Si vous decouvrez une vulnerabilite de securite, veuillez la signaler de maniere responsable :

1. **N'ouvrez pas** une issue publique sur GitHub
2. Envoyez un email a **security@macaron-software.com**
3. Incluez :
   - Description de la vulnerabilite
   - Etapes de reproduction
   - Impact potentiel
   - Correction suggeree (le cas echeant)

Nous accuserons reception sous 48 heures et fournirons une reponse detaillee sous 7 jours.

## Mesures de Securite

### Authentification et Autorisation

- Authentification JWT avec rafraichissement de token
- Controle d'acces base sur les roles (RBAC) : admin, project_manager, developer, viewer
- Integration OAuth 2.0 (GitHub, Azure AD)
- Gestion de session avec cookies securises

### Validation des Entrees

- Garde contre l'injection de prompt sur toutes les entrees LLM
- Assainissement des entrees sur tous les endpoints API
- Requetes SQL parametrees (pas d'interpolation SQL brute)
- Protection contre le parcours de chemin de fichier

### Protection des Donnees

- Masquage des secrets dans les sorties agents (cles API, mots de passe, tokens)
- Aucun secret stocke dans le code source ou les logs
- Configuration par environnement pour les valeurs sensibles
- Mode WAL SQLite pour l'integrite des donnees

### Securite Reseau

- En-tetes Content Security Policy (CSP)
- Configuration CORS pour les endpoints API
- Limitation de debit par utilisateur/IP
- HTTPS impose en production (via Nginx)

### Gestion des Dependances

- Audits reguliers des dependances via `pip-audit`
- Analyse SAST avec bandit et semgrep
- Missions de securite automatisees par projet (scans hebdomadaires)

## Politique de Divulgation

Nous suivons la divulgation coordonnee. Apres la publication d'un correctif :
1. Credit au rapporteur (sauf si l'anonymat est demande)
2. Publication d'un avis de securite sur GitHub
3. Mise a jour du changelog avec les correctifs de securite
