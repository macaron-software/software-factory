# Schéma de Données — Software Factory

> **Status:** 🚧 À compléter (phase Discovery)

## Entités principales

```
Entity: NomEntite
  - id: UUID (PK)
  - created_at: timestamp
  - ...
```

## Relations

```
NomEntite 1---* AutreEntite
```

## Flux de données

1. *Source* → *Transformation* → *Destination*

---
*Généré par Software Factory — à compléter par l'agent architecte*
