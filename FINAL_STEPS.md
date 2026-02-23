# Étapes Finales - Merge Master → Main

## ✅ Terminé

1. **Merge master dans main**: 101 commits mergés
2. **Résolution conflits**: Tous les conflits résolus
3. **Fix imports**: Notification service corrigé
4. **SF CLI**: Commandes fonctionnelles
   - `sf platform status` ✅
   - `sf db status` ✅
5. **Déploiement Azure**: http://4.233.64.30 ✅

## ⏳ Reste à Faire

### 1. Pousser les commits sur GitHub

**Option A - Avec Personal Access Token:**
```bash
cd ~/software-factory

# Créer un token sur https://github.com/settings/tokens
# Permissions: repo (full control)

export GITHUB_TOKEN='ghp_votre_token_ici'
git remote set-url origin https://${GITHUB_TOKEN}@github.com/macaron-software/software-factory.git
git push origin main

# Remettre HTTPS normal après
git remote set-url origin https://github.com/macaron-software/software-factory.git
```

**Option B - Avec SSH:**
```bash
cd ~/software-factory

# Configurer SSH key sur https://github.com/settings/keys
git remote set-url origin git@github.com:macaron-software/software-factory.git
git push origin main
```

### 2. Protéger la branche master (lecture seule)

**Via Interface Web GitHub:**
1. Aller sur https://github.com/macaron-software/software-factory/settings/branches
2. Cliquer Add rule
3. Branch name pattern: `master`
4. Cocher Lock branch (read-only)
5. Save changes

**Via API GitHub (avec token):**
```bash
curl -X PUT \
  -H Authorization: token ${GITHUB_TOKEN} \
  -H Accept: application/vnd.github.v3+json \
  https://api.github.com/repos/macaron-software/software-factory/branches/master/protection \
  -d '{
    lock_branch: true,
    enforce_admins: false,
    required_pull_request_reviews: null,
    required_status_checks: null,
    restrictions: null
  }'
```

### 3. Supprimer master (optionnel, après vérification)

**Après avoir vérifié que tout est sur main:**
```bash
# Supprimer localement (déjà fait)
git branch -D master

# Supprimer sur GitHub
git push origin --delete master
```

## État Actuel

- **Branche**: main
- **Commits locaux**: 101 en avance sur origin/main
- **Dernier commit**: 54ff3f6 - SF routing and notification service imports
- **Azure**: Déployé et fonctionnel
- **Tests**: SF CLI opérationnel

## Vérifications Post-Push

Après avoir pushé:
```bash
# Vérifier que main est à jour
git fetch origin
git status

# Vérifier les branches
git branch -a

# Tester sur production
curl http://4.233.64.30/
curl -X POST http://4.233.64.30/api/cli/execute \
  -H Content-Type: application/json \
  -d '{command:sf,args:[platform,status]}'
```
