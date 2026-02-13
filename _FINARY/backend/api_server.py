"""
Finary Clone — API Server
Serves real scraped patrimoine data to the Next.js frontend.
Reads from scrapers/data/patrimoine_complet_*.json
Live market prices via yfinance.
"""
import json
import math
import uuid
import random
import time
import threading
from pathlib import Path
from datetime import date, timedelta
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.insights_engine import (
    compute_diversification, analyze_loans, compute_fees,
    generate_insights, compute_projections,
    load_transactions, aggregate_monthly_budget, categorize_transaction,
    INFLATION_RATE,
)

app = FastAPI(title="Finary Clone API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Load Data ────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "scrapers" / "data"
DB_PATH = DATA_DIR / "finary.duckdb"

def _get_duckdb():
    """Get a DuckDB connection."""
    import duckdb
    return duckdb.connect(str(DB_PATH))

def _persist_market_prices(ticker: str, rows: list[dict]):
    """Persist OHLCV rows to DuckDB market_prices table."""
    if not DB_PATH.exists() or not rows:
        return
    try:
        con = _get_duckdb()
        con.execute("""CREATE TABLE IF NOT EXISTS market_prices (
            date DATE, ticker VARCHAR, open DECIMAL(12,4), high DECIMAL(12,4),
            low DECIMAL(12,4), close DECIMAL(12,4), volume BIGINT, currency VARCHAR,
            PRIMARY KEY (date, ticker)
        )""")
        for r in rows:
            con.execute("""INSERT OR REPLACE INTO market_prices
                (date, ticker, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [r["date"], ticker, r["open"], r["high"], r["low"], r["close"], r["volume"]])
        con.close()
    except Exception as e:
        print(f"[DB] market_prices persist error: {e}")

def _persist_snapshot():
    """Store daily net worth snapshot in DuckDB."""
    if not DB_PATH.exists():
        return
    try:
        con = _get_duckdb()
        con.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            date DATE, key VARCHAR, value DECIMAL(15,2), currency VARCHAR DEFAULT 'EUR',
            PRIMARY KEY (date, key)
        )""")
        today = date.today().isoformat()
        totals = P.get("totals", {})
        snapshots = {
            "net_worth": totals.get("net_worth", 0),
            "total_assets": totals.get("total_assets", 0),
            "total_liabilities": totals.get("total_liabilities", 0),
            "portfolio_value": totals.get("portfolio_value", 0),
            "cash": totals.get("cash_eur", 0),
            "real_estate": totals.get("real_estate_net", 0),
        }
        for key, value in snapshots.items():
            con.execute("INSERT OR REPLACE INTO snapshots (date, key, value) VALUES (?, ?, ?)",
                        [today, key, round(float(value), 2)])
        con.close()
        print(f"[SNAPSHOT] Saved {len(snapshots)} values for {today}")
    except Exception as e:
        print(f"[SNAPSHOT] Error: {e}")

def load_patrimoine():
    files = sorted(DATA_DIR.glob("patrimoine_complet_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No patrimoine_complet_*.json found in scrapers/data/")
    with open(files[0]) as f:
        return json.load(f)

P = load_patrimoine()

# Load extraction_complete for reliable avg_price (from TR detail page click)
def load_extraction_avg_prices():
    """Load avg_price per TR position from extraction_complete (detail page scrape)."""
    files = sorted(DATA_DIR.glob("extraction_complete_*.json"), reverse=True)
    avg_prices = {}  # name → avg_price
    for f in files:
        try:
            ext = json.load(open(f))
            for p in ext.get("tr_positions", []):
                name = p.get("name", "")
                avg = p.get("avg_price")
                if name and avg and avg > 0 and name not in avg_prices:
                    avg_prices[name] = avg
        except Exception:
            continue
    return avg_prices

TR_AVG_PRICES = load_extraction_avg_prices()

# DCA-period average prices (Feb-Jul 2025) for positions missing extraction avg_price
# Computed from yfinance historical data, converted to EUR at ~1.10 EUR/USD
TR_DCA_FALLBACK = {
    "Allianz": 336.50,
    "Exxon Mobil": 96.92,
    "Johnson & Johnson": 140.46,
    "Plug Power": 1.20,
    "Sanofi": 91.59,
    "S&P 500 Information Tech USD (Acc)": 29.95,
    "MercadoLibre": 2056.23,
    "Soitec": 51.59,
    "Sea (ADR)": 128.85,
    "Rheinmetall": 1470.03,
}
# Merge: extraction_complete wins, DCA fallback fills gaps
for name, avg in TR_DCA_FALLBACK.items():
    TR_AVG_PRICES.setdefault(name, avg)

@app.post("/api/v1/reload")
def reload_patrimoine():
    """Hot-reload patrimoine data from disk."""
    global P
    P = load_patrimoine()
    return {"status": "ok", "date": P.get("date", "?")}

# ─── Live Market Data ─────────────────────────────────────────────────────────

# ISIN → Yahoo Finance ticker mapping
ISIN_TO_TICKER = {
    "US0231351067": "AMZN", "NL0000226223": "STM", "FR0000120321": "OR.PA",
    "CNE100000296": "1211.HK", "US60770K1079": "MRNA", "DE0008404005": "ALV.DE",
    "US30231G1022": "XOM", "FR0000121014": "MC.PA", "US7561091049": "O",
    "US46120E6023": "ISRG", "FR0000120271": "TTE.PA", "US4781601046": "JNJ",
    "US29355A1079": "ENPH", "US72919P2020": "PLUG", "FR0000120578": "SAN.PA",
    "IE00B3WJKG14": "IUIT.L", "US58733R1023": "MELI", "FR0013227113": "SOI.PA",
    "CA1363751027": "CNR.TO", "US81141R1005": "SE", "DE0007030009": "RHM.DE",
    "US4612021034": "INTU",
    "US5949181045": "MSFT", "US02079K3059": "GOOGL", "US67066G1040": "NVDA",
}

# Cache for live prices
_price_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes

def _fetch_live_prices():
    """Fetch all stock prices + EUR/USD. Batch first, then individual fallback."""
    try:
        import yfinance as yf
        tickers_list = list(set(ISIN_TO_TICKER.values())) + ["EURUSD=X", "HKDEUR=X", "CADEUR=X"]
        now = time.time()

        # Batch download
        try:
            data = yf.download(tickers_list, period="1d", progress=False, threads=True)
            with _cache_lock:
                for ticker in tickers_list:
                    try:
                        if len(tickers_list) > 1:
                            close = data["Close"][ticker].iloc[-1]
                        else:
                            close = data["Close"].iloc[-1]
                        if not math.isnan(close):
                            _price_cache[ticker] = {"price": float(close), "ts": now}
                    except (KeyError, IndexError):
                        pass
        except Exception as e:
            print(f"[MARKET] Batch error: {e}")

        # Individual fallback for missed tickers
        missed = [t for t in tickers_list if t not in _price_cache]
        for ticker in missed:
            try:
                t = yf.Ticker(ticker)
                price = t.fast_info.get("lastPrice") or t.fast_info.get("last_price")
                if price and not math.isnan(price):
                    with _cache_lock:
                        _price_cache[ticker] = {"price": float(price), "ts": now}
            except Exception:
                pass

        print(f"[MARKET] Fetched {len(_price_cache)}/{len(tickers_list)} prices (missed: {len(missed) - sum(1 for t in missed if t in _price_cache)})")
    except Exception as e:
        print(f"[MARKET] Error: {e}")

def get_live_price(ticker: str) -> float | None:
    with _cache_lock:
        cached = _price_cache.get(ticker)
        if cached and time.time() - cached["ts"] < _CACHE_TTL:
            return cached["price"]
    return None

def get_eur_usd() -> float:
    rate = get_live_price("EURUSD=X")
    return rate if rate else 1.08  # fallback

# Fetch prices on startup + periodic refresh
def _price_refresh_loop():
    _fetch_live_prices()
    while True:
        time.sleep(_CACHE_TTL)
        _fetch_live_prices()

threading.Thread(target=_price_refresh_loop, daemon=True).start()

# ─── Sector/Country mapping for diversification ──────────────────────────────

SECTOR_MAP = {
    "US0231351067": ("Technology", "US"),       # Amazon
    "NL0000226223": ("Semiconductors", "NL"),   # STMicro
    "FR0000120321": ("Consumer", "FR"),          # L'Oreal
    "CNE100000296": ("Automotive", "CN"),        # BYD
    "US60770K1079": ("Healthcare", "US"),        # Moderna
    "DE0008404005": ("Finance", "DE"),           # Allianz
    "US30231G1022": ("Energy", "US"),            # Exxon
    "FR0000121014": ("Luxury", "FR"),            # LVMH
    "US7561091049": ("Real Estate", "US"),       # Realty Income
    "US46120E6023": ("Healthcare", "US"),        # Intuitive Surgical
    "FR0000120271": ("Energy", "FR"),            # TotalEnergies
    "US4781601046": ("Healthcare", "US"),        # J&J
    "US29355A1079": ("Energy", "US"),            # Enphase
    "US72919P2020": ("Energy", "US"),            # Plug Power
    "FR0000120578": ("Healthcare", "FR"),        # Sanofi
    "IE00B3WJKG14": ("Technology", "IE"),        # S&P 500 IT ETF
    "US58733R1023": ("Technology", "BR"),        # MercadoLibre
    "FR0013227113": ("Semiconductors", "FR"),    # Soitec
    "CA1363751027": ("Industrials", "CA"),       # CN Railway
    "US81141R1005": ("Technology", "SG"),        # Sea
    "DE0007030009": ("Defense", "DE"),           # Rheinmetall
    "US4612021034": ("Technology", "US"),        # Intuit
    "US5949181045": ("Technology", "US"),        # MSFT
    "US02079K3059": ("Technology", "US"),        # GOOGL
    "US67066G1040": ("Semiconductors", "US"),    # NVDA
}

COUNTRY_NAMES = {
    "US": "États-Unis", "FR": "France", "DE": "Allemagne", "NL": "Pays-Bas",
    "CN": "Chine", "IE": "Irlande", "BR": "Brésil", "CA": "Canada", "SG": "Singapour",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _id(prefix: str, i: int) -> str:
    return f"{prefix}-{i:04d}"

# ─── Build accounts list ─────────────────────────────────────────────────────

def build_accounts():
    accounts = []
    i = 0

    # Trade Republic
    tr = P["trade_republic"]
    i += 1
    accounts.append({
        "id": _id("acc", i), "institution_id": "trade_republic",
        "institution": "trade_republic", "institution_display_name": "Trade Republic",
        "external_id": None, "name": "CTO Trade Republic",
        "account_type": "cto", "currency": "EUR",
        "balance": tr["total_account_value"], "is_pro": False,
        "updated_at": P["date"],
    })

    # IBKR
    ibkr = P["ibkr"]
    i += 1
    accounts.append({
        "id": _id("acc", i), "institution_id": "ibkr",
        "institution": "ibkr", "institution_display_name": "Interactive Brokers",
        "external_id": ibkr["account_id"], "name": "CTO Margin IBKR",
        "account_type": "cto", "currency": "EUR",
        "balance": ibkr["net_liquidation_eur"], "is_pro": False,
        "updated_at": P["date"],
    })

    # Boursobank
    b = P["boursobank"]
    for key, acc_data in b["accounts"].items():
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "boursobank",
            "institution": "boursobank", "institution_display_name": "Boursobank",
            "external_id": acc_data.get("account"), "name": acc_data["label"],
            "account_type": acc_data.get("type", "checking").lower(),
            "currency": "EUR", "balance": acc_data["balance"],
            "is_pro": False, "updated_at": P["date"],
        })
    for key, acc_data in b["children_accounts"].items():
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "boursobank",
            "institution": "boursobank", "institution_display_name": "Boursobank",
            "external_id": None, "name": acc_data["label"],
            "account_type": "savings" if "livret" in key.lower() else "checking",
            "currency": "EUR", "balance": acc_data["balance"],
            "is_pro": False, "updated_at": P["date"],
            "owner": "Nathael", "excluded": True,
        })
    for loan in b["loans"]:
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "boursobank",
            "institution": "boursobank", "institution_display_name": "Boursobank",
            "external_id": None, "name": loan["name"],
            "account_type": "loan", "currency": "EUR",
            "balance": -loan["remaining"], "is_pro": False,
            "updated_at": P["date"],
        })

    # Crédit Agricole
    ca = P["credit_agricole"]
    ca_acc = ca["accounts"]["checking"]
    i += 1
    accounts.append({
        "id": _id("acc", i), "institution_id": "credit_agricole",
        "institution": "credit_agricole", "institution_display_name": "Crédit Agricole",
        "external_id": ca_acc.get("account"), "name": ca_acc["label"],
        "account_type": "checking", "currency": "EUR",
        "balance": ca_acc["balance"], "is_pro": False,
        "updated_at": P["date"],
    })
    for credit in ca["credits"]:
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "credit_agricole",
            "institution": "credit_agricole", "institution_display_name": "Crédit Agricole",
            "external_id": credit.get("account"), "name": credit["name"],
            "account_type": "loan", "currency": "EUR",
            "balance": -credit["remaining"], "is_pro": False,
            "updated_at": P["date"],
            # Extra loan fields
            "loan_borrowed": credit["borrowed"],
            "loan_remaining": credit["remaining"],
            "loan_monthly": credit["monthly_payment"],
            "loan_rate": credit.get("rate"),
            "loan_type": credit.get("type"),
        })

    return accounts

