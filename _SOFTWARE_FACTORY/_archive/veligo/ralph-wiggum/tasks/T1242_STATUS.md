# T1242 - Supprimer REST routes de http-server.rs

**Status:** ✅ COMPLETE

**Date:** 2026-01-14

## Résumé

La tâche T1242 est déjà complète. Le fichier `http-server.rs` a été correctement configuré pour:
- ✅ Supprimer les routes REST dupliquées
- ✅ Garder uniquement les OAuth callbacks et webhooks
- ✅ Utiliser les routes gRPC-Web pour bookings et stations

## Vérification

### Routes configurées dans http-server.rs

```rust
// gRPC-Web (KEEP)
.merge(booking_grpc_web_routes())
.merge(station_grpc_web_routes())

// OAuth callbacks (KEEP)
.nest("/api/auth/franceconnect", franceconnect_routes())
.nest("/api/auth/google", google_oauth_routes(...))
.nest("/api/auth/microsoft", microsoft_oauth_routes(...))

// Webhooks (KEEP)
.nest("/api/webhooks", webhooks::routes(...))
```

### Routes REST supprimées

Les routes REST suivantes ont été supprimées de http-server.rs:
- `/api/auth/*` → Utilise gRPC via nginx proxy
- `/api/stations/*` → Utilise `station_grpc_web_routes`
- `/api/bookings/*` → Utilise `booking_grpc_web_routes`
- `/api/subscriptions/*` → Utilise gRPC via nginx proxy

## Notes

Les erreurs de compilation préexistantes (modules manquants, crates manquants) ne sont pas liées à T1242.
