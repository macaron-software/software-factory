"""
Keep-alive: rafraîchit les sessions bancaires ouvertes dans Chrome CDP toutes les 5 min.
Utilise l'API HTTP CDP pour naviguer sur la même URL (soft refresh) sans fermer/rouvrir.
"""
import json
import time
import urllib.request

CDP_URL = "http://127.0.0.1:9222"
INTERVAL = 5 * 60  # 5 minutes
BANK_DOMAINS = [
    "credit-agricole.fr",
    "interactivebrokers",
    "boursobank.com",
    "traderepublic.com",
]

def get_bank_tabs():
    """Get all open bank tabs from CDP."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json") as resp:
            tabs = json.loads(resp.read())
        return [t for t in tabs if any(d in t.get("url", "") for d in BANK_DOMAINS)]
    except Exception as e:
        print(f"[KEEP-ALIVE] CDP unreachable: {e}")
        return []

def ping_tab(tab):
    """Activate the tab via CDP HTTP API to keep session alive."""
    tab_id = tab["id"]
    try:
        req = urllib.request.Request(f"{CDP_URL}/json/activate/{tab_id}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        domain = tab["url"].split("/")[2][:35]
        print(f"[KEEP-ALIVE] ✓ {domain}")
        return True
    except Exception as e:
        print(f"[KEEP-ALIVE] ✗ {tab['url'][:50]} — {e}")
        return False

def main():
    print(f"[KEEP-ALIVE] Started — pinging bank sessions every {INTERVAL}s")
    cycle = 0
    while True:
        tabs = get_bank_tabs()
        if not tabs:
            print(f"[KEEP-ALIVE] No bank tabs found, retrying in {INTERVAL}s...")
        else:
            ok = sum(1 for t in tabs if ping_tab(t))
            cycle += 1
            print(f"[KEEP-ALIVE] Cycle {cycle}: {ok}/{len(tabs)} tabs alive")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
