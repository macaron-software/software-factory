# Browser Setup — Scraping & Session Management

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Google Chrome (real, /Applications/...)         │
│  Port 18800 — CDP (Chrome DevTools Protocol)     │
│  User-data: scrapers/data/.browser_state         │
│                                                  │
│  Tabs:                                           │
│    🏦 Crédit Agricole  (ca-languedoc)            │
│    🏦 Boursobank                                 │
│    🏦 Interactive Brokers (IBKR)                 │
│    🏦 Trade Republic                             │
│                                                  │
│  Session keepalive daemon (ping every 2min)      │
└─────────────────────────────────────────────────┘
         ▲ CDP websocket
         │
┌────────┴────────┐    ┌──────────────┐
│ Scrapers        │    │ API Server   │
│ (Python/asyncio)│    │ (:8000)      │
│                 │    │ reads JSON   │
│ daily_sync.py   │    │ from data/   │
│ scrape_cdp.py   │    └──────────────┘
│ session_keepalive│
└─────────────────┘
```

## Pourquoi Chrome réel (pas Chrome for Testing)

| | Chrome for Testing | Chrome réel |
|---|---|---|
| TLS fingerprint | Non-standard → détecté | Standard |
| FingerprintJS | Bloqué (HTTP 418/ERR_CONNECTION_RESET) | ✅ Passe |
| SwiftShader GPU | `--enable-unsafe-swiftshader` → **200%+ CPU** | GPU natif, ~2% CPU |
| Crédit Agricole | ❌ Bloqué | ✅ Fonctionne |
| Boursobank | ✅ OK | ✅ OK |

**Chrome for Testing** est conçu pour les tests automatisés, pas pour le scraping bancaire.
Son empreinte TLS et ses flags (`--enable-automation`) sont détectés par les WAF/anti-bot.

## Lancement

### Démarrage rapide

```bash
# 1. Lancer le browser (si pas déjà ouvert)
./scrapers/launch_browser.sh

# 2. Se loguer manuellement sur les 4 banques

# 3. Lancer le stack
./start.sh
```

### Démarrage manuel du browser

```bash
open -n -a "Google Chrome" --args \
  --remote-debugging-port=18800 \
  --user-data-dir="$(pwd)/scrapers/data/.browser_state" \
  --no-first-run --no-default-browser-check --disable-sync --lang=fr-FR
```

> **⚠️ `open -n`** force une nouvelle instance Chrome séparée de ton Chrome perso.

### Keepalive daemon

```bash
# Démarrer en arrière-plan
python3 scrapers/session_keepalive.py --daemon

# Vérifier le log
tail -f /tmp/session-keepalive.log

# Arrêter
kill $(cat /tmp/session-keepalive.pid)
```

Le daemon ping chaque onglet bancaire toutes les **2 minutes** via `fetch(HEAD)` en JS.
Il ne navigue jamais, ne clique pas, ne change pas d'URL.

**Statuts possibles :**
- `✅ ping=ok` — Session active, cookie rafraîchi
- `⚠ LOGGED OUT` — Session expirée, re-login nécessaire
- `⏱ timeout` — Page ne répond pas (reload nécessaire)
- `❌ error` — Problème websocket

## Port 18800

Tous les scrapers utilisent `http://localhost:18800` pour se connecter au browser.

**Fichiers configurés :**
- `scrapers/session_keepalive.py` — CDP_URL
- `scrapers/keep_alive.py` — CDP_URL
- `scrapers/scrape_cdp.py` — CDP_URL
- `scrapers/scrape_cdp_v2.py` — CDP_URL
- `scrapers/scrape_final.py` — CDP_URL
- `scrapers/scrape_loan_details.py` — connect_over_cdp
- `scrapers/daily_sync.py` — CDP_URL
- `scrapers/scrape_details.py` — remote-debugging-port
- `start.sh` — health check

## Troubleshooting

### "ERR_CONNECTION_RESET" sur Crédit Agricole
→ Tu utilises Chrome for Testing. Relance avec le vrai Chrome.

### GPU process à 100%+ CPU
→ Chrome for Testing utilise SwiftShader (rendu GPU logiciel).
   Relance avec `--disable-gpu` ou utilise le vrai Chrome.

### Sessions expirent
→ Vérifie que le keepalive daemon tourne : `cat /tmp/session-keepalive.pid | xargs ps`

### "LOGGED OUT" dans les logs keepalive
→ La banque a expiré la session malgré le ping. Re-login manuel nécessaire.
   Certaines banques (Bourso) expirent après ~15min d'inactivité quel que soit le ping.

### Impossible de lancer Chrome ("profile locked")
```bash
rm -f scrapers/data/.browser_state/SingletonLock
rm -f scrapers/data/.browser_state/SingletonSocket
rm -f scrapers/data/.browser_state/SingletonCookie
```
