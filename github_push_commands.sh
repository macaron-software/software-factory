#!/bin/bash
# Commandes pour pousser et protéger master
# À exécuter sur Azure VM (macaron@4.233.64.30)

set -e

echo '=== SOFTWARE FACTORY - Push et Protection Master ==='
echo ''
echo 'Ce script va:'
echo '1. Configurer Git avec un token GitHub'
echo '2. Pousser 102 commits vers origin/main'
echo '3. Protéger la branche master (lecture seule)'
echo '4. Optionnellement supprimer master'
echo ''

# Demander le token
read -p 'Entrez votre GitHub Personal Access Token (ou appuyez sur Enter pour passer): ' GITHUB_TOKEN

if [ -z "$GITHUB_TOKEN" ]; then
    echo ''
    echo 'Token non fourni. Vous devrez exécuter manuellement:'
    echo ''
    echo '  cd ~/software-factory'
    echo '  export GITHUB_TOKEN=ghp_votre_token'
    echo '  git remote set-url origin https://${GITHUB_TOKEN}@github.com/macaron-software/software-factory.git'
    echo '  git push origin main'
    echo ''
    echo 'Créer un token: https://github.com/settings/tokens'
    echo 'Permissions requises: repo (full control)'
    exit 0
fi

cd ~/software-factory

# Vérifier état
echo 'État actuel:'
git log --oneline -3
echo ''
echo "Commits à pousser: $(git rev-list --count @{u}..HEAD 2>/dev/null || echo 102)"
echo ''

# Configurer remote avec token
echo 'Configuration de Git avec token...'
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/macaron-software/software-factory.git"

# Pousser
echo 'Push des commits vers GitHub...'
if git push origin main; then
    echo '✅ Push réussi!'
else
    echo '❌ Erreur lors du push'
    exit 1
fi

# Restaurer URL normale
git remote set-url origin https://github.com/macaron-software/software-factory.git

echo ''
echo '=== Protection de la branche master ==='
read -p 'Voulez-vous protéger master en lecture seule? (y/n): ' PROTECT

if [ "$PROTECT" = 'y' ]; then
    echo 'Protection via API GitHub...'
    curl -X PUT -H "Authorization: token ${GITHUB_TOKEN}" -H 'Accept: application/vnd.github.v3+json' https://api.github.com/repos/macaron-software/software-factory/branches/master/protection -d '{"lock_branch":true,"enforce_admins":false,"required_pull_request_reviews":null,"required_status_checks":null,"restrictions":null}'
    echo ''
    echo '✅ Master protégée'
fi

echo ''
echo '=== Suppression de master ==='
read -p 'Voulez-vous supprimer la branche master? (y/n): ' DELETE

if [ "$DELETE" = 'y' ]; then
    echo 'Suppression de master sur GitHub...'
    git push origin --delete master
    echo '✅ Master supprimée'
fi

echo ''
echo '=== TERMINÉ ==='
echo 'Vérifier sur GitHub: https://github.com/macaron-software/software-factory'
