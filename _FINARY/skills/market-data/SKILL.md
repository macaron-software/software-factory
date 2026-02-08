---
name: market-data
description: Market data aggregation from multiple free providers (yfinance, ECB, Finnhub). Use when building or modifying the market data pipeline. Covers real-time stock/ETF quotes, ISIN-ticker resolution, ECB FX rates (EUR/USD/GBP), historical OHLCV data, instrument metadata enrichment, dividend calendars, and multi-currency portfolio valuation.
---

# Market Data

Pipeline d'agrégation de données de marché multi-providers pour valorisation du portefeuille.

## Providers

### Yahoo Finance (yfinance) — Source principale

```python
import yfinance as yf
from decimal import Decimal

class YFinanceProvider:
    """Cours, historique, dividendes, métadonnées. Gratuit, illimité."""

    def get_quote(self, ticker: str) -> dict:
        """Cours actuel + métadonnées."""
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "ticker": ticker,
            "price": Decimal(str(info.get("currentPrice", 0))),
            "currency": info.get("currency", "USD"),
            "name": info.get("longName", info.get("shortName", "")),
            "sector": info.get("sector"),
            "country": info.get("country"),
            "exchange": info.get("exchange"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
        }

    def get_history(self, ticker: str, period: str = "5y") -> list[dict]:
        """Historique OHLCV daily."""
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        return [
            {
                "date": idx.date(),
                "open": Decimal(str(row["Open"])),
                "high": Decimal(str(row["High"])),
                "low": Decimal(str(row["Low"])),
                "close": Decimal(str(row["Close"])),
                "volume": int(row["Volume"]),
            }
            for idx, row in df.iterrows()
        ]

    def get_dividends(self, ticker: str) -> list[dict]:
        """Historique dividendes."""
        t = yf.Ticker(ticker)
        divs = t.dividends
        return [
            {"date": idx.date(), "amount": Decimal(str(val))}
            for idx, val in divs.items()
        ]

    def search(self, query: str) -> list[dict]:
        """Recherche ticker par nom ou ISIN."""
        import httpx
        r = httpx.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 10},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        results = r.json().get("quotes", [])
        return [
            {"ticker": q["symbol"], "name": q.get("longname", q.get("shortname", "")),
             "exchange": q.get("exchange"), "type": q.get("quoteType")}
            for q in results
        ]
```

### ECB FX Rates

```python
import httpx
from xml.etree import ElementTree
from decimal import Decimal

class ECBFXProvider:
    """Taux de change EUR/X depuis la BCE. Gratuit, quotidien."""

    DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
    NS = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}

    async def get_daily_rates(self) -> dict[str, Decimal]:
        """Taux EUR -> X du jour."""
        async with httpx.AsyncClient() as client:
            r = await client.get(self.DAILY_URL)
        root = ElementTree.fromstring(r.text)
        return {
            cube.get("currency"): Decimal(cube.get("rate"))
            for cube in root.findall(".//ecb:Cube[@currency]", self.NS)
        }

    def convert_to_eur(self, amount: Decimal, currency: str, rates: dict) -> Decimal:
        """Convertit un montant en EUR."""
        if currency == "EUR":
            return amount
        rate = rates.get(currency)
        if not rate:
            raise ValueError(f"No rate for {currency}")
        return (amount / rate).quantize(Decimal("0.01"))

    def fx_impact(self, amount_native: Decimal, currency: str,
                  rate_at_purchase: Decimal, rate_current: Decimal) -> Decimal:
        """Calcule l'impact devise sur un montant."""
        value_at_purchase_rate = amount_native / rate_at_purchase
        value_at_current_rate = amount_native / rate_current
        return value_at_current_rate - value_at_purchase_rate
```

### Finnhub — Enrichissement