ACCOUNTS = build_accounts()

# ─── Build positions (dynamic with live prices) ──────────────────────────────

def build_positions():
    """Build positions list. Uses live prices when available, falls back to scraped."""
    positions = []
    total_value = 0
    eur_usd = get_eur_usd()

    # TR positions (EUR)
    for i, pos in enumerate(P["trade_republic"]["positions"]):
        isin = pos["isin"]
        ticker = ISIN_TO_TICKER.get(isin)
        sector, country = SECTOR_MAP.get(isin, ("Other", "??"))
        shares = pos["shares"]

        # Use reliable avg_price from extraction_complete (detail page scrape)
        # TR's portfolio page return_pct has no sign (color-only) → unreliable
        reliable_avg = TR_AVG_PRICES.get(pos["name"])
        if reliable_avg:
            invested = round(shares * reliable_avg, 2)
        else:
            # Fallback: use patrimoine avg_price_eur if it exists
            avg_eur = pos.get("avg_price_eur", 0)
            invested = round(shares * avg_eur, 2) if avg_eur else pos["current_value_eur"]

        # Try live price
        live = get_live_price(ticker) if ticker else None
        if live and ticker:
            # Convert to EUR if needed
            if ticker.endswith(".PA"):
                current_price = live  # already EUR
            elif ticker.endswith(".DE"):
                current_price = live  # already EUR
            elif ticker == "IUIT.L":
                current_price = live / eur_usd  # USD → EUR
            elif ticker == "1211.HK":
                hkd_eur = get_live_price("HKDEUR=X") or 0.107
                current_price = live * hkd_eur  # HKD → EUR
            elif ticker.endswith(".TO"):
                cad_eur = get_live_price("CADEUR=X") or 0.617
                current_price = live * cad_eur  # CAD → EUR
            else:
                current_price = live / eur_usd  # USD → EUR
            val = round(shares * current_price, 2)
            pnl = round(val - invested, 2)
            pnl_pct = round(pnl / abs(invested) * 100, 2) if invested != 0 else 0
        else:
            val = pos["current_value_eur"]
            current_price = round(val / shares, 2) if shares else None
            pnl = round(val - invested, 2)
            pnl_pct = round(pnl / abs(invested) * 100, 2) if invested != 0 else 0

        total_value += val
        short_name = pos["name"].split()[0][:6].upper() if pos["name"] else isin[:6]

        positions.append({
            "id": _id("pos", i + 1),
            "account_id": "acc-0001",
            "ticker": short_name,
            "isin": isin,
            "name": pos["name"],
            "quantity": shares,
            "avg_cost": reliable_avg or pos.get("avg_price_eur", 0),
            "current_price": round(current_price, 2) if current_price else None,
            "currency": "EUR",
            "asset_type": "etf" if isin == "IE00B3WJKG14" else "stock",
            "sector": sector,
            "country": country,
            "value_native": val,
            "value_eur": val,
            "pnl_native": pnl,
            "pnl_eur": pnl,
            "pnl_pct": pnl_pct,
            "weight_pct": 0,
            "pe_ratio": pos.get("pe_ratio"),
            "beta": pos.get("beta"),
            "source": "Trade Republic",
            "live": live is not None,
        })

    # IBKR positions (USD)
    for j, pos in enumerate(P["ibkr"]["positions"]):
        isin = pos["isin"]
        ticker = ISIN_TO_TICKER.get(isin)
        sector, country = SECTOR_MAP.get(isin, ("Other", "US"))
        shares = pos["quantity"]
        cost_usd = pos["cost_basis_usd"]

        live = get_live_price(ticker) if ticker else None
        if live:
            current_price_usd = live
            val_usd = round(shares * current_price_usd, 2)
            pnl_usd = round(val_usd - cost_usd, 2)
        else:
            current_price_usd = pos["last_price_usd"]
            val_usd = pos["market_value_usd"]
            pnl_usd = pos["unrealized_pnl_usd"]

        val_eur = round(val_usd / eur_usd, 2)
        pnl_eur = round(pnl_usd / eur_usd, 2)
        pnl_pct = round(pnl_usd / cost_usd * 100, 2) if cost_usd else 0
        total_value += val_eur

        positions.append({
            "id": _id("pos", 100 + j),
            "account_id": "acc-0002",
            "ticker": pos["symbol"],
            "isin": isin,
            "name": {"GOOGL": "Alphabet (Google)", "NVDA": "NVIDIA", "MSFT": "Microsoft"}.get(pos["symbol"], pos["symbol"]),
            "quantity": shares,
            "avg_cost": pos["avg_price_usd"],
            "current_price": round(current_price_usd, 2),
            "currency": "USD",
            "asset_type": "stock",
            "sector": sector,
            "country": country,
            "value_native": val_usd,
            "value_eur": val_eur,
            "pnl_native": pnl_usd,
            "pnl_eur": pnl_eur,
            "pnl_pct": pnl_pct,
            "weight_pct": 0,
            "dividend_yield_pct": pos.get("dividend_yield_pct"),
            "ex_dividend_date": pos.get("ex_dividend_date"),
            "source": "Interactive Brokers",
            "live": live is not None,
        })

    # Compute weights
    for pos in positions:
        pos["weight_pct"] = round(pos["value_eur"] / total_value * 100, 2) if total_value else 0

    # Sort by value descending
    positions.sort(key=lambda x: x["value_eur"], reverse=True)
    return positions

# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/v1/market/refresh")
def refresh_prices():
    """Manually trigger a price refresh."""
    _fetch_live_prices()
    return {"status": "ok", "cached": len(_price_cache), "eur_usd": get_eur_usd()}

