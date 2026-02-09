#!/usr/bin/env python3
"""
Scrape bank transactions via CDP and store in DuckDB.

Scrapes:
- Boursobank: DOM parsing from account operations page
- Crédit Agricole: DOM parsing from synthèse page
- Pagination: follows "Mouvements précédents" links for history

Usage:
    python3 scrapers/scrape_transactions.py          # scrape current month
    python3 scrapers/scrape_transactions.py --months 12  # scrape last 12 months
"""
import asyncio
import json
import re
import sys
import urllib.request
from datetime import datetime, date
from pathlib import Path

CDP_URL = "http://localhost:18800"
DB_PATH = Path(__file__).resolve().parent / "data" / "finary.duckdb"

# ─── DuckDB setup ─────────────────────────────────────────────────────────────

def init_db():
    import duckdb
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect(str(DB_PATH))
    db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id VARCHAR PRIMARY KEY,
            date DATE NOT NULL,
            description VARCHAR NOT NULL,
            amount DOUBLE NOT NULL,
            category VARCHAR,
            subcategory VARCHAR,
            bank VARCHAR NOT NULL,
            account VARCHAR,
            account_id VARCHAR,
            scraped_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            date DATE NOT NULL,
            key VARCHAR NOT NULL,
            value DOUBLE NOT NULL,
            currency VARCHAR DEFAULT 'EUR',
            scraped_at TIMESTAMP DEFAULT current_timestamp,
            PRIMARY KEY (date, key)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            date DATE NOT NULL,
            ticker VARCHAR NOT NULL,
            price DOUBLE NOT NULL,
            currency VARCHAR DEFAULT 'USD',
            source VARCHAR,
            PRIMARY KEY (date, ticker)
        )
    """)
    return db


def tx_id(date_str: str, amount: float, desc: str, bank: str) -> str:
    import hashlib
    key = f"{date_str}|{amount}|{desc}|{bank}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def upsert_transactions(db, transactions: list[dict]):
    if not transactions:
        return 0
    inserted = 0
    for tx in transactions:
        tid = tx_id(tx["date"], tx["amount"], tx["description"], tx["bank"])
        existing = db.execute("SELECT 1 FROM transactions WHERE id = ?", [tid]).fetchone()
        if not existing:
            db.execute("""
                INSERT INTO transactions (id, date, description, amount, category, subcategory, bank, account, account_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [tid, tx["date"], tx["description"], tx["amount"],
                  tx.get("category"), tx.get("subcategory"),
                  tx["bank"], tx.get("account"), tx.get("account_id")])
            inserted += 1
    return inserted


# ─── Bourso scraping ──────────────────────────────────────────────────────────

FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
}


def parse_bourso_date(text: str, fallback_year: int = None) -> str | None:
    """Parse 'vendredi 6 février 2026' → '2026-02-06'"""
    m = re.match(r'\w+\s+(\d+)\s+(\w+)\s+(\d{4})', text.strip())
    if m:
        day = int(m.group(1))
        month = FRENCH_MONTHS.get(m.group(2).lower())
        year = int(m.group(3))
        if month:
            return f"{year}-{month:02d}-{day:02d}"
    return None


def parse_bourso_amount(text: str) -> float | None:
    """Parse '− 1 262,79 €' or '4 900,12 €' → float"""
    text = text.replace('\xa0', ' ').replace('\u202f', ' ').strip()
    neg = text.startswith('−') or text.startswith('-')
    text = re.sub(r'[−\-€]', '', text).strip()
    text = text.replace(' ', '').replace(',', '.')
    try:
        val = float(text)
        return -val if neg else val
    except ValueError:
        return None