```python
import finnhub

class FinnhubProvider:
    """Profils, dividendes futurs, quotes real-time US. Free tier: 60 calls/min."""

    def __init__(self, api_key: str):
        self.client = finnhub.Client(api_key=api_key)

    def get_profile(self, ticker: str) -> dict:
        """Profil societe (secteur GICS, pays, devise)."""
        p = self.client.company_profile2(symbol=ticker)
        return {
            "ticker": p.get("ticker"),
            "name": p.get("name"),
            "sector": p.get("finnhubIndustry"),
            "country": p.get("country"),
            "currency": p.get("currency"),
            "exchange": p.get("exchange"),
            "ipo": p.get("ipo"),
            "market_cap": p.get("marketCapitalization"),
            "logo": p.get("logo"),
        }

    def get_upcoming_dividends(self, ticker: str) -> list[dict]:
        """Dividendes prevus."""
        from datetime import date, timedelta
        today = date.today()
        divs = self.client.stock_dividends(
            ticker, _from=str(today), to=str(today + timedelta(days=365))
        )
        return [
            {"ex_date": d["exDate"], "pay_date": d.get("payDate"),
             "amount": Decimal(str(d["amount"])), "currency": d.get("currency", "USD")}
            for d in divs
        ]
```

## ISIN <-> Ticker Resolution

```python
class ISINResolver:
    """
    Les scrapers retournent parfois un ISIN (Boursobank, CA),
    parfois un ticker (IBKR, TR). Il faut unifier.
    
    Strategie:
    1. Table locale isin_ticker_map (cache permanent)
    2. Yahoo Finance search comme fallback
    3. Preferer le ticker de la bourse principale (XETR pour EU, XNAS/XNYS pour US)
    """
    
    async def resolve(self, identifier: str) -> dict:
        # 1. Check local cache
        cached = await db.fetch_one(
            "SELECT * FROM isin_ticker_map WHERE isin = $1 OR ticker = $1", identifier
        )
        if cached:
            return cached
        
        # 2. Yahoo Finance search
        results = yfinance_provider.search(identifier)
        if results:
            best = results[0]
            await db.execute(
                """INSERT INTO isin_ticker_map (isin, ticker, name, exchange) 
                   VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING""",
                identifier if len(identifier) == 12 else None,
                best["ticker"], best["name"], best["exchange"]
            )
            return best
        
        raise ValueError(f"Cannot resolve: {identifier}")
```

## Multi-Currency Portfolio Valuation

```python
def value_portfolio_multicurrency(positions, rates):
    """
    Valorise le portfolio en EUR avec decomposition FX.
    
    Pour chaque position:
    - value_native = quantity * current_price (devise de cotation)
    - value_eur = value_native / rate_eur_to_native
    - pnl_native = value_native - (quantity * avg_cost)
    - pnl_eur = pnl en EUR (inclut impact FX)
    - fx_exposure = % du portfolio par devise
    """
    results = []
    total_eur = Decimal("0")
    
    for p in positions:
        value_native = p.quantity * p.current_price
        value_eur = convert_to_eur(value_native, p.currency, rates)
        cost_native = p.quantity * p.avg_cost if p.avg_cost else Decimal("0")
        pnl_native = value_native - cost_native
        pnl_eur = convert_to_eur(pnl_native, p.currency, rates)
        
        results.append({
            **p.__dict__,
            "value_native": value_native,
            "value_eur": value_eur,
            "pnl_native": pnl_native,
            "pnl_eur": pnl_eur,
            "pnl_pct": (pnl_native / cost_native * 100) if cost_native else Decimal("0"),
        })
        total_eur += value_eur
    
    # Ajouter le poids de chaque position
    for r in results:
        r["weight_pct"] = (r["value_eur"] / total_eur * 100) if total_eur else Decimal("0")
    
    return results, total_eur
```

## Cache Strategy

```
Redis cache keys:
  finary:quote:{ticker}           TTL 5min (heures marche), 1h (hors marche)
  finary:fx:daily                 TTL 24h
  finary:profile:{ticker}         TTL 7 jours
  finary:networth                 TTL 5min (invalide apres sync)
  finary:portfolio:valuation      TTL 5min (invalide apres sync ou refresh cours)
```

## Scheduler Market Data

```
# Heures de marche EU (09:00-17:30 CET):  refresh cours toutes les 5 min
# Heures de marche US (15:30-22:00 CET):  refresh cours toutes les 5 min
# Hors marche:                             refresh 1x apres cloture
# FX ECB:                                  1x/jour a 16:30 CET
# Historique cours:                         1x/jour a 23:00 CET
# Metadonnees instruments:                 1x/semaine
```