@app.get("/api/v1/status")
def get_status():
    """Health check with data freshness info."""
    positions = build_positions()
    live_count = sum(1 for p in positions if p.get("live"))
    total_val = sum(p["value_eur"] for p in positions)
    total_pnl = sum(p["pnl_eur"] for p in positions)

    # Data file info
    data_file = sorted(DATA_DIR.glob("patrimoine_complet_*.json"), reverse=True)[0]
    file_mtime = data_file.stat().st_mtime
    import os
    hours_ago = (time.time() - file_mtime) / 3600

    return {
        "status": "ok",
        "data_date": P.get("date", "?"),
        "data_timestamp": P.get("timestamp", "?"),
        "data_file": data_file.name,
        "data_age_hours": round(hours_ago, 1),
        "stale": hours_ago > 48,
        "net_worth": round(total_val + P.get("totals", {}).get("total_bank_liquid", 0) +
                          P.get("totals", {}).get("total_real_estate", 0) -
                          P.get("totals", {}).get("total_debt", 0), 2),
        "positions": len(positions),
        "live_prices": live_count,
        "eur_usd": round(get_eur_usd(), 4),
        "total_portfolio": round(total_val, 2),
        "total_pnl": round(total_pnl, 2),
    }

@app.get("/api/v1/networth")
def get_networth():
    positions = build_positions()
    eur_usd = get_eur_usd()

    tr_portfolio = sum(p["value_eur"] for p in positions if p["source"] == "Trade Republic")
    tr_cash = P["trade_republic"]["cash"]
    tr_val = tr_portfolio + tr_cash

    ibkr_portfolio = sum(p["value_eur"] for p in positions if p["source"] == "Interactive Brokers")
    ibkr_cash_eur = P["ibkr"]["cash"]["total_eur"]
    ibkr_val = ibkr_portfolio + ibkr_cash_eur

    # Exclude children accounts (Nathael = son, not user's patrimoine)
    children = P["boursobank"].get("children_accounts", {})
    nathael_total = sum(a["balance"] for a in children.values())
    bourso_liquid = P["boursobank"]["total_liquid"] - children.get("checking_nathael", {}).get("balance", 0)
    bourso_savings = P["boursobank"]["total_savings"] - children.get("livret_a_nathael", {}).get("balance", 0)
    ca_liquid = P["credit_agricole"]["accounts"]["checking"]["balance"]
    sca_prop = P["sca_la_desirade"]["your_share_property_value"]

    total_investments = tr_val + ibkr_val
    total_bank_liquid = bourso_liquid + bourso_savings + ca_liquid
    total_real_estate = sca_prop
    total_assets = total_investments + total_bank_liquid + total_real_estate

    bourso_loans = abs(P["boursobank"]["total_loans"])
    ca_debt = abs(P["credit_agricole"]["total_debt"])
    total_debt = bourso_loans + ca_debt
    net_worth = total_assets - total_debt

    live_count = sum(1 for p in positions if p.get("live"))

    return {
        "net_worth": round(net_worth, 2),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_debt, 2),
        "breakdown": {
            "cash": round(total_bank_liquid, 2),
            "savings": round(bourso_savings, 2),
            "investments": round(total_investments, 2),
            "real_estate": round(total_real_estate, 2),
        },
        "by_institution": [
            {"name": "ibkr", "display_name": "Interactive Brokers", "total": round(ibkr_val, 2), "source": "live" if live_count > 0 else "scraped"},
            {"name": "credit_agricole", "display_name": "Crédit Agricole", "total": round(ca_liquid + P["credit_agricole"]["total_debt"], 2), "source": "scraped"},
            {"name": "boursobank", "display_name": "Boursobank", "total": round(bourso_liquid + bourso_savings + P["boursobank"]["total_loans"], 2), "source": "scraped"},
            {"name": "trade_republic", "display_name": "Trade Republic", "total": round(tr_val, 2), "source": "live" if live_count > 0 else "scraped"},
            {"name": "sca", "display_name": "SCA La Désirade", "total": round(sca_prop, 2), "source": "estimate"},
        ],
        "variation_day": None,
        "variation_month": None,
        "eur_usd": round(eur_usd, 4),
        "live_prices": live_count,
        "sources": {
            "investments": "live" if live_count > 0 else "scraped",
            "cash": "scraped",
            "savings": "scraped",
            "real_estate": "estimate",
            "liabilities": "scraped",
        },
    }


@app.get("/api/v1/networth/history")
def get_networth_history(limit: int = Query(365)):
    """Real net worth history using Yahoo Finance historical prices."""
    from backend.history_manager import build_real_history
    try:
        history = build_real_history(limit)
        if history:
            return history
    except Exception as e:
        print(f"[history] Yahoo Finance fetch failed: {e}, falling back to mock")

    # Fallback: deterministic mock if Yahoo fails
    today = date.today()
    t = P["totals"]
    random.seed(42)
    inv = t["total_investments"]
    cash = t["total_bank_liquid"]
    re = t["total_real_estate"]
    debt = t["total_debt"]
    points = []
    for i in range(limit):
        d = today - timedelta(days=i)
        if i > 0:
            inv *= 1 - (random.random() - 0.47) * 0.008
            cash += (random.random() - 0.5) * 50
        points.append({
            "date": d.isoformat(),
            "total_assets": round(inv + cash + re, 2),
            "total_liabilities": round(debt, 2),
            "net_worth": round(inv + cash + re - debt, 2),
            "breakdown": {"investments": round(inv, 2), "cash": round(cash, 2), "real_estate": round(re, 2)},
        })
    points.reverse()
    return points[:limit]


@app.get("/api/v1/accounts")
def get_accounts():
    return ACCOUNTS


@app.get("/api/v1/accounts/{account_id}")
def get_account(account_id: str):
    for a in ACCOUNTS:
        if a["id"] == account_id:
            return a
    return {"error": "not found"}


@app.get("/api/v1/portfolio")
def get_portfolio():
    return build_positions()


@app.get("/api/v1/portfolio/allocation")
def get_allocation():
    # By sector
    sectors: dict[str, float] = {}
    countries: dict[str, float] = {}
    currencies: dict[str, float] = {}
    asset_types: dict[str, float] = {}

    positions = build_positions()
    total = sum(p["value_eur"] for p in positions)

    for p in positions:
        s = p.get("sector", "Other")
        sectors[s] = sectors.get(s, 0) + p["value_eur"]

        c = COUNTRY_NAMES.get(p.get("country", ""), p.get("country", "Other"))
        countries[c] = countries.get(c, 0) + p["value_eur"]

        cur = p["currency"]
        currencies[cur] = currencies.get(cur, 0) + p["value_eur"]

        at = p.get("asset_type", "stock")
        asset_types[at] = asset_types.get(at, 0) + p["value_eur"]

    def to_items(d):
        return sorted(
            [{"label": k, "value_eur": round(v, 2), "percentage": round(v / total * 100, 1)} for k, v in d.items()],
            key=lambda x: -x["value_eur"]
        )

    return {
        "by_sector": to_items(sectors),
        "by_country": to_items(countries),
        "by_currency": to_items(currencies),
        "by_asset_type": to_items(asset_types),
    }


@app.get("/api/v1/portfolio/dividends")
def get_dividends():
    positions = build_positions()
    divs = []
    for p in positions:
        dy = p.get("dividend_yield_pct")
        if dy and dy != "?":
            try:
                rate = float(dy) / 100
            except (ValueError, TypeError):
                continue
            divs.append({
                "id": f"div-{p['id']}",
                "position_id": p["id"],
                "ex_date": p.get("ex_dividend_date"),
                "pay_date": None,
                "amount_per_share": round(p["current_price"] * rate, 4) if p["current_price"] else 0,
                "total_amount": round(p["value_eur"] * rate, 2),
                "currency": p["currency"],
            })
    return divs


@app.get("/api/v1/analytics/diversification")
def get_diversification():
    positions = build_positions()
    return compute_diversification(positions)


@app.get("/api/v1/transactions")
def get_transactions(limit: int = Query(50), months: int = Query(6)):
    txs = load_transactions(months=months)
    return txs[:limit]


@app.get("/api/v1/accounts/{account_id}/transactions")
def get_account_transactions(account_id: str, limit: int = Query(50)):
    txs = load_transactions(months=24)
    filtered = [t for t in txs if t.get("account_id") == account_id or t.get("bank") == account_id]
    return filtered[:limit]