async def scrape_bourso_page(ws, page_url: str = None) -> tuple[list[dict], str | None]:
    """Scrape transactions from current Bourso page. Returns (transactions, next_page_url)."""
    
    if page_url:
        await ws.send(json.dumps({'id': 100, 'method': 'Page.navigate', 'params': {'url': page_url}}))
        await ws.recv()
        await asyncio.sleep(4)
    
    # Extract transactions from DOM
    await ws.send(json.dumps({'id': 101, 'method': 'Runtime.evaluate', 'params': {
        'expression': '''
            (() => {
                const body = document.body.innerText;
                // Find "Mouvements précédents" link
                const nextLink = document.querySelector('a[href*="mouvements-precedents"], a[class*="previous"]');
                let nextUrl = null;
                if (!nextLink) {
                    // Try text-based search
                    const allLinks = document.querySelectorAll('a');
                    for (const a of allLinks) {
                        if (a.innerText.includes('Mouvements précédents') || a.innerText.includes('précédent')) {
                            nextUrl = a.href;
                            break;
                        }
                    }
                } else {
                    nextUrl = nextLink.href;
                }
                return JSON.stringify({
                    body: body,
                    nextUrl: nextUrl,
                    url: location.href,
                });
            })()
        ''',
        'returnByValue': True
    }}))
    r = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
    data = json.loads(r['result']['result']['value'])
    
    body = data['body']
    next_url = data.get('nextUrl')
    
    # Parse transactions from body text
    transactions = []
    current_date = None
    lines = body.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Try to parse as date header
        parsed_date = parse_bourso_date(line)
        if parsed_date:
            current_date = parsed_date
            i += 1
            continue
        
        # Try to parse as transaction: description + category + amount pattern
        if current_date and i + 2 < len(lines):
            desc = line
            cat_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            amt_line = lines[i + 2].strip() if i + 2 < len(lines) else ""
            
            amount = parse_bourso_amount(amt_line)
            if amount is not None and desc and len(desc) > 1 and not parse_bourso_date(desc):
                # Skip navigation/footer items
                if any(skip in desc.lower() for skip in [
                    'exporter', 'rechercher', 'critères', 'rubrique', 'relevés',
                    'incidents', 'dons', 'une question', 'aide', 'foire',
                    'copyright', 'mentions', 'politique', 'mes virements',
                    'ma carte', 'rib', 'chèques', 'découvert', 'ajouter',
                    'aller au contenu', 'activer le contraste', 'accueil',
                    'mes comptes', 'services', 'produits', 'parrainage',
                    'cashback', 'bourse', 'afficher', 'consulter', 'gérer',
                    'mouvements à venir', 'solde à venir', 'solde disponible',
                ]):
                    i += 1
                    continue
                
                transactions.append({
                    "date": current_date,
                    "description": desc,
                    "category": cat_line if cat_line and not parse_bourso_amount(cat_line) else None,
                    "amount": amount,
                    "bank": "boursobank",
                    "account": "BOURSORAMA ESSENTIEL SYLVAIN",
                    "account_id": "00040773846",
                })
                i += 3
                continue
        
        i += 1
    
    return transactions, next_url


async def scrape_bourso(ws, max_pages: int = 12) -> list[dict]:
    """Scrape multiple pages of Bourso transactions."""
    all_txs = []
    
    # Start from the account page
    account_url = "https://clients.boursobank.com/compte/cav/fab68d213d98fe597b6cbf7e08d8dd4a/"
    
    # First page: navigate
    txs, next_url = await scrape_bourso_page(ws, account_url)
    all_txs.extend(txs)
    print(f"    → {len(txs)} transactions (total: {len(all_txs)})")
    
    for page_num in range(1, max_pages):
        if not next_url or next_url.startswith('javascript:'):
            # Try clicking "Mouvements précédents" link in DOM
            await ws.send(json.dumps({'id': 150, 'method': 'Runtime.evaluate', 'params': {
                'expression': '''
                    (() => {
                        const links = document.querySelectorAll('a');
                        for (const a of links) {
                            if (a.innerText.includes('Mouvements précédents') || a.innerText.includes('précédent')) {
                                a.click();
                                return 'clicked';
                            }
                        }
                        return 'not_found';
                    })()
                ''',
                'returnByValue': True
            }}))
            r = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            clicked = r.get('result', {}).get('result', {}).get('value', '')
            if clicked != 'clicked':
                print(f"    → No 'Mouvements précédents' link found, stopping")
                break
            await asyncio.sleep(4)
            txs, next_url = await scrape_bourso_page(ws)  # no navigation, page already changed
        else:
            print(f"  Bourso page {page_num + 1}: {next_url[:80]}...")
            txs, next_url = await scrape_bourso_page(ws, next_url)
        
        if not txs:
            print(f"    → 0 transactions, stopping")
            break
        
        all_txs.extend(txs)
        print(f"    → {len(txs)} transactions (total: {len(all_txs)})")
        await asyncio.sleep(2)
    
    return all_txs


