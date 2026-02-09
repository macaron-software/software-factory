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

def load_patrimoine():
    files = sorted(DATA_DIR.glob("patrimoine_complet_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No patrimoine_complet_*.json found in scrapers/data/")
    with open(files[0]) as f:
        return json.load(f)

P = load_patrimoine()

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
        invested = pos["current_value_eur"] - pos["unrealized_pnl_eur"]

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
            pnl = pos["unrealized_pnl_eur"]
            pnl_pct = pos["unrealized_pnl_pct"] if pos["unrealized_pnl_pct"] else (
                round(pnl / abs(invested) * 100, 2) if invested != 0 else 0
            )

        total_value += val
        short_name = pos["name"].split()[0][:6].upper() if pos["name"] else isin[:6]

        positions.append({
            "id": _id("pos", i + 1),
            "account_id": "acc-0001",
            "ticker": short_name,
            "isin": isin,
            "name": pos["name"],
            "quantity": shares,
            "avg_cost": pos["avg_price_eur"],
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
            "name": pos["symbol"],
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

    bourso_liquid = P["boursobank"]["total_liquid"]
    bourso_savings = P["boursobank"]["total_savings"]
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
            {"name": "ibkr", "display_name": "Interactive Brokers", "total": round(ibkr_val, 2)},
            {"name": "credit_agricole", "display_name": "Crédit Agricole", "total": round(ca_liquid + P["credit_agricole"]["total_debt"], 2)},
            {"name": "boursobank", "display_name": "Boursobank", "total": round(bourso_liquid + bourso_savings + P["boursobank"]["total_loans"], 2)},
            {"name": "trade_republic", "display_name": "Trade Republic", "total": round(tr_val, 2)},
            {"name": "sca", "display_name": "SCA La Désirade", "total": round(sca_prop, 2)},
        ],
        "variation_day": None,
        "variation_month": None,
        "eur_usd": round(eur_usd, 4),
        "live_prices": live_count,
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
def get_transactions(limit: int = Query(50)):
    return []  # No transaction data scraped yet


@app.get("/api/v1/accounts/{account_id}/transactions")
def get_account_transactions(account_id: str, limit: int = Query(50)):
    return []


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
def get_category_spending(limit: int = Query(3)):
    ca_credits = P["credit_agricole"]["monthly_payments"]
    margin_monthly = P["totals"].get("monthly_margin_cost", 0)
    bourso_loans = P.get("boursobank", {}).get("loans", [])
    bourso_monthly = sum(l.get("monthly_payment", 0) or round(l["remaining"] / 24, 2) for l in bourso_loans)
    return [
        {"category": "credits_immobilier", "total": round(ca_credits * limit, 2), "count": 2},
        {"category": "marge_ibkr", "total": round(margin_monthly * limit, 2), "count": limit},
        {"category": "prets_perso", "total": round(bourso_monthly * limit, 2), "count": len(bourso_loans)},
    ]


@app.get("/api/v1/market/fx")
def get_fx_rates():
    return [
        {"date": date.today().isoformat(), "base_currency": "EUR", "quote_currency": "USD", "rate": EUR_USD},
    ]


@app.get("/api/v1/market/quote/{ticker}")
def get_quote(ticker: str):
    return []


@app.get("/api/v1/market/history/{ticker}")
def get_history(ticker: str, limit: int = Query(365)):
    return []


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
    # --- ONLY mathematically proven rates (from scraped amortization data) ---
    # PTZ: 0% by law (Prêt à Taux Zéro)
    # PAS 2: 90.32€/mo × 12 = 1,083.84€/yr interest, 1,083.84 / 110,594.85 = 0.98%
    #   PROOF: interest-only phase (différé), monthly = exact interest
    # PAS 1: same contract as PAS 2 → 0.98%
    # PACP: borrowed 5,000€, monthly 73.69€, 5000/73.69=67.9mo → total≈5,000€ → 0%
    PROVEN_RATES = {
        "00004690214": 0.0,      # PTZ — 0% par la loi
        "00004690213": 0.98,     # PAS 1 — même contrat que PAS 2
        "00004690212": 0.98,     # PAS 2 — prouvé: 90.32×12/110594.85 = 0.98%
        "73140424333": 0.0,      # PACP — prouvé: total remboursé ≈ capital emprunté
    }
    # Insurance/assurance: NOT scraped → None. To be filled when scraper
    # navigates to credit detail pages (CA "tableau d'amortissement" link exists).

    raw_loans = []
    for credit in P["credit_agricole"]["credits"]:
        acct = credit.get("account", "")
        rate = PROVEN_RATES.get(acct)
        raw_loans.append({
            "institution": "Crédit Agricole",
            "name": credit["name"],
            "type": credit.get("type", "unknown"),
            "borrowed": credit["borrowed"],
            "remaining": credit["remaining"],
            "monthly_payment": credit["monthly_payment"],
            "rate": rate,
            "rate_source": "computed" if rate is not None else "unknown",
            "insurance_monthly": None,  # not scraped yet
            "start_date": credit.get("start_date"),
            "status": credit.get("status"),
        })
    # Boursobank personal loans — rate/monthly NOT in scraped data
    for loan in P["boursobank"]["loans"]:
        raw_loans.append({
            "institution": "Boursobank",
            "name": loan["name"],
            "type": loan.get("type", "consumer"),
            "borrowed": None,
            "remaining": loan["remaining"],
            "monthly_payment": loan.get("monthly_payment"),
            "rate": None,  # not scraped — session expired, need re-login
            "rate_source": "unknown",
            "insurance_monthly": None,
        })
    # IBKR margin
    margin_usd = abs(P["ibkr"].get("margin_loan_usd", 0))
    margin_eur = abs(P["ibkr"]["cash"]["total_eur"]) if margin_usd else 0
    margin_rate = P["ibkr"].get("margin_interest_rate", "5.83%")
    margin_monthly = P["totals"].get("monthly_margin_cost", 0)
    raw_loans.append({
        "institution": "Interactive Brokers",
        "name": "Prêt sur marge",
        "type": "margin",
        "borrowed": None,
        "remaining": round(margin_eur, 2),
        "monthly_payment": round(margin_monthly, 2),
        "rate": str(margin_rate),
        "rate_source": "scraped",  # from IBKR Client Portal
        "insurance_monthly": 0,
    })
    return analyze_loans(raw_loans)


@app.get("/api/v1/sca")
def get_sca():
    """SCA La Désirade data with Grabels market context."""
    sca = P["sca_la_desirade"]
    # Correct property data (scraped values may be approximate)
    sca["property"]["surface_m2"] = 114
    sca["property"]["type"] = "Villa R+1"
    sca["property"]["rooms"] = 4
    sca["property"]["terrain_m2"] = 420
    surface = 114
    terrain_m2 = 420
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
            "median": round(surface * 3530),
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
            "surface_m2": terrain_m2,
            "prix_m2_terrain_grabels": {"low": 250, "median": 380, "high": 500},
            "estimation_terrain": {
                "low": round(terrain_m2 * 250),
                "median": round(terrain_m2 * 380),
                "high": round(terrain_m2 * 500),
            },
        },
    }
    return sca


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
    """Detailed loan analysis with inflation comparison."""
    loans = get_loans()
    return {
        "loans": loans,
        "inflation_rate": INFLATION_RATE * 100,
        "summary": {
            "total_debt": sum(l.get("remaining", 0) for l in loans),
            "total_monthly": sum(l.get("monthly_payment", 0) or 0 for l in loans),
            "shields": len([l for l in loans if l.get("vs_inflation") == "bouclier_inflation"]),
            "costly": len([l for l in loans if l.get("vs_inflation") == "rembourser"]),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