@app.get("/api/v1/budget/monthly")
def get_monthly_budget(limit: int = Query(12)):
    # Try real transaction data first
    txs = load_transactions(months=limit)
    if txs:
        return aggregate_monthly_budget(txs)[-limit:]
    # Fallback: basic fixed-cost budget
    monthly_costs = P["totals"]["monthly_loan_payments"] + P["totals"].get("monthly_margin_cost", 0)
    months = []
    today = date.today()
    for i in range(limit - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append({
            "month": f"{y}-{m:02d}",
            "income": 0,
            "expenses": round(monthly_costs, 2),
            "savings_rate": 0,
        })
    return months


@app.get("/api/v1/budget/categories")
def get_category_spending(months: int = Query(3)):
    txs = load_transactions(months=months)
    if txs:
        budget = aggregate_monthly_budget(txs)
        # Merge all months' categories
        from collections import defaultdict
        total_cats: dict[str, float] = defaultdict(float)
        cat_counts: dict[str, int] = defaultdict(int)
        for m in budget:
            for cat, amount in m.get("categories", {}).items():
                total_cats[cat] += amount
                cat_counts[cat] += 1
        return [
            {"category": cat, "total": round(amt, 2), "count": cat_counts[cat]}
            for cat, amt in sorted(total_cats.items(), key=lambda x: -x[1])
        ]
    # Fallback: fixed costs
    ca_credits = P["credit_agricole"]["monthly_payments"]
    margin_monthly = P["totals"].get("monthly_margin_cost", 0)
    bourso_loans = P.get("boursobank", {}).get("loans", [])
    bourso_monthly = sum(l.get("monthly_payment", 0) or round(l["remaining"] / 24, 2) for l in bourso_loans)
    return [
        {"category": "credits_immobilier", "total": round(ca_credits * months, 2), "count": 2},
        {"category": "marge_ibkr", "total": round(margin_monthly * months, 2), "count": months},
        {"category": "prets_perso", "total": round(bourso_monthly * months, 2), "count": len(bourso_loans)},
    ]


@app.get("/api/v1/budget/categories/{category}/transactions")
def get_category_transactions(category: str, months: int = Query(3)):
    """Return individual transactions for a given normalized category."""
    from backend.insights_engine import _normalize_category
    txs = load_transactions(months=months)
    matches = []
    for tx in txs:
        norm = _normalize_category(tx)
        if norm == category and tx.get("amount", 0) < 0:
            matches.append({
                "date": tx["date"],
                "description": tx["description"],
                "amount": tx["amount"],
                "category": norm,
                "merchant": tx.get("merchant", ""),
                "bank": tx.get("bank", ""),
            })
    return sorted(matches, key=lambda x: x["date"], reverse=True)


@app.get("/api/v1/budget/projections")
def get_budget_projections():
    """Forecast M+1, M+2, M+3 budget based on rolling averages."""
    txs = load_transactions(months=12)
    if not txs:
        return {"projections": []}
    budget = aggregate_monthly_budget(txs)
    if len(budget) < 3:
        return {"projections": []}

    from collections import defaultdict
    # Use last 6 full months (exclude current partial month)
    today = date.today()
    current_month = f"{today.year}-{today.month:02d}"
    full_months = [m for m in budget if m["month"] != current_month][-6:]
    if not full_months:
        full_months = budget[-6:]

    avg_income = sum(m["income"] for m in full_months) / len(full_months)
    avg_expenses = sum(m["expenses"] for m in full_months) / len(full_months)
    avg_savings = avg_income - avg_expenses

    # Category averages
    cat_totals: dict[str, float] = defaultdict(float)
    for m in full_months:
        for cat, amt in m.get("categories", {}).items():
            cat_totals[cat] += amt
    cat_averages = {cat: round(total / len(full_months), 2) for cat, total in cat_totals.items()}

    projections = []
    for i in range(1, 4):
        month_num = today.month + i
        year = today.year
        while month_num > 12:
            month_num -= 12
            year += 1
        projections.append({
            "month": f"{year}-{month_num:02d}",
            "projected_income": round(avg_income, 2),
            "projected_expenses": round(avg_expenses, 2),
            "projected_savings": round(avg_savings, 2),
            "projected_savings_rate": round((avg_savings / avg_income * 100) if avg_income > 0 else 0, 1),
            "categories": cat_averages,
        })

    yearly_income = round(avg_income * 12, 2)
    yearly_expenses = round(avg_expenses * 12, 2)

    return {
        "basis_months": len(full_months),
        "avg_income": round(avg_income, 2),
        "avg_expenses": round(avg_expenses, 2),
        "avg_savings": round(avg_savings, 2),
        "avg_savings_rate": round((avg_savings / avg_income * 100) if avg_income > 0 else 0, 1),
        "yearly": {
            "projected_income": yearly_income,
            "projected_expenses": yearly_expenses,
            "projected_savings": round(yearly_income - yearly_expenses, 2),
        },
        "projections": projections,
    }


@app.get("/api/v1/market/fx")
def get_fx_rates():
    return [
        {"date": date.today().isoformat(), "base_currency": "EUR", "quote_currency": "USD", "rate": EUR_USD},
    ]


@app.get("/api/v1/market/quote/{ticker}")
def get_quote(ticker: str):
    """Return live price from yfinance cache."""
    price = get_live_price(ticker)
    if price is not None:
        return {"ticker": ticker, "price": price, "currency": "USD", "date": date.today().isoformat()}
    # Try resolving ISIN → ticker
    resolved = ISIN_TO_TICKER.get(ticker, ticker)
    price = get_live_price(resolved)
    if price is not None:
        return {"ticker": resolved, "price": price, "currency": "USD", "date": date.today().isoformat()}
    # Fetch on-demand via yfinance
    try:
        import yfinance as yf
        t = yf.Ticker(resolved)
        p = t.fast_info.get("lastPrice") or t.fast_info.get("last_price")
        if p and not math.isnan(p):
            with _cache_lock:
                _price_cache[resolved] = {"price": float(p), "ts": time.time()}
            return {"ticker": resolved, "price": float(p), "currency": str(t.fast_info.get("currency", "USD")), "date": date.today().isoformat()}
    except Exception:
        pass
    return {"ticker": ticker, "price": None, "error": "not_found"}


@app.get("/api/v1/market/history/{ticker}")
def get_history(ticker: str, period: str = Query("1y"), limit: int = Query(365)):
    """Return OHLCV history from yfinance + persist to DuckDB."""
    resolved = ISIN_TO_TICKER.get(ticker, ticker)
    try:
        import yfinance as yf
        t = yf.Ticker(resolved)
        hist = t.history(period=period)
        if hist.empty:
            return []
        rows = []
        for dt, row in hist.tail(limit).iterrows():
            rows.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]) if not math.isnan(row["Volume"]) else 0,
            })
        # Persist to DuckDB
        _persist_market_prices(resolved, rows)
        return rows
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/market/sparklines")
def get_sparklines():
    """Return 30-day close prices for all portfolio positions (batch).
    Keys include both Yahoo ticker AND portfolio display ticker for frontend matching."""
    import yfinance as yf
    result = {}
    tickers = set()
    # Build mapping: yahoo_ticker → portfolio display ticker(s)
    yahoo_to_display: dict[str, list[str]] = {}
    for bank_key in ["ibkr", "trade_republic"]:
        bank = P.get(bank_key, {})
        for pos in bank.get("positions", []):
            isin = pos.get("isin", "")
            sym = pos.get("symbol") or ISIN_TO_TICKER.get(isin, "")
            if sym:
                tickers.add(sym)
                # Portfolio display ticker
                if bank_key == "trade_republic":
                    display = pos["name"].split()[0][:6].upper() if pos.get("name") else isin[:6]
                else:
                    display = pos.get("symbol", sym)
                yahoo_to_display.setdefault(sym, []).append(display)
    if not tickers:
        return result
    try:
        data = yf.download(list(tickers), period="1mo", group_by="ticker", auto_adjust=True, progress=False)
        for t in tickers:
            try:
                if len(tickers) == 1:
                    closes = data["Close"].dropna().tolist()
                else:
                    closes = data[t]["Close"].dropna().tolist()
                points = [round(float(c), 2) for c in closes[-30:]]
                result[t] = points
                # Also store under display ticker for frontend matching
                for disp in yahoo_to_display.get(t, []):
                    if disp != t:
                        result[disp] = points
            except Exception:
                pass
    except Exception as e:
        print(f"[sparklines] yfinance error: {e}")
    return result


@app.get("/api/v1/alerts")
def get_alerts():
    return []


# ─── Extra: Patrimoine & Loans detail endpoints ──────────────────────────────

@app.get("/api/v1/patrimoine")
def get_patrimoine():
    """Full patrimoine data including SCA, property, loans."""
    return P