# ─── CA scraping ──────────────────────────────────────────────────────────────

async def scrape_ca(ws) -> list[dict]:
    """Scrape CA transactions from synthèse page."""
    # Navigate to CA operations
    await ws.send(json.dumps({'id': 200, 'method': 'Page.navigate', 'params': {
        'url': 'https://www.credit-agricole.fr/ca-languedoc/particulier/operations/synthese.html'
    }}))
    await ws.recv()
    await asyncio.sleep(5)
    
    await ws.send(json.dumps({'id': 201, 'method': 'Runtime.evaluate', 'params': {
        'expression': 'document.body.innerText.substring(0, 8000)',
        'returnByValue': True
    }}))
    r = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
    body = r.get('result', {}).get('result', {}).get('value', '')
    
    # Parse CA operations — format differs from Bourso
    transactions = []
    lines = body.split('\n')
    current_date = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        # CA date format: "06/02/2026" or "06 FEV"
        m = re.match(r'(\d{2})/(\d{2})/(\d{4})', line)
        if m:
            current_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            continue
        
        # Look for amount patterns in subsequent lines
        if current_date and i + 1 < len(lines):
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            amount = parse_bourso_amount(next_line)
            if amount is not None and line and len(line) > 3:
                transactions.append({
                    "date": current_date,
                    "description": line,
                    "amount": amount,
                    "bank": "credit_agricole",
                    "account": "COMPTE CHEQUE",
                    "account_id": "85172056038",
                })
    
    return transactions


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    import websockets
    
    max_pages = 12
    for arg in sys.argv:
        if arg.startswith('--months'):
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                max_pages = int(sys.argv[idx + 1])
    
    db = init_db()
    print(f"DuckDB: {DB_PATH}")
    
    targets = json.loads(urllib.request.urlopen(f'{CDP_URL}/json/list', timeout=5).read())
    
    # Find bank tabs
    bourso_tab = None
    ca_tab = None
    for t in targets:
        url = t.get('url', '')
        if 'bourso' in url and t.get('type') == 'page':
            bourso_tab = t
        elif 'credit-agricole' in url and 'googletagmanager' not in url and t.get('type') == 'page':
            ca_tab = t
    
    all_txs = []
    
    # Scrape Bourso
    if bourso_tab:
        print(f"\n=== Boursobank ===")
        async with websockets.connect(bourso_tab['webSocketDebuggerUrl'], max_size=10*1024*1024) as ws:
            txs = await scrape_bourso(ws, max_pages=max_pages)
            all_txs.extend(txs)
            print(f"  Total Bourso: {len(txs)} transactions")
    else:
        print("⚠ No Bourso tab found")
    
    # Scrape CA
    if ca_tab:
        print(f"\n=== Crédit Agricole ===")
        async with websockets.connect(ca_tab['webSocketDebuggerUrl'], max_size=10*1024*1024) as ws:
            txs = await scrape_ca(ws)
            all_txs.extend(txs)
            print(f"  Total CA: {len(txs)} transactions")
    else:
        print("⚠ No CA tab found")
    
    # Save to DuckDB
    inserted = upsert_transactions(db, all_txs)
    total = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    
    print(f"\n=== Summary ===")
    print(f"  Scraped: {len(all_txs)} transactions")
    print(f"  New: {inserted}")
    print(f"  Total in DB: {total}")
    
    # Show monthly summary
    rows = db.execute("""
        SELECT strftime(date, '%Y-%m') as month,
               bank,
               COUNT(*) as count,
               ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) as income,
               ROUND(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 2) as expenses
        FROM transactions
        GROUP BY month, bank
        ORDER BY month DESC, bank
    """).fetchall()
    
    if rows:
        print(f"\n  {'Mois':10s} {'Banque':15s} {'Nb':>5s} {'Revenus':>12s} {'Dépenses':>12s}")
        for row in rows[:20]:
            print(f"  {row[0]:10s} {row[1]:15s} {row[2]:5d} {row[3]:12,.2f} {row[4]:12,.2f}")
    
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
