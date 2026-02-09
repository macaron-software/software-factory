#!/usr/bin/env python3
"""
Session Keep-Alive Daemon — prevents bank sessions from expiring.

Runs every 2 minutes, sends a lightweight JS ping on each bank tab
via CDP websocket. Does NOT navigate, click, or change URLs.

Usage:
    python3 scrapers/session_keepalive.py          # foreground
    python3 scrapers/session_keepalive.py --daemon  # background (writes to /tmp/session-keepalive.log)

Kill:
    kill $(cat /tmp/session-keepalive.pid)
"""
import asyncio
import json
import os
import sys
import signal
import urllib.request
from datetime import datetime

CDP_URL = "http://localhost:18800"
INTERVAL = 120  # seconds between pings
LOG_FILE = "/tmp/session-keepalive.log"
PID_FILE = "/tmp/session-keepalive.pid"

# Lightweight JS that triggers cookie/session refresh without visible side effects
KEEPALIVE_JS = {
    "credit-agricole": "fetch(document.location.href, {method:'HEAD',credentials:'include'}).then(()=>'ok').catch(()=>'err')",
    "bourso": "fetch(document.location.href, {method:'HEAD',credentials:'include'}).then(()=>'ok').catch(()=>'err')",
    "interactive": "fetch(document.location.href,{method:'HEAD',credentials:'include'}).then(()=>'ok').catch(()=>'err')",
    "traderepublic": "fetch(document.location.href, {method:'HEAD',credentials:'include'}).then(()=>'ok').catch(()=>'err')",
}


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def detect_bank(url: str) -> str | None:
    for key in KEEPALIVE_JS:
        if key in url:
            return key
    return None


def is_logged_out(text: str) -> bool:
    lower = text.lower()[:300]
    return any(kw in lower for kw in [
        "se connecter", "connexion", "mot de passe", "identifiant",
        "sign in", "log in", "authentication",
    ])


async def ping_page(ws_url: str, bank: str, page_url: str) -> str:
    """Send keepalive ping to a single page. Returns status string."""
    import websockets
    try:
        async with websockets.connect(ws_url, open_timeout=5, close_timeout=3) as ws:
            # 1. Check if still logged in (read-only)
            await ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": "document.body?.innerText?.substring(0,300) || ''"}
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            text = resp.get("result", {}).get("result", {}).get("value", "")

            if is_logged_out(text):
                return "⚠ LOGGED OUT"

            # 2. Send keepalive fetch (background, no navigation)
            js = KEEPALIVE_JS.get(bank, "Promise.resolve('skip')")
            await ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js,
                    "awaitPromise": True,
                    "returnByValue": True,
                }
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            val = resp.get("result", {}).get("result", {}).get("value", "?")
            return f"✅ ping={val}"
    except asyncio.TimeoutError:
        return "⏱ timeout"
    except Exception as e:
        return f"❌ {type(e).__name__}: {e}"


async def keepalive_loop():
    log(f"Session keepalive started (every {INTERVAL}s)")
    while True:
        try:
            raw = urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=3).read()
            pages = json.loads(raw)
        except Exception as e:
            log(f"CDP unreachable: {e}")
            await asyncio.sleep(INTERVAL)
            continue

        results = []
        for p in pages:
            url = p.get("url", "")
            bank = detect_bank(url)
            if not bank:
                continue
            ws_url = p.get("webSocketDebuggerUrl", "")
            if not ws_url:
                continue
            status = await ping_page(ws_url, bank, url)
            results.append(f"{bank:20} {status}")

        if results:
            log(" | ".join(results))
        else:
            log("No bank tabs found")

        await asyncio.sleep(INTERVAL)


def daemonize():
    """Fork to background."""
    # Kill existing daemon
    if os.path.exists(PID_FILE):
        try:
            old_pid = int(open(PID_FILE).read().strip())
            os.kill(old_pid, signal.SIGTERM)
            log(f"Killed old daemon (PID {old_pid})")
        except (ProcessLookupError, ValueError):
            pass

    pid = os.fork()
    if pid > 0:
        print(f"Session keepalive daemon started (PID {pid})")
        print(f"  Log: {LOG_FILE}")
        print(f"  PID: {PID_FILE}")
        print(f"  Kill: kill $(cat {PID_FILE})")
        sys.exit(0)

    # Child process
    os.setsid()
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Redirect stdout/stderr to log
    sys.stdout = open(LOG_FILE, "a", buffering=1)
    sys.stderr = sys.stdout


def main():
    if "--daemon" in sys.argv:
        daemonize()

    try:
        asyncio.run(keepalive_loop())
    except KeyboardInterrupt:
        log("Stopped")


if __name__ == "__main__":
    main()