@app.get("/api/v1/loans")
def get_loans():
    """All loans with inflation analysis & recommendations."""
    # --- REAL rates scraped from CA BFF API (dcam.credit-agricole.fr/bff01/credits/) ---
    # Scraped 2026-02-09 from credit detail pages via CDP
    CA_SCRAPED_BY_INDEX = [
        {  # 0: PTZ
            "account": "00004690214",
            "taux": 0.0, "taux_type": "FIXE", "taux_assurance": None,
            "mensualite": 0.0,
            "duree_mois": 264, "date_debut": "28/09/2022", "date_fin": "05/10/2044",
        },
        {  # 1: PAS 10K
            "account": "00004690213",
            "taux": 0.0, "taux_type": "FIXE", "taux_assurance": None,
            "mensualite": 0.0,
            "duree_mois": 240, "date_debut": "28/09/2022", "date_fin": "05/10/2042",
        },
        {  # 2: PAS 138K
            "account": "00004690212",
            "taux": 0.98, "taux_type": "FIXE", "taux_assurance": None,
            "mensualite": 636.91,
            "duree_mois": 240, "date_debut": "27/03/2025", "date_fin": "05/04/2045",
        },
        {  # 3: Prêt Conso
            "account": "73140424333",
            "taux": 1.972, "taux_type": "FIXE", "taux_assurance": None,
            "mensualite": 73.69,
            "duree_mois": 72, "date_debut": "25/01/2022", "date_fin": "05/02/2028",
        },
    ]

    raw_loans = []
    for idx, credit in enumerate(P["credit_agricole"]["credits"]):
        scraped = CA_SCRAPED_BY_INDEX[idx] if idx < len(CA_SCRAPED_BY_INDEX) else {}
        rate = scraped.get("taux")
        monthly = scraped.get("mensualite") or credit["monthly_payment"]
        raw_loans.append({
            "institution": "Crédit Agricole",
            "name": credit["name"],
            "type": credit.get("type", "unknown"),
            "borrowed": credit["borrowed"],
            "remaining": credit["remaining"],
            "monthly_payment": monthly,
            "rate": rate,
            "rate_source": "scraped" if rate is not None else "unknown",
            "insurance_monthly": None,  # CA doesn't expose assurance via BFF
            "start_date": scraped.get("date_debut") or credit.get("start_date"),
            "end_date": scraped.get("date_fin"),
            "duration_months": scraped.get("duree_mois"),
            "rate_type": scraped.get("taux_type"),
            "status": credit.get("status"),
        })
    # Boursobank personal loans — REAL data scraped from detail pages
    BOURSO_LOANS_SCRAPED = {
        "PRÊT PERSONNEL 1": {
            "account_number": "00060570381",
            "borrowed": 10_000.00,
            "remaining": 1_448.78,
            "taeg": 0.75,
            "taux_nominal": 0.747,
            "monthly_payment": 0.90,
            "insurance_monthly": 0.00,
            "start_date": "2022-01-26",
            "end_date": "2027-01-26",
            "total_echeances": 60,
            "echeances_restantes": 12,
        },
        "PRÊT PERSONNEL 2": {
            "account_number": "00060401620",
            "borrowed": 15_000.00,
            "remaining": 6_284.35,
            "taeg": 1.90,
            "taux_nominal": 1.884,
            "monthly_payment": 9.87,
            "insurance_monthly": 0.00,
            "start_date": "2025-06-26",
            "end_date": "2026-09-26",
            "total_echeances": 15,
            "echeances_restantes": 8,
        },
    }
    for i, loan in enumerate(P["boursobank"]["loans"]):
        key = f"PRÊT PERSONNEL {i+1}"
        scraped = BOURSO_LOANS_SCRAPED.get(key, {})
        raw_loans.append({
            "institution": "Boursobank",
            "name": loan["name"],
            "type": "consumer",
            "account_number": scraped.get("account_number"),
            "borrowed": scraped.get("borrowed"),
            "remaining": scraped.get("remaining", loan["remaining"]),
            "monthly_payment": scraped.get("monthly_payment"),
            "rate": scraped.get("taeg"),
            "taux_nominal": scraped.get("taux_nominal"),
            "rate_source": "scraped" if scraped else "unknown",
            "insurance_monthly": scraped.get("insurance_monthly"),
            "start_date": scraped.get("start_date"),
            "end_date": scraped.get("end_date"),
            "remaining_months": scraped.get("echeances_restantes"),
            "status": "active",
        })
    # IBKR margin — two separate loans by currency (real rates from interactivebrokers.com/en/trading/margin-rates.php)
    ibkr_cash = P["ibkr"].get("cash", {})
    eur_debt = abs(ibkr_cash.get("eur", 0))  # EUR debit balance
    usd_debt = abs(ibkr_cash.get("usd", 0))  # USD debit balance
    # IBKR Pro Tier 1 rates (verified 2026-02-09 from official margin rates page)
    IBKR_RATE_USD = 5.140  # BM + 1.5%, Tier 1 (0-100K USD)
    IBKR_RATE_EUR = 3.499  # BM + 1.5%, Tier 1 (0-90K EUR)
    if usd_debt > 0:
        usd_monthly_interest = usd_debt * (IBKR_RATE_USD / 100) / 12
        raw_loans.append({
            "institution": "Interactive Brokers",
            "name": "Marge USD",
            "type": "margin",
            "borrowed": None,
            "remaining": round(usd_debt, 2),
            "currency": "USD",
            "monthly_payment": round(usd_monthly_interest, 2),
            "rate": IBKR_RATE_USD,
            "rate_source": "official",  # interactivebrokers.com/en/trading/margin-rates.php
            "insurance_monthly": 0,
        })
    if eur_debt > 0:
        eur_monthly_interest = eur_debt * (IBKR_RATE_EUR / 100) / 12
        raw_loans.append({
            "institution": "Interactive Brokers",
            "name": "Marge EUR",
            "type": "margin",
            "borrowed": None,
            "remaining": round(eur_debt, 2),
            "currency": "EUR",
            "monthly_payment": round(eur_monthly_interest, 2),
            "rate": IBKR_RATE_EUR,
            "rate_source": "official",  # interactivebrokers.com/en/trading/margin-rates.php
            "insurance_monthly": 0,
        })
    return analyze_loans(raw_loans)


@app.get("/api/v1/sca")
def get_sca():
    """SCA La Désirade data with Grabels market context."""
    sca = P["sca_la_desirade"]
    # Property data now correct in build_patrimoine (118m², Villa R+1)
    surface = sca["property"]["surface_m2"]  # 118
    terrain_privatif = sca["property"].get("terrain_privatif_m2", 466)
    terrain_commun = sca["property"].get("terrain_commun_m2", 300)
    terrain_total = terrain_privatif + terrain_commun // 2  # ~616m² effective
    # Update price/m² based on Bourso estimate
    sca["property"]["price_per_m2_estimate"] = round(sca["property"]["bourso_estimate"] / surface, 2)
    # Grabels (34790) market data — 2025 sources
    sca["market"] = {
        "commune": "Grabels",
        "code_postal": "34790",
        "date_source": "2025-Q1",
        "prix_m2_achat": {
            "appartement": {"low": 2610, "median": 3121, "high": 4129},
            "maison": {"low": 2550, "median": 3530, "high": 4630},
            "neuf_maison": {"low": 3690, "median": 4100, "high": 4690},
            "source": "MeilleursAgents / Le Figaro / PAP",
        },
        "loyer_m2": {
            "median": 13.5,
            "low": 11.8,
            "high": 15.2,
            "source": "Carte des loyers (ecologie.gouv.fr) + SeLoger",
        },
        "cout_construction_m2": {
            "economique": {"low": 1400, "high": 1600},
            "standard": {"low": 1800, "high": 2200},
            "contemporain": {"low": 2200, "high": 2800},
            "source": "Constructeurs Hérault / Cobea / Villasgaia 2025",
        },
        # Computed analyses
        "estimation_revente": {
            "low": round(surface * 2550),
            "median_ancien": round(surface * 3530),
            "median_neuf": round(surface * 4100),
            "high": round(surface * 4630),
            "bourso": sca["property"]["bourso_estimate"],
        },
        "estimation_loyer_mensuel": {
            "low": round(surface * 11.8),
            "median": round(surface * 13.5),
            "high": round(surface * 15.2),
        },
        "cout_reconstruction": {
            "economique": round(surface * 1500),
            "standard": round(surface * 2000),
            "contemporain": round(surface * 2500),
        },
        "rendement_locatif_brut_pct": round(
            (surface * 13.5 * 12) / sca["property"]["bourso_estimate"] * 100, 2
        ),
        "terrain": {
            "privatif_m2": terrain_privatif,
            "commun_m2": terrain_commun,
            "prix_m2_terrain_grabels": {"low": 250, "median": 380, "high": 500},
            "estimation_terrain_privatif": {
                "low": round(terrain_privatif * 250),
                "median": round(terrain_privatif * 380),
                "high": round(terrain_privatif * 500),
            },
        },
    }
    return sca


