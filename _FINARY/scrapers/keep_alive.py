"""
Keep-alive: recharge les pages bancaires via WebSocket CDP toutes les 4 min.
Envoie Page.reload sur chaque onglet bancaire pour maintenir la session serveur active.
"""
import json
import time
import urllib.request

CDP_URL = "http://127.0.0.1:9222"
INTERVAL = 4 * 60  # 4 minutes
BANK_DOMAINS = [
    "credit-agricole",
    "ca-languedoc",
    "ca-centrest",
    "interactivebrokers",
    "boursobank.com",
    "traderepublic.com",
]


def get_bank_tabs():
    """Get all open bank tabs from CDP."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json") as resp:
            tabs = json.loads(resp.read())
        return [t for t in tabs
                if any(d in t.get("url", "") for d in BANK_DOMAINS)
                and "googletagmanager" not in t.get("url", "")
                and t.get("type") == "page"]
    except Exception as e:
        print(f"[KEEP-ALIVE] CDP unreachable: {e}")
        return []


def reload_tab(tab):
    """Reload the tab via WebSocket CDP Page.reload command."""
    import websocket
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print(f"[KEEP-ALIVE] ✗ No WS URL for {tab['url'][:50]}")
        return False
    try:
        ws = websocket.create_connection(ws_url, timeout=10,
                                          suppress_origin=True)
        # Page.reload with ignoreCache=False (soft reload, keeps session cookies)
        ws.send(json.dumps({"id": 1, "method": "Page.reload",
                            "params": {"ignoreCache": False}}))
        result = ws.recv()
        ws.close()
        domain = tab["url"].split("/")[2][:35]
        print(f"[KEEP-ALIVE] ✓ reloaded {domain}", flush=True)
        return True
    except Exception as e:
        print(f"[KEEP-ALIVE] ✗ {tab['url'][:50]} — {e}")
        return False


def main():
    print(f"[KEEP-ALIVE] Started — reloading bank pages every {INTERVAL}s", flush=True)
    cycle = 0
    while True:
        tabs = get_bank_tabs()
        if not tabs:
            print(f"[KEEP-ALIVE] No bank tabs found, retrying in {INTERVAL}s...", flush=True)
        else:
            ok = sum(1 for t in tabs if reload_tab(t))
            cycle += 1
            print(f"[KEEP-ALIVE] Cycle {cycle}: {ok}/{len(tabs)} tabs reloaded", flush=True)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
