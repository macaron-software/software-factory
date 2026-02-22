# TMA CRUD - Guide de Déploiement Azure

## 📋 Prérequis
- Accès SSH à 4.233.64.30 (azureuser)
- Container `deploy-platform-1` en cours d'exécution
- Privilèges root dans le container

## 📦 Fichiers à Déployer

### 1. API Routes
**Source:** `platform/web/routes/tma.py`
**Destination:** `/app/macaron_platform/web/routes/tma.py`
**Taille:** ~7KB (220 lignes)
**Contenu:** API REST endpoints pour CRUD tickets TMA

### 2. Routes Index
**Source:** `platform/web/routes/__init__.py`
**Destination:** `/app/macaron_platform/web/routes/__init__.py`
**Modification:** Ajout de `from .tma import router as tma_router` + `router.include_router(tma_router)`

### 3. Template Frontend
**Source:** `platform/web/templates/pi_board.html`
**Destination:** `/app/macaron_platform/web/templates/pi_board.html`
**Modification:** Modal JavaScript réécrite pour édition (lignes 623-780)

## 🚀 Procédure de Déploiement

### Étape 1: Upload vers VM
```bash
scp -i ~/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa \
    platform/web/routes/tma.py \
    platform/web/routes/__init__.py \
    platform/web/templates/pi_board.html \
    azureuser@4.233.64.30:/tmp/
```

### Étape 2: Connexion SSH
```bash
ssh -i ~/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa azureuser@4.233.64.30
```

### Étape 3: Copie vers Container
```bash
# Créer dossier temporaire
docker exec deploy-platform-1 mkdir -p /tmp/deploy

# Copier fichiers
docker cp /tmp/tma.py deploy-platform-1:/tmp/deploy/
docker cp /tmp/__init__.py deploy-platform-1:/tmp/deploy/
docker cp /tmp/pi_board.html deploy-platform-1:/tmp/deploy/
```

### Étape 4: Déploiement avec Root
```bash
docker exec -u root deploy-platform-1 bash -c "
    cp /tmp/deploy/tma.py /app/macaron_platform/web/routes/tma.py && \
    cp /tmp/deploy/__init__.py /app/macaron_platform/web/routes/__init__.py && \
    cp /tmp/deploy/pi_board.html /app/macaron_platform/web/templates/pi_board.html && \
    chown appuser:appuser /app/macaron_platform/web/routes/tma.py && \
    chown appuser:appuser /app/macaron_platform/web/routes/__init__.py && \
    chown appuser:appuser /app/macaron_platform/web/templates/pi_board.html
"
```

### Étape 5: Vérification
```bash
# Vérifier que les fichiers existent
docker exec deploy-platform-1 ls -lh /app/macaron_platform/web/routes/tma.py

# Vérifier le contenu (premières lignes)
docker exec deploy-platform-1 head -10 /app/macaron_platform/web/routes/tma.py

# Vérifier l'import Python
docker exec deploy-platform-1 python3 -c "from macaron_platform.web.routes.tma import router; print(f'✅ TMA router OK: {len(router.routes)} routes')"
```

### Étape 6: Redémarrage (Optionnel)
Le serveur FastAPI devrait auto-reload. Si nécessaire:
```bash
# Trouver le PID du processus uvicorn
docker exec deploy-platform-1 ps aux | grep uvicorn

# Envoyer signal HUP pour reload gracieux
docker exec -u root deploy-platform-1 kill -HUP <PID>
```

## ✅ Tests de Validation

### 1. Test de l'API
```bash
# Lister tous les tickets
curl -s http://4.233.64.30/api/tma/tickets | jq .

# Obtenir un ticket spécifique
curl -s http://4.233.64.30/api/tma/tickets/<TICKET_ID> | jq .

# Mettre à jour un ticket
curl -X PUT http://4.233.64.30/api/tma/tickets/<TICKET_ID> \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress","name":"Updated name"}' | jq .

# Supprimer un ticket (soft delete)
curl -X DELETE http://4.233.64.30/api/tma/tickets/<TICKET_ID> | jq .
```

### 2. Test UI
1. Ouvrir http://4.233.64.30/pi
2. Scroller vers section "TMA — Tickets de Maintenance"
3. Cliquer sur un ticket (n'importe quelle vue: card/list/compact)
4. Vérifier que la modale s'ouvre avec formulaire éditable
5. Modifier un champ et cliquer "💾 Enregistrer"
6. Vérifier le toast de confirmation "✅ Ticket mis à jour avec succès"
7. Vérifier que la page se rafraîchit avec les nouvelles données

### 3. Test Suppression
1. Cliquer sur "🗑️ Supprimer" dans la modale
2. Confirmer la suppression
3. Vérifier le toast "✅ Ticket supprimé"
4. Vérifier que le ticket disparaît de la board

## 🐛 Troubleshooting

### Routes API non trouvées (404)
```bash
# Vérifier l'import dans __init__.py
docker exec deploy-platform-1 grep "tma_router" /app/macaron_platform/web/routes/__init__.py

# Redémarrer le serveur
docker restart deploy-platform-1
```

### Modal ne s'ouvre pas
```bash
# Vérifier le JavaScript
docker exec deploy-platform-1 grep -n "openTMAModal" /app/macaron_platform/web/templates/pi_board.html

# Vérifier la console browser (F12) pour erreurs JS
```

### Permissions denied
```bash
# Fixer les permissions
docker exec -u root deploy-platform-1 chown -R appuser:appuser /app/macaron_platform/web/
```

## 📊 Fonctionnalités Déployées

✅ **API REST CRUD**
- GET /api/tma/tickets - Liste avec filtres (status, type, project_id)
- GET /api/tma/tickets/{id} - Détails d'un ticket
- PUT /api/tma/tickets/{id} - Mise à jour (name, description, goal, status, type)
- DELETE /api/tma/tickets/{id} - Suppression soft (archive)

✅ **Modal Éditable**
- Formulaire avec tous les champs éditables
- Dropdowns pour type (bug, security, debt, performance)
- Dropdowns pour status (open, in_progress, resolved, closed)
- Validation client-side (champs requis)
- Boutons "Enregistrer" et "Supprimer"
- Confirmation avant suppression

✅ **UX Améliorée**
- Toast notifications animées (success/error)
- Auto-refresh après modifications
- Click-outside-to-close modal
- Animations CSS (slideIn/slideOut)
- Hover effects sur boutons

## 📝 Notes

- **Soft Delete:** Les tickets ne sont jamais supprimés définitivement, seulement marqués `status='archived'`
- **Auto-Reload:** FastAPI détecte les changements de fichiers et reload automatiquement en dev
- **Cache Template:** Jinja2 peut cacher les templates, attendre ~30s ou redémarrer si besoin
- **Permissions:** Tous les fichiers doivent appartenir à `appuser:appuser`
- **Logs:** Vérifier `/var/log/platform/` dans le container pour erreurs

## 🔗 Liens Utiles

- **Production:** http://4.233.64.30/pi (section TMA)
- **API Docs:** http://4.233.64.30/docs (Swagger UI)
- **GitHub Commit:** 7546e7f7 (feat: TMA CRUD)
- **Local Repo:** /Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY/
