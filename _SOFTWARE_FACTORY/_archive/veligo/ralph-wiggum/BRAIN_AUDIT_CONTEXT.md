# BRAIN RLM MISSION: Audit & Fix ALL Broken Endpoints

## AUDIT RÉEL EFFECTUÉ (2026-01-14)

### ERREURS CONSOLE CAPTURÉES EN PRODUCTION

#### 1. gRPC STUBS (NOT IMPLEMENTED)
```
gRPC Error (UNIMPLEMENTED): get_tenant_modules not yet implemented
```
- Affecte: TOUS les sites (idfm, admin, owner, nantes, lyon)
- Service: `veligo.module.v1.ModuleService/GetTenantModules`

#### 2. gRPC 405 Method Not Allowed
```
405 /veligo.module.v1.ModuleService/GetTenantModules
```
- Nginx ne route pas correctement les appels gRPC-Web sur owner.veligo.app

#### 3. REST 404 (Endpoints non implémentés)
```
404 /api/analytics/events          - TOUS les sites
404 /api/errors/client             - TOUS les sites
404 /api/tenants/{id}/theme        - admin, owner
404 /api/tenants/default/config    - admin, owner
```

#### 4. PAGES BLANCHES
- `/signup` - Page complètement blanche
- `/stations` - Page complètement blanche
- Toute page après clic sur CTA

#### 5. LOGIN CASSÉ
- owner.veligo.app affiche identifiants par défaut `owner@veligo.app / owner123!`
- Ces identifiants retournent "Email ou mot de passe incorrect"
- L'utilisateur owner n'existe pas en base ou mauvais hash

#### 6. CSP BLOQUE RESSOURCES EXTERNES
```
Loading stylesheet 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css' violates CSP
Loading script 'https://analytics.veligo.fr/matomo.js' violates CSP
Loading script 'https://client.crisp.chat/l.js' violates CSP
```

#### 7. ERREUR tenant_id VIDE (Reportée par user)
```
gRPC Error (INVALID_ARGUMENT): Invalid tenant_id: invalid length: expected length 32 for simple format, found 0
```
- tenant_id n'est pas propagé dans les appels gRPC
- Intercepteur auth ne set pas le contexte tenant

---

## MISSION DU BRAIN

### OBJECTIF
Générer des tasks T*.md pour corriger TOUS les endpoints cassés et implémenter TOUS les parcours utilisateurs.

### RÈGLES ABSOLUES
1. **PAS DE SLOP** - Code réel, fonctionnel, testé
2. **PAS DE CONTOURNEMENT** - Si un endpoint manque, l'implémenter
3. **PAS D'HALLUCINATION** - Vérifier que le code existe avant de dire qu'il marche
4. **PAS DE MENSONGE** - Tests E2E qui testent vraiment, pas des mocks

### PARCOURS À COUVRIR

#### USER JOURNEY (idfm.veligo.app, nantes.veligo.app, lyon.veligo.app)
1. Homepage → Login → Dashboard
2. Homepage → Signup → Choix plan → Paiement → Confirmation
3. Dashboard → Réserver vélo → Choisir station → Confirmer
4. Dashboard → Voir mes réservations → Annuler
5. Dashboard → Signaler incident → Suivi
6. Dashboard → Mon profil → Modifier infos
7. Dashboard → Mes factures → Télécharger PDF

#### ADMIN JOURNEY (admin.{tenant}.veligo.app)
1. Login admin → Dashboard KPI
2. Dashboard → Gérer utilisateurs → CRUD user
3. Dashboard → Gérer stations → CRUD station
4. Dashboard → Gérer vélos → CRUD bike
5. Dashboard → Voir incidents → Traiter incident
6. Dashboard → Rapports → Export PDF/Excel

#### OWNER JOURNEY (owner.veligo.app)
1. Login owner → Dashboard multi-tenant
2. Dashboard → Créer tenant → Config tenant
3. Dashboard → Gérer admins → CRUD admin
4. Dashboard → Voir métriques globales
5. Dashboard → Config modules par tenant
6. Dashboard → Facturation tenants

### OUTPUT ATTENDU

Pour CHAQUE endpoint/page cassé, générer un fichier `tasks/T{XXX}.md` avec:

```markdown
# Task T{XXX}: {Description courte}

**Priority**: P0|P1|P2
**WSJF Score**: {score}
**Queue**: TDD
**Domain**: {api|frontend|infra}

## Description
{Ce qui est cassé et pourquoi}

## Erreur actuelle
{Message d'erreur exact de la console}

## Solution
{Comment corriger - fichiers à modifier}

## Test E2E
{Parcours utilisateur qui DOIT passer après fix}

## Definition of Done
- [ ] Endpoint implémenté (pas de stub)
- [ ] Test E2E passe en local
- [ ] Test E2E passe en staging
- [ ] Test E2E passe en prod
```

### PRIORISATION

**P0 - BLOQUANT** (empêche tout usage):
- tenant_id propagation
- get_tenant_modules implementation
- Pages blanches (signup, stations)
- Login owner cassé

**P1 - CRITIQUE** (parcours principal cassé):
- Tous les endpoints 404
- gRPC routing nginx
- CSP configuration

**P2 - IMPORTANT** (features secondaires):
- Analytics
- Error reporting

---

## COMMENCER

1. Lister TOUS les fichiers .proto pour identifier les services gRPC
2. Lister TOUS les fichiers +page.svelte pour identifier les routes frontend
3. Pour chaque service gRPC, vérifier si implémenté ou stub
4. Pour chaque route frontend, vérifier si backend connecté
5. Générer les tasks par ordre de priorité WSJF