@app.get("/api/v1/sca/legal")
def get_sca_legal():
    """SCA La Désirade — legal costs, procedures, timeline."""
    import csv
    from collections import defaultdict

    # 1. Parse FEC for SCA legal expenses (accounts 6221/6226/6227)
    fec_path = Path("/Users/sylvain/MAISON GRABELS/COMPTA SCA/EXPORT_EXPERT_COMPTABLE/FEC_SCA_2021_2025.txt")
    legal_entries = []
    # Professional fee accounts — classified by purpose:
    # juridique: avocat, huissier, divers (condamnation), publication
    # études: géomètre (BET Seals), architecte (permis modificatif)
    # acquisition: notaire (terrain)
    COMPTE_MAP = {
        "6220": "condamnation", "6221": "acquisition_notaire", "6222": "études_géomètre",
        "6223": "études_architecte", "6226": "avocat", "6227": "huissier", "6234": "publication",
    }
    if fec_path.exists():
        with open(fec_path) as f:
            for row in csv.DictReader(f, delimiter='|'):
                compte = row.get("CompteNum", "")
                if row.get("JournalCode") != "ACH":
                    continue
                cat = None
                for prefix, c in COMPTE_MAP.items():
                    if compte.startswith(prefix):
                        cat = c
                        break
                if not cat:
                    continue
                d = float(row.get("Debit", "0") or 0)
                if d > 0:
                    dt = row["EcritureDate"]
                    legal_entries.append({
                        "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                        "category": cat,
                        "account": row["CompteLib"],
                        "description": row["EcritureLib"],
                        "amount": d,
                        "piece_ref": row.get("PieceRef", ""),
                    })

    # Expertise judiciaire — consignation payée par chèque perso au TJ (régie)
    # SELARL AMAJ (Philippe Combes): 11 039,57€ TTC (rapport du 31/01/2025)
    # Consignation initiale ~juil 2023 + complémentaire ~oct 2023, 100% Legland
    legal_entries.append({
        "date": "2023-07-27", "category": "expertise_judiciaire",
        "account": "Consignation TJ", "description": "Consignation initiale expertise (chèque régie TJ)",
        "amount": 8399.57, "piece_ref": "AMAJ-2023",
    })
    legal_entries.append({
        "date": "2023-10-24", "category": "expertise_judiciaire",
        "account": "Consignation TJ", "description": "Consignation complémentaire sapiteur géomètre (chèque régie TJ)",
        "amount": 2640.00, "piece_ref": "AMAJ-2023-COMP",
    })

    # 2. Personal legal payments (Bourso → lawyers / huissiers / greffe, not via SCA)
    personal_legal = []
    try:
        import duckdb
        db = duckdb.connect(str(DATA_DIR / "finary.duckdb"), read_only=True)
        rows = db.execute("""
            SELECT date, description, amount FROM transactions
            WHERE LOWER(description) LIKE '%axel saint martin%'
               OR LOWER(description) LIKE '%alfier%'
               OR (LOWER(description) LIKE '%huissier%' AND bank = 'boursobank')
               OR LOWER(description) LIKE '%greffe%'
               OR LOWER(description) LIKE '%infogreffe%'
            ORDER BY date
        """).fetchall()
        seen = set()
        for r in rows:
            # Deduplicate (some Bourso entries appear twice)
            key = (str(r[0]), round(r[2], 2))
            if key in seen:
                continue
            seen.add(key)
            personal_legal.append({
                "date": str(r[0]),
                "description": r[1].split("|")[0].strip(),
                "amount": round(abs(r[2]), 2),
                "category": "greffe" if "greffe" in r[1].lower() or "infogreffe" in r[1].lower()
                    else "huissier" if "alfier" in r[1].lower() or "huissier" in r[1].lower()
                    else "avocat",
            })
        db.close()
    except Exception:
        pass

    # 3. SCA cash flow (Bourso → SCA transfers)
    sca_cashflow = []
    try:
        db = duckdb.connect(str(DATA_DIR / "finary.duckdb"), read_only=True)
        rows = db.execute("""
            SELECT date, description, amount FROM transactions
            WHERE (LOWER(description) LIKE '%scia la desirade%'
               OR LOWER(description) LIKE '%sca la desirade%')
            ORDER BY date
        """).fetchall()
        for r in rows:
            sca_cashflow.append({
                "date": str(r[0]),
                "description": r[1].split("|")[0].strip(),
                "amount": round(r[2], 2),
            })
        db.close()
    except Exception:
        pass

    # 4. Totals by category
    by_cat_sca = defaultdict(float)
    for e in legal_entries:
        by_cat_sca[e["category"]] += e["amount"]
    total_sca_legal = sum(by_cat_sca.values())

    by_cat_perso = defaultdict(float)
    for e in personal_legal:
        by_cat_perso[e.get("category", "avocat")] += e["amount"]
    total_personal = sum(by_cat_perso.values())

    # 5. Procedures timeline
    procedures = [
        {
            "id": "expertise",
            "name": "Expertise Judiciaire (Beaussier c/ Legland)",
            "type": "expertise",
            "status": "terminée",
            "lawyer": "Me Axel Saint Martin",
            "adverse": "Me Vernhet (avocat Beaussier)",
            "start_date": "2023-03-01",
            "key_dates": [
                {"date": "2023-03-09", "event": "Ordonnance de référé — désignation expert"},
                {"date": "2023-05-02", "event": "Consignation initiale expertise (régie TJ — 100% Legland)"},
                {"date": "2023-06-21", "event": "1ère réunion d'expertise"},
                {"date": "2023-07-27", "event": "Versement consignation initiale (8 399,57€)"},
                {"date": "2023-10-24", "event": "Versement consignation complémentaire sapiteur géomètre (2 640€)"},
                {"date": "2024-04-11", "event": "Nomination mandataire ad'hoc (Me Sandian — 1 800€)"},
                {"date": "2024-08-16", "event": "Note expert aux parties n°3"},
                {"date": "2024-08-28", "event": "Convocation expertise + réunion"},
                {"date": "2025-01-31", "event": "Rapport expertise déposé (SELARL AMAJ Philippe Combes — 11 039,57€ TTC)"},
            ],
            "cost": 11039.57,
            "cost_note": "Consignation 100% avancée par Legland (8 399,57€ + 2 640€ sapiteur géomètre)",
        },
        {
            "id": "fond_beaussier",
            "name": "Procédure au Fond (Beaussier c/ SCA — suite expertise)",
            "type": "judiciaire_civil",
            "status": "en_attente",
            "lawyer": "Me Axel Saint Martin",
            "adverse": "Me Vernhet (avocat Beaussier)",
            "jurisdiction": "TJ Montpellier",
            "start_date": "2025-01-31",
            "note": "Suite au rapport d'expertise judiciaire (SELARL AMAJ, 31/01/2025). Pas encore d'assignation au fond. Porte sur les malfaçons / étanchéité entre les 2 ouvrages.",
            "key_dates": [
                {"date": "2025-01-31", "event": "Rapport expertise déposé (SELARL AMAJ — 11 039,57€ TTC)"},
            ],
        },
        {
            "id": "refere_hah",
            "name": "Appel Référé Heure-à-Heure (Beaussier)",
            "type": "judiciaire_civil",
            "status": "en_cours",
            "lawyer": "Me Axel Saint Martin",
            "adverse": "Me Vernhet (avocat Beaussier)",
            "jurisdiction": "Cour d'Appel Montpellier",
            "start_date": "2025-10-01",
            "note": "Appel du référé heure-à-heure. Me Saint Martin a plaidé le 12/02/2026.",
            "key_dates": [
                {"date": "2025-10-14", "event": "Facture Me Saint Martin — Défense Référé Nullité AG (1 800€)"},
                {"date": "2026-02-12", "event": "Plaidoirie Me Saint Martin (appel heure-à-heure)"},
                {"date": "2026-03-31", "event": "⚖️ DÉLIBÉRÉ — Décision attendue"},
            ],
        },
        {
            "id": "refere_expulsion",
            "name": "Référé Expulsion (Beaussier occupante sans titre)",
            "type": "judiciaire_civil",
            "status": "en_cours",
            "lawyer": "Me Axel Saint Martin",
            "adverse": "Me Vernhet (avocat Beaussier) — joue la montre (dissolution SCA sept. 2026)",
            "jurisdiction": "TJ Montpellier — JCP (Juge des Contentieux de la Protection)",
            "start_date": "2025-08-26",
            "note": "Me Vernhet parie sur la dissolution automatique de la SCA en septembre 2026 (5 ans). Stratégie dilatoire.",
            "key_dates": [
                {"date": "2025-08-26", "event": "Assignation TJ JCP — occupant sans droit ni titre"},
                {"date": "2025-10-14", "event": "Facture Me Saint Martin — Référé Expulsion (1 800€)"},
                {"date": "2025-10-27", "event": "Facture Me Saint Martin — Assignation Mandataire (1 275€)"},
                {"date": "2026-03-23", "event": "📋 Conclusions adverses (Vernhet — deadline)"},
                {"date": "2026-05-04", "event": "📋 Conclusions en réplique (Saint Martin — deadline)"},
            ],
        },
        {
            "id": "prolongation",
            "name": "Prolongation SCA (2 ans — mandataire ad'hoc)",
            "type": "judiciaire_civil",
            "status": "en_cours",
            "lawyer": "Me Axel Saint Martin",
            "adverse": "Me Vernhet — a demandé renvoi (accordé de droit au 1er appel)",
            "jurisdiction": "TJ Montpellier — Référé",
            "start_date": "2026-01-22",
            "note": "Assignation mandataire ad'hoc pour prolonger la SCA de 2 ans (dissolution prévue sept. 2026). Vernhet a obtenu un renvoi de droit au 1er appel, mais le président a renvoyé au 26/02 (les autres renvoyés en avril).",
            "key_dates": [
                {"date": "2026-01-22", "event": "Audience référé — 1ère audience utile (assignation mandataire)"},
                {"date": "2026-01-23", "event": "Renvoi demandé par Vernhet (de droit au 1er appel)"},
                {"date": "2026-02-26", "event": "⚖️ AUDIENCE — Prolongation SCA (renvoi accéléré par le président)"},
            ],
        },
        {
            "id": "ta_grabels",
            "name": "Recours TA — Arrêté Interruptif (Commune de Grabels)",
            "type": "administratif",
            "status": "en_cours",
            "lawyer": "Me Sébastien Avallone",
            "jurisdiction": "Tribunal Administratif de Montpellier",
            "reference": "2025-733",
            "start_date": "2025-07-07",
            "key_dates": [
                {"date": "2025-06-24", "event": "Arrêté interruptif de travaux par la Mairie de Grabels"},
                {"date": "2025-07-07", "event": "Requête en référé suspension au TA"},
                {"date": "2025-08-01", "event": "Provision Me Avallone (4 800€)"},
                {"date": "2025-08-29", "event": "Ordonnance TA référé"},
                {"date": "2025-09-01", "event": "Requête en excès de pouvoir (fond)"},
                {"date": "2026-01-28", "event": "LRAR à Mairie de Grabels"},
                {"date": "2026-02-12", "event": "Pas encore de date de plaidoirie (en attente TA)"},
            ],
            "note": "Beaussier est intervenue volontairement dans la procédure TA aux côtés de la commune contre la SCA.",
        },
        {
            "id": "art19",
            "name": "Vente Forcée Parts Art. 19 (Beaussier)",
            "type": "vente_forcee",
            "status": "en_preparation",
            "lawyer": "Me Axel Saint Martin",
            "start_date": "2025-11-01",
            "note": "Dépend de: validation comptes → AGO → libération capital → AG art.19. Vernhet bloquera en heure-à-heure à chaque étape.",
            "key_dates": [
                {"date": "2025-03-17", "event": "AGO Révocation Beaussier de la cogérance"},
                {"date": "2025-05-27", "event": "AGE Modification statuts"},
                {"date": "2025-11-03", "event": "AGO Approbation comptes + AF impayés"},
                {"date": "2025-11-25", "event": "Provision huissier vente art.19 (58,75€)"},
                {"date": "2026-02-01", "event": "Validation comptes par Lionel (expert-comptable — en cours)"},
                {"date": "2026-03-01", "event": "📋 AGO Approbation comptes (à planifier)"},
                {"date": "2026-04-01", "event": "📋 Libération capital restant (à planifier)"},
                {"date": "2026-05-01", "event": "📋 AG Article 19 — mise en vente forcée"},
                {"date": "2026-06-01", "event": "⚠️ Heure-à-heure probable (Vernhet bloquera)"},
            ],
        },
    ]

    # Key strategic context
    strategy = {
        "dissolution_date": "2026-09-01",
        "dissolution_note": "SCA créée 28/07/2021, durée 5 ans → dissolution automatique ~sept. 2026",
        "adverse_strategy": "Me Vernhet joue la montre: renvois systématiques, heure-à-heure sur chaque AG. Pari = SCA dissoute avant expulsion/vente art.19.",
        "our_counter": "Prolongation SCA de 2 ans (audience 26/02) + accélérer art.19 en parallèle",
        "critical_path": [
            "26/02 → Prolongation SCA (bloque la dissolution)",
            "31/03 → Délibéré appel heure-à-heure",
            "23/03 → Conclusions adverses expulsion",
            "04/05 → Nos conclusions en réplique",
            "Comptes validés → AGO → Libération capital → AG art.19",
        ],
    }

    # 6. Monthly spending chart data
    monthly_spend = defaultdict(float)
    for e in legal_entries:
        month = e["date"][:7]  # YYYY-MM
        monthly_spend[month] += e["amount"]
    for e in personal_legal:
        month = e["date"][:7]
        monthly_spend[month] += e["amount"]

    chart_data = [{"month": k, "amount": round(v, 2)} for k, v in sorted(monthly_spend.items())]

    return {
        "summary": {
            "total_legal_sca": round(total_sca_legal, 2),
            "total_legal_personal": round(total_personal, 2),
            "total_legal_all": round(total_sca_legal + total_personal, 2),
            "by_category_sca": {k: round(v, 2) for k, v in sorted(by_cat_sca.items())},
            "by_category_perso": {k: round(v, 2) for k, v in sorted(by_cat_perso.items())},
            "total_sca_cashflow_out": round(sum(e["amount"] for e in sca_cashflow if e["amount"] < 0), 2),
            "total_sca_cashflow_in": round(sum(e["amount"] for e in sca_cashflow if e["amount"] > 0), 2),
        },
        "legal_entries": sorted(legal_entries, key=lambda x: x["date"]),
        "personal_legal": personal_legal,
        "sca_cashflow": sca_cashflow,
        "procedures": procedures,
        "strategy": strategy,
        "chart_monthly": chart_data,
        "beaussier_debt": {
            "af_impayes": 25334.71,
            "capital_non_libere": 192127.97,
            "fournisseurs_qp": 7105.89,
            "total": 25334.71 + 7105.89,
        },
        # Estimation des frais juridiques de Beaussier (Me Vernhet, avocat cher Montpellier)
        "beaussier_legal_estimate": {
            "note": "Estimation basée sur tarifs avocat Montpellier haut de gamme (350-450€/h)",
            "procedures": [
                {"name": "Expertise judiciaire (défense + dires + réunions)", "estimate_low": 4000, "estimate_high": 6000,
                 "note": "2 réunions expertise + 3 dires + conclusions"},
                {"name": "Référé heure-à-heure AG (1ère instance — gagné)", "estimate_low": 2500, "estimate_high": 4000,
                 "note": "Assignation + plaidoirie + ordonnance favorable"},
                {"name": "Appel référé heure-à-heure (PERDU — délibéré 31/03)", "estimate_low": 3000, "estimate_high": 5000,
                 "note": "Conclusions d'appel + plaidoirie CA — procédure perdue"},
                {"name": "Référé expulsion (conclusions + plaidoirie)", "estimate_low": 3000, "estimate_high": 5000,
                 "note": "Conclusions adverses 23/03 + audience à venir"},
                {"name": "Prolongation SCA (opposition)", "estimate_low": 1500, "estimate_high": 3000,
                 "note": "Renvoi obtenu de droit, audience 26/02"},
                {"name": "Procédure au fond (à venir)", "estimate_low": 5000, "estimate_high": 10000,
                 "note": "Procédure la plus lourde — expertise + assignation + conclusions + plaidoirie"},
                {"name": "Heure-à-heure sur chaque AG", "estimate_low": 1500, "estimate_high": 2500,
                 "note": "~3 AG contestées à ce jour"},
                {"name": "Intervention volontaire TA (arrêté interruptif)", "estimate_low": 2000, "estimate_high": 4000,
                 "note": "Intervention aux côtés de la commune contre la SCA au TA"},
            ],
            "total_low": 22500,
            "total_high": 39500,
            "condamnation_hah_perdu": {
                "note": "Référé HAH 1ère instance — Beaussier condamnée Art. 700 CPC",
                "art_700_legland": 1000,
                "art_700_sca": 1000,
                "total": 2000,
            },
            # QP Beaussier impayée sur les procédures SCA (elle refuse de payer sa part)
            "qp_impayes_sca": [
                # 401200 — factures fournisseurs non réglées
                {"desc": "Epsilon GE — étude murs soutènement (100% Beaussier)", "amount": 4200.00, "source": "401200"},
                {"desc": "Avocat Référé Expulsion (QP 49,4%)", "amount": 889.56, "source": "401200"},
                {"desc": "Avocat Défense Référé Nullité AG (QP 49,4%)", "amount": 889.56, "source": "401200"},
                {"desc": "Avocat Assignation Mandataire (QP 49,4%)", "amount": 630.10, "source": "401200"},
                {"desc": "Condamnation Mairie Art. L.761-1 (QP 49,4%)", "amount": 496.67, "source": "401200"},
                # 456110 — avancé par Legland (capital versé)
                {"desc": "Avocat Avallone — TA Grabels (QP 49,4%)", "amount": 2371.20, "source": "456110"},
                {"desc": "Géomètre BBASS — relevé topo (QP 49,4%)", "amount": 212.51, "source": "456110"},
                {"desc": "Géomètre BBASS — altimétrie (QP 49,4%)", "amount": 487.28, "source": "456110"},
                {"desc": "Huissier Peyrache — constat (QP 49,4%)", "amount": 183.41, "source": "456110"},
                {"desc": "Huissier Lafont — provision (QP)", "amount": 58.75, "source": "456110"},
                # 455100 — avancé via CCA Legland
                {"desc": "Mandataire Me Sandian (QP 49,4%)", "amount": 889.56, "source": "455100"},
                {"desc": "Architecte Bruno Cres — PCM (QP 49,4%)", "amount": 177.91, "source": "455100"},
            ],
            "total_qp_impayes": 11486.51,
            # Préjudices judiciaires — basés sur le rapport d'expertise et conclusions
            "prejudices": {
                "note": "Montants issus du rapport d'expertise (SELARL AMAJ, 31/01/2025) et des conclusions d'avocat",
                # Demandes de Legland (Me Saint Martin — Dire n°5)
                "demandes_legland": [
                    {"desc": "Préjudice de loyer (24 mois depuis jan 2023)", "amount_demande": 30720.00,
                     "amount_expert": 30720.00,
                     "note": "1 280€/mois × 24 mois — sous réserve production quittances (5 fournies sur 24)"},
                    {"desc": "Préjudice de loyer (durée chantier)", "amount_demande": 15360.00,
                     "amount_expert": 10240.00,
                     "note": "Expert retient 8 mois (construction bois) au lieu de 12 demandés"},
                    {"desc": "Préjudice assurance habitation", "amount_demande": 2662.92,
                     "amount_expert": 0,
                     "note": "Rejeté par l'expert — pas de justificatif, aurait payé assurance dans nouveau logement"},
                    {"desc": "Actualisation coût construction (ICC 2021→2024)", "amount_demande": 36364.00,
                     "amount_expert": 36575.00,
                     "note": "ICC 1 821 → 2 205 sur 173 443€ de travaux restants = 210 017€ actualisé"},
                ],
                "total_demande_legland": 85106.92,
                "total_expert_legland": 77535.00,
                # Demandes de Legland au profit de la SCA
                "demandes_sca": [
                    {"desc": "Indemnité d'occupation illicite (24 mois)", "amount_demande": 38400.00,
                     "amount_expert": None,
                     "note": "1 600€/mois × 24 mois — expert note que la DAACT n'est pas établie, lots non livrés"},
                    {"desc": "Indemnité d'occupation (assignation JCP)", "amount_mensuel": 1600.00,
                     "note": "Demandée à compter du 01/01/2023 jusqu'à libération effective des lieux"},
                ],
                # Travaux de remise en conformité (imputés à Beaussier 100%)
                "travaux_remise_conformite": [
                    {"desc": "Terrassement reprofilage chemin (Lorthioir, réduit par expert)", "amount": 18000.00,
                     "note": "Devis 31 056€ TTC ramené à 18 000€ TTC par expert (suppression terrassements excessifs)"},
                    {"desc": "Maîtrise d'œuvre bassin rétention (Ingesurf)", "amount": 5400.00,
                     "note": "Devis SEIRI/DIEGO 4 500€ HT soit 5 400€ TTC — conception"},
                    {"desc": "Direction exécution travaux bassin", "amount": 6480.00,
                     "note": "Devis SEIRI/DIEGO 5 400€ HT soit 6 480€ TTC"},
                    {"desc": "Maîtrise d'œuvre murs soutènement (Epsilon GE)", "amount": 12600.00,
                     "note": "Devis 10 500€ HT + calcul structure 2 000€ HT estimé par expert"},
                    {"desc": "Géomètre BBASS — relevé + direction exécution", "amount": 3480.00,
                     "note": "Devis 2 900€ HT + mission DET 2 000€ HT estimée par expert = 4 900€ HT soit ~5 880€ TTC"},
                ],
                "total_travaux": 45960.00,
                "note_travaux": "Responsabilité 100% Beaussier selon expert — travaux non conformes au PC réalisés de sa propre initiative",
                # Demandes de Beaussier (Me Vernhet — Dire n°6)
                "demandes_beaussier": [
                    {"desc": "Préjudice de jouissance", "amount_demande": None,
                     "amount_expert": 0,
                     "note": "Non chiffré par Beaussier, rejeté par expert : c'est elle qui a pris l'initiative des travaux non conformes"},
                    {"desc": "Frais de justice et conseil technique", "amount_demande": 10000.00,
                     "amount_expert": 0,
                     "note": "Rejeté — l'expert note que c'est Legland qui est à l'origine de l'instance, la SCA ne pouvant construire"},
                    {"desc": "Changement pare-pluie façade ouest (2025)", "amount_demande": 804.00,
                     "amount_expert": 0,
                     "note": "Rejeté — entretien normal lié au retard de construction du mur mitoyen"},
                    {"desc": "Responsabilité contractuelle art. 1217 CC (appel HAH)", "amount_demande": 40000.00,
                     "amount_expert": None,
                     "note": "Demandé dans conclusions d'appel HAH — prétend abus de majorité de Legland"},
                ],
                "total_demande_beaussier": 50804.00,
                "total_expert_beaussier": 0,
                "note_beaussier": "Expert : 0€ de préjudice retenu pour Beaussier (zéro euros)",
                # Condamnations prononcées
                "condamnations": [
                    {"desc": "Art. 700 CPC — HAH 1ère instance → Legland", "amount": 1000.00,
                     "beneficiaire": "Legland", "payeur": "Beaussier"},
                    {"desc": "Art. 700 CPC — HAH 1ère instance → SCA", "amount": 1000.00,
                     "beneficiaire": "SCA", "payeur": "Beaussier"},
                    {"desc": "Dépens HAH 1ère instance", "amount": None,
                     "beneficiaire": "Legland/SCA", "payeur": "Beaussier"},
                ],
                # Demandes en cours (pas encore jugées)
                "demandes_en_cours": [
                    {"procedure": "Référé expulsion (JCP)", "demandeur": "SCA",
                     "desc": "Expulsion + indemnité d'occupation 1 600€/mois depuis 01/2023",
                     "estimation_low": 57600, "estimation_high": 72000,
                     "note": "1 600€ × 36-45 mois (jan 2023 → audience 2026)"},
                    {"procedure": "Appel HAH (CA Montpellier)", "demandeur": "Beaussier",
                     "desc": "Art. 700 + 40 000€ responsabilité contractuelle",
                     "estimation_low": 3000, "estimation_high": 43000,
                     "note": "Délibéré 31/03/2026 — Beaussier demande 3K art.700 + 40K dommages"},
                    {"procedure": "Procédure au fond (TJ)", "demandeur": "Legland/SCA",
                     "desc": "Travaux remise en conformité + préjudices",
                     "estimation_low": 77535, "estimation_high": 130000,
                     "note": "Expert retient 77 535€ préjudice Legland + ~46K travaux 100% Beaussier"},
                ],
            },
        },
        # Impayés envers Me Axel Saint Martin
        "axel_unpaid": {
            "paid_sca": [
                {"date": "2024-04-11", "amount": 1800, "desc": "Mandataire ad'hoc (Me Sandian/AMAJ)"},
                {"date": "2025-07-15", "amount": 1050, "desc": "Référé Beaussier"},
                {"date": "2025-10-14", "amount": 1800, "desc": "Référé Expulsion (n°2025-10-112)"},
                {"date": "2025-10-14", "amount": 1800, "desc": "Défense Référé Nullité AG (n°2025-10-113)"},
                {"date": "2025-10-27", "amount": 1275, "desc": "Assignation Mandataire (n°2025-10-124)"},
            ],
            "total_paid_sca": 7725,
            "paid_perso": [
                {"date": "2024-08-21", "amount": 3000, "desc": "Virement perso (provision)"},
                {"date": "2025-07-15", "amount": 1050, "desc": "Virement perso (remboursé via SCA)"},
                {"date": "2025-07-15", "amount": 600, "desc": "Virement perso"},
            ],
            "total_paid_perso": 4650,
            "sca_owes_legland": 2974.11,
            "beaussier_qp_unpaid": 7105.89,
            "note": "SCA doit 2 974€ à Legland (QP fournisseurs). Beaussier doit 7 106€ à la SCA (QP impayée).",
        },
    }


