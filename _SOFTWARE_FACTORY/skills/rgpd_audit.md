# RGPD Audit — Skill Prompt

## Objectif
Auditer la conformité RGPD d'une feature, d'un module ou d'un système complet.

## Checklist RGPD (articles clés)

### 1. Base légale (Art. 6)
- [ ] Consentement explicite, libre, éclairé, spécifique ?
- [ ] Ou contrat (nécessaire à l'exécution) ?
- [ ] Ou intérêt légitime (balance des intérêts documentée) ?
- [ ] Ou obligation légale ?
- [ ] Base légale documentée dans le registre des traitements ?

### 2. Minimisation (Art. 5.1.c)
- [ ] Seules les données strictement nécessaires sont collectées ?
- [ ] Pas de champs "au cas où" ou "pour plus tard" ?
- [ ] Données sensibles (Art. 9) justifiées et protégées ?

### 3. Finalité (Art. 5.1.b)
- [ ] Finalité claire, explicite, légitime ?
- [ ] Pas de détournement de finalité ?
- [ ] Information de la personne sur la finalité ?

### 4. Conservation (Art. 5.1.e)
- [ ] Durée de conservation définie et justifiée ?
- [ ] Purge automatique implémentée ?
- [ ] Archivage intermédiaire vs suppression ?

### 5. Droits des personnes (Art. 15-22)
- [ ] Droit d'accès : endpoint /api/me/data ?
- [ ] Droit de rectification : modification possible ?
- [ ] Droit d'effacement : suppression complète (cascade) ?
- [ ] Droit à la portabilité : export JSON/CSV ?
- [ ] Droit d'opposition : opt-out fonctionnel ?
- [ ] Droit à la limitation : gel du traitement ?

### 6. Sécurité (Art. 32)
- [ ] Chiffrement au repos (AES-256) ?
- [ ] Chiffrement en transit (TLS 1.2+) ?
- [ ] Pseudonymisation si possible ?
- [ ] Logs d'accès aux données personnelles ?

### 7. Sous-traitants (Art. 28)
- [ ] Contrat avec chaque sous-traitant (clause RGPD) ?
- [ ] Registre des sous-traitants à jour ?
- [ ] Transferts hors UE : clauses contractuelles types ?

### 8. PIA — Analyse d'Impact (Art. 35)
- [ ] Traitement à grande échelle ?
- [ ] Profilage ou scoring ?
- [ ] Données sensibles (santé, biométrie, opinions) ?
- [ ] Croisement de données ?
- [ ] Si oui → PIA obligatoire, documenté

## Anti-patterns à rejeter
- Stockage de mot de passe en clair
- Logs contenant des données personnelles non masquées
- Cookies traceurs sans consentement préalable
- Email en clair dans les URLs
- Pas de mentions légales / politique de confidentialité
- Consentement pré-coché (invalide)
- Pas de mécanisme de suppression de compte

## Template de rapport
```
## Audit RGPD — [Module/Feature]
**Date:** YYYY-MM-DD
**Auditeur:** DPO
**Résultat:** ✅ Conforme / ⚠️ Non-conformités mineures / ❌ Non-conforme

### Traitements identifiés
| Donnée | Finalité | Base légale | Conservation | Sous-traitant |
|--------|----------|-------------|--------------|---------------|

### Non-conformités
| # | Gravité | Description | Article RGPD | Action corrective |
|---|---------|-------------|--------------|-------------------|

### Recommandations
1. ...
```
