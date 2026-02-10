"""
Finary Clone — Real Portfolio History Manager
Reconstitutes portfolio value over time using Yahoo Finance historical prices.
Saves daily snapshots for ongoing tracking.
"""
import json
import math
from pathlib import Path
from datetime import date, timedelta, datetime

DATA_DIR = Path(__file__).resolve().parent.parent / "scrapers" / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
HISTORY_CACHE = DATA_DIR / "portfolio_history.json"

# IBKR positions (the big ones that move the needle)
IBKR_HOLDINGS = {
    "MSFT": {"qty": 45.2854, "cost_usd": 20293},
    "GOOGL": {"qty": 105.3515, "cost_usd": 20210},
    "NVDA": {"qty": 100.0222, "cost_usd": 12653},
}

# TR positions (small, fractional — treat as constant for history)
TR_TOTAL_EUR = 2861.0


def _load_current_constants() -> tuple[float, float, float]:
    """Load current cash, real_estate, debt from latest patrimoine file."""
    files = sorted(DATA_DIR.glob("patrimoine_complet_*.json"), reverse=True)
    if files:
        P = json.loads(files[0].read_text())
        t = P.get("totals", {})
        cash = t.get("total_bank_liquid", 221.16)
        real_estate = t.get("total_real_estate", 483800)
        debt = t.get("total_debt", 232060.75)
        return cash, real_estate, debt
    return 221.16, 483800, 232060.75

CASH_EUR, REAL_ESTATE_EUR, DEBT_EUR = _load_current_constants()


def _fetch_historical_prices(days: int = 365) -> dict[str, list[dict]]:
    """Fetch historical close prices from Yahoo Finance."""
    import yfinance as yf

    tickers = list(IBKR_HOLDINGS.keys()) + ["EURUSD=X"]
    end = date.today()
    start = end - timedelta(days=days + 10)

    data = yf.download(
        tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        group_by="ticker",
        auto_adjust=True,
        progress=False,
    )

    result: dict[str, list[dict]] = {}
    for ticker in tickers:
        try:
            if len(tickers) > 1:
                series = data[ticker]["Close"].dropna()
            else:
                series = data["Close"].dropna()
            result[ticker] = [
                {"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)}
                for d, v in series.items()
            ]
        except (KeyError, TypeError):
            result[ticker] = []

    return result


def build_real_history(days: int = 365) -> list[dict]:
    """Build real portfolio value history using Yahoo Finance prices."""

    # Try cache first (valid for same day)
    if HISTORY_CACHE.exists():
        try:
            cached = json.loads(HISTORY_CACHE.read_text())
            if cached.get("built_date") == date.today().isoformat() and len(cached.get("history", [])) >= days * 0.8:
                return cached["history"][-days:]
        except (json.JSONDecodeError, KeyError):
            pass

    prices = _fetch_historical_prices(days)

    # Build EUR/USD lookup
    eurusd_map: dict[str, float] = {}
    for p in prices.get("EURUSD=X", []):
        eurusd_map[p["date"]] = p["close"]

    # Build price maps per ticker
    price_maps: dict[str, dict[str, float]] = {}
    for ticker in IBKR_HOLDINGS:
        price_maps[ticker] = {}
        for p in prices.get(ticker, []):
            price_maps[ticker][p["date"]] = p["close"]

    # Find all dates
    all_dates = set()
    for pm in price_maps.values():
        all_dates.update(pm.keys())
    all_dates = sorted(all_dates)

    if not all_dates:
        return []

    history = []
    last_eurusd = 1.08
    last_prices: dict[str, float] = {}

    for d_str in all_dates:
        # EUR/USD
        if d_str in eurusd_map:
            last_eurusd = eurusd_map[d_str]
        eur_usd = last_eurusd

        # IBKR portfolio value
        ibkr_val_usd = 0
        ibkr_cost_usd = 0
        for ticker, hold in IBKR_HOLDINGS.items():
            if d_str in price_maps[ticker]:
                last_prices[ticker] = price_maps[ticker][d_str]
            price = last_prices.get(ticker)
            if price:
                ibkr_val_usd += hold["qty"] * price
                ibkr_cost_usd += hold["cost_usd"]

        ibkr_val_eur = ibkr_val_usd / eur_usd if eur_usd else 0
        investments = ibkr_val_eur + TR_TOTAL_EUR

        total_assets = investments + CASH_EUR + REAL_ESTATE_EUR
        net_worth = total_assets - DEBT_EUR
        pnl_eur = (ibkr_val_usd - ibkr_cost_usd) / eur_usd if eur_usd else 0

        history.append({
            "date": d_str,
            "net_worth": round(net_worth, 2),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(DEBT_EUR, 2),
            "breakdown": {
                "investments": round(investments, 2),
                "cash": round(CASH_EUR, 2),
                "real_estate": round(REAL_ESTATE_EUR, 2),
            },
            "pnl_eur": round(pnl_eur, 2),
            "eur_usd": round(eur_usd, 4),
        })

    # Cache result
    HISTORY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_CACHE.write_text(json.dumps({
        "built_date": date.today().isoformat(),
        "history": history,
    }, indent=2))

    return history[-days:]


def save_daily_snapshot(patrimoine: dict, positions_live: list[dict] | None = None):
    """Save today's snapshot for ongoing history tracking."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    snapshot_file = SNAPSHOTS_DIR / f"{today}.json"

    snapshot = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "totals": patrimoine.get("totals", {}),
        "positions_count": len(positions_live) if positions_live else 0,
    }

    if positions_live:
        snapshot["portfolio_value"] = sum(p.get("value_eur", 0) for p in positions_live)
        snapshot["portfolio_pnl"] = sum(p.get("pnl_eur", 0) for p in positions_live)

    snapshot_file.write_text(json.dumps(snapshot, indent=2))
    return snapshot_file