@app.get("/api/v1/costs")
def get_costs():
    """Monthly recurring costs + annual fee analysis."""
    positions = build_positions()
    P["_eur_usd"] = get_eur_usd()
    return compute_fees(P, positions)


@app.get("/api/v1/insights/rules")
def get_insights_rules():
    """Rules-based financial insights with severity."""
    positions = build_positions()
    P["_eur_usd"] = get_eur_usd()
    diversification = compute_diversification(positions)
    fees = compute_fees(P, positions)
    loans = get_loans()
    return generate_insights(P, positions, diversification, fees, loans)


@app.get("/api/v1/budget/projections")
def get_budget_projections():
    """M+1/+2/+3 and Y+1 projections."""
    txs = load_transactions(months=12)
    monthly = aggregate_monthly_budget(txs) if txs else []
    return compute_projections(monthly, P)


@app.get("/api/v1/loans/analysis")
def get_loans_analysis():
    """Detailed loan analysis with inflation comparison + projections."""
    loans = get_loans()
    total_debt = sum(l.get("remaining", 0) for l in loans)
    inf = INFLATION_RATE  # 0.024

    # Inflation-adjusted debt projections (year 0 → 20)
    projections = []
    for year in range(0, 21):
        # Nominal debt reduces by amortization, but we also show the real value
        # Real value of 1€ owed in N years = 1 / (1 + inflation)^N
        deflator = 1 / ((1 + inf) ** year)
        # For each loan: project remaining nominal debt after N years of payments
        nom_debt = 0
        for l in loans:
            rem = l.get("remaining", 0)
            rate = (l.get("rate_numeric") or 0) / 100
            monthly = l.get("monthly_payment") or 0
            rm = l.get("remaining_months")
            if rm and year * 12 >= rm:
                # Loan fully paid off
                continue
            if monthly > 0 and rate > 0:
                r = rate / 12
                # Outstanding after year*12 payments
                n_paid = min(year * 12, rm or year * 12)
                balance = rem * ((1 + r) ** n_paid) - monthly * (((1 + r) ** n_paid - 1) / r)
                nom_debt += max(0, balance)
            elif monthly > 0:
                # 0% loan: linear amortization
                nom_debt += max(0, rem - monthly * year * 12)
            else:
                # Interest-only or no payment (PTZ deferred)
                nom_debt += rem
        real_debt = round(nom_debt * deflator, 0)
        projections.append({
            "year": year,
            "nominal_debt": round(nom_debt, 0),
            "real_debt": real_debt,
            "inflation_erosion": round(nom_debt - real_debt, 0),
        })

    return {
        "loans": loans,
        "inflation_rate": INFLATION_RATE * 100,
        "summary": {
            "total_debt": total_debt,
            "total_monthly": sum(l.get("monthly_payment", 0) or 0 for l in loans),
            "shields": len([l for l in loans if l.get("vs_inflation") == "bouclier_inflation"]),
            "costly": len([l for l in loans if l.get("vs_inflation") == "rembourser"]),
            "real_debt_today": total_debt,
            "real_debt_10y": projections[10]["real_debt"] if len(projections) > 10 else None,
            "inflation_gain_10y": projections[10]["inflation_erosion"] if len(projections) > 10 else None,
        },
        "projections": projections,
    }


