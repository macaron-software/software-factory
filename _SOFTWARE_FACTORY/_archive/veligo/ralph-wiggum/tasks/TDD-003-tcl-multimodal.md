# TDD-003: TCL Multimodal Lyon Integration

**Anomalie:** #3 - TCL Multimodal Non Implémenté (15 tests SKIPPED)  
**Priorité:** P0 - CRITICAL BLOCKER  
**AO Référence:** AO-LYON-§4.2.1  
**Fichier Source:** `tests/e2e/journeys/lyon-tcl-multimodal-full.spec.ts`

## 🎯 Objectif

Implémenter intégration TCL Multimodal pour Lyon tenant selon AO-LYON-§4.2.1

## 📋 Tasks Détaillées

### Phase 1: TCL Open Data API Integration
- [ ] Créer compte développeur TCL Open Data
- [ ] Implémenter client API TCL (base URL, auth)
- [ ] Implémenter endpoint real-time arrivals (`/api/tcl/real-time`)
- [ ] Implémenter endpoint stations list (`/api/tcl/stations`)
- [ ] Implémenter endpoint lines/routes (`/api/tcl/lines`)

### Phase 2: Caching Strategy
- [ ] Configurer Redis pour cache TCL
- [ ] Implémenter cache 30 secondes
- [ ] Implémenter fallback sur cache si API down
- [ ] Implémenter stale-while-revalidate

### Phase 3: Rate Limiting Handling
- [ ] Implémenter detection 429 responses
- [ ] Implémenter exponential backoff
- [ ] Implémenter retry automatique (max 3)
- [ ] Show cached data avec alert

### Phase 4: Multimodal Route Planner
- [ ] Créer algorithme route planning
- [ ] Intégrer TCL + Véligo dans résultats
- [ ] Calculer durées combinées
- [ ] Calculer coûts combinés
- [ ] Implementer step-by-step instructions

### Phase 5: Map Overlay
- [ ] Intégrer stations TCL sur map (Leaflet/Mapbox)
- [ ] Filtres metro/tram/bus
- [ ] Info popup avec arrivals
- [ ] Toggle visibilityTCL stations

### Phase 6: Combined Subscriptions
- [ ] Créer plan TCL + Véligo combo
- [ ] Implémenter pricing bundle (59.90€ vs 65€)
- [ ] Implémenter linking TCL card
- [ ] Display combined stats

### Phase 7: Tests E2E
- [ ] Activer tests Real-Time Data (AC-001 à AC-005)
- [ ] Activer tests Itinerary Planning (AC-006 à AC-010)
- [ ] Activer tests Subscriptions (AC-011 à AC-013)
- [ ] Activer tests Error Handling (AC-014 à AC-015)

## 🔗 Fichiers à Créer/Modifier

```
backend/
├── src/
│   ├── services/
│   │   ├── tcl_client.rs
│   │   ├── tcl_cache.rs
│   │   ├── route_planner.rs
│   │   └── multimodal_service.rs
│   └── routes/
│       └── tcl.rs

frontend/
├── src/
│   ├── maps/
│   │   ├── TCLMarkers.svelte
│   │   └── TCLOverlay.svelte
│   ├── planner/
│   │   ├── MultimodalPlanner.svelte
│   │   └── RouteResult.svelte
│   ├── subscription/
│   │   └── TCLComboPlan.svelte
│   └── stats/
│       └── MultimodalStats.svelte

tests/e2e/journeys/lyon-tcl-multimodal-full.spec.ts
```

## ✅ Criteria Definition

| AC | Criteria | Test |
|----|----------|------|
| AC-001 | TCL stations affichées sur map | ✅ |
| AC-002 | Real-time arrivals affichés | ✅ |
| AC-003 | Auto-refresh 30 secondes | ✅ |
| AC-004 | Fallback sur API down | ✅ |
| AC-005 | Filtres metro/tram/bus | ✅ |
| AC-006 | Itinéraires TCL + Bike | ✅ |
| AC-007 | Instructions step-by-step | ✅ |
| AC-008 | Coût combiné affiché | ✅ |
| AC-009 | Routes favorites sauvegardées | ✅ |
| AC-010 | Rerouting sur delay | ✅ |
| AC-011 | Plan combo TCL+Véligo visible | ✅ |
| AC-012 | Linking TCL card | ✅ |
| AC-013 | Stats multimodales | ✅ |
| AC-014 | Message pas de TCL nearby | ✅ |
| AC-015 | Rate limit handling 429 | ✅ |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| TCL API Integration | 4h | - |
| Caching Strategy | 2h | Phase 1 |
| Rate Limiting | 2h | Phase 1 |
| Route Planner | 6h | Phases 1-3 |
| Map Overlay | 4h | Phase 1 |
| Combined Subscriptions | 3h | - |
| Tests E2E | 2h | Phases 1-6 |

**Total estimé:** 23h