@app.get("/api/v1/patrimoine/projection")
def get_patrimoine_projection():
    """20-year patrimoine projection accounting for inflation.
    Real estate appreciates with inflation, debt erodes in real terms."""
    inf = INFLATION_RATE  # 2.4%
    real_estate_extra = 0.005  # Real estate historically +0.5% above inflation in France

    # Current values
    sca = P.get("sca_la_desirade", {})
    property_val = sca.get("property", {}).get("bourso_estimate", 0) * sca.get("ownership_pct", 50.633) / 100
    investments = sum(p["value_eur"] for p in build_positions())
    cash = sum(a["balance"] for a in ACCOUNTS if a["account_type"] in ("checking", "savings") and not a.get("excluded"))
    loans_data = get_loans()
    total_debt = sum(l.get("remaining", 0) for l in loans_data)

    # Assumptions
    STOCK_REAL_RETURN = 0.07  # 7% nominal (~4.6% real)
    SAVINGS_RATE = 0.03       # Livrets regulated rate

    projections = []
    for year in range(0, 21):
        deflator = 1 / ((1 + inf) ** year)

        # Real estate: appreciates at inflation + 0.5%/year (nominal)
        re_nominal = property_val * ((1 + inf + real_estate_extra) ** year)
        re_real = round(re_nominal * deflator, 0)

        # Investments: 7% nominal growth
        inv_nominal = investments * ((1 + STOCK_REAL_RETURN) ** year)
        inv_real = round(inv_nominal * deflator, 0)

        # Cash/savings: grows at savings rate
        cash_nominal = cash * ((1 + SAVINGS_RATE) ** year)
        cash_real = round(cash_nominal * deflator, 0)

        # Debt: amortization schedule (nominal), then deflate
        nom_debt = 0
        for l in loans_data:
            rem = l.get("remaining", 0)
            rate = (l.get("rate_numeric") or 0) / 100
            monthly = l.get("monthly_payment") or 0
            rm = l.get("remaining_months")
            if rm and year * 12 >= rm:
                continue
            if monthly > 0 and rate > 0:
                r = rate / 12
                n_paid = min(year * 12, rm or year * 12)
                try:
                    balance = rem * ((1 + r) ** n_paid) - monthly * (((1 + r) ** n_paid - 1) / r)
                except OverflowError:
                    balance = 0
                nom_debt += max(0, balance)
            elif monthly > 0:
                nom_debt += max(0, rem - monthly * year * 12)
            else:
                nom_debt += rem
        debt_real = round(nom_debt * deflator, 0)

        net_nominal = round(re_nominal + inv_nominal + cash_nominal - nom_debt, 0)
        net_real = round(re_real + inv_real + cash_real - debt_real, 0)

        projections.append({
            "year": year,
            "net_nominal": net_nominal,
            "net_real": net_real,
            "real_estate_real": re_real,
            "investments_real": inv_real,
            "cash_real": cash_real,
            "debt_real": debt_real,
        })

    return {
        "inflation_rate": inf * 100,
        "assumptions": {
            "stock_return": STOCK_REAL_RETURN * 100,
            "savings_rate": SAVINGS_RATE * 100,
            "real_estate_extra": real_estate_extra * 100,
        },
        "current": {
            "real_estate": round(property_val, 0),
            "investments": round(investments, 0),
            "cash": round(cash, 0),
            "debt": round(total_debt, 0),
            "net": round(property_val + investments + cash - total_debt, 0),
        },
        "projections": projections,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
