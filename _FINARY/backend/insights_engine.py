"""
Finary Clone — Financial Insights Engine
Rules-based analysis + data for projections.
"""
import json
import math
from pathlib import Path
from datetime import date, timedelta

DATA_DIR = Path(__file__).resolve().parent.parent / "scrapers" / "data"
TX_DIR = DATA_DIR / "transactions"

# ─── Inflation rate (BCE zone euro, approximate) ──────────────────────────────
INFLATION_RATE = 0.024  # 2.4% annuel zone euro Q1 2026

# ─── Categorization rules ─────────────────────────────────────────────────────

CATEGORY_RULES: list[tuple[str, str]] = [
    # Alimentation
    (r"carrefour|leclerc|auchan|lidl|aldi|monoprix|picard|franprix|intermarche|casino|biocoop|super u|marche|boulang|primeur", "alimentation"),
    (r"deliveroo|uber\s*eat|just\s*eat|frichti|getir|gorillas|too\s*good", "alimentation"),
    # Restaurants
    (r"restaurant|brasserie|mcdon|burger\s*king|kfc|subway|sushi|kebab|pizza|cafe|starbucks|paul\b", "restaurants"),
    # Transport
    (r"sncf|ratp|navigo|uber(?!\s*eat)|bolt|lime|bird|blabla|essence|total\s*energ|shell|bp\b|parkm|stationnement|autoroute|peage", "transport"),
    # Logement
    (r"loyer|edf|engie|gaz|electricite|eau|syndic|assurance\s*hab|charges\s*loc|taxe\s*(?:fonciere|hab)", "logement"),
    # Santé
    (r"pharmacie|doctolib|medecin|dentiste|ophtal|mutuelle|cpam|ameli", "sante"),
    # Abonnements
    (r"netflix|spotify|amazon\s*prime|disney|dazn|canal|sfr|orange|bouygues|free\b|apple|google\s*(?:one|storage)|notion|chatgpt|github|icloud", "abonnements"),
    # Shopping
    (r"zara|h&m|uniqlo|amazon(?!\s*prime)|fnac|darty|ikea|decathlon|leroy\s*merlin|aliexpress|apple\s*store", "shopping"),
    # Loisirs
    (r"cinema|theatre|concert|museum|parc|voyage|hotel|airbnb|booking|sport|salle|gym|piscine", "loisirs"),
    # Banque/Frais
    (r"cotisation|commission|agios|frais\s*bancaire|inter[eê]ts?\s*d[eé]bit|frais\s*carte", "banque_frais"),
    # Assurances
    (r"assurance|maif|maaf|axa|allianz|generali|groupama|macif|mma|matmut", "assurances"),
    # Épargne/Investissement (virements vers épargne)
    (r"trade\s*republic|interactive\s*brokers|ibkr|bourso.*pea|virement.*epargne|livret", "epargne_invest"),
    # Impôts
    (r"impot|dgfip|tresor\s*public|taxe|csg|crds|prelevement\s*source", "impots"),
    # Virements entre comptes (à neutraliser)
    (r"virement\s*(?:emis|recu|permanent)|transfert|sepa.*(?:legland|sylvain)", "virement_interne"),
    # Revenus
    (r"salaire|paie|prime|remboursement|caf\b|pole\s*emploi|allocation|dividende|coupon", "revenu"),
]

# ─── HHI Diversification Score ────────────────────────────────────────────────

def compute_diversification(positions: list[dict]) -> dict:
    """Compute diversification score using Herfindahl-Hirschman Index."""
    if not positions:
        return {"score": 0, "max_score": 10, "details": {}, "breakdown": {}}

    total_value = sum(p["value_eur"] for p in positions)
    if total_value <= 0:
        return {"score": 0, "max_score": 10, "details": {}, "breakdown": {}}

    weights = [p["value_eur"] / total_value * 100 for p in positions]
    weights_sorted = sorted(weights, reverse=True)

    # HHI = sum of squared market shares (0-10000 scale)
    hhi = sum(w ** 2 for w in weights)

    # Concentration metrics
    top1 = weights_sorted[0] if weights_sorted else 0
    top3 = sum(weights_sorted[:3])
    top5 = sum(weights_sorted[:5])

    sectors = set(p.get("sector", "Other") for p in positions)
    countries = set(p.get("country", "??") for p in positions)

    # Country zone mapping
    zones = set()
    zone_map = {
        "US": "Amérique du Nord", "CA": "Amérique du Nord",
        "FR": "Europe", "DE": "Europe", "NL": "Europe", "IE": "Europe",
        "CN": "Asie", "SG": "Asie", "JP": "Asie", "KR": "Asie",
        "BR": "Amérique Latine",
    }
    for p in positions:
        z = zone_map.get(p.get("country", ""), "Autre")
        zones.add(z)

    max_ticker = ""
    max_w = 0
    for p in positions:
        w = p["value_eur"] / total_value * 100
        if w > max_w:
            max_w = w
            max_ticker = p.get("ticker", "")

    # Score calculation /10:
    # - Concentration (0-4 points): HHI penalty
    #   HHI < 1000 (well diversified) = 4pts
    #   HHI 1000-2500 (moderate) = 2pts
    #   HHI > 2500 (concentrated) = 0-1pts
    if hhi < 500:
        concentration_score = 4.0
    elif hhi < 1000:
        concentration_score = 3.0
    elif hhi < 1500:
        concentration_score = 2.0
    elif hhi < 2500:
        concentration_score = 1.0
    else:
        concentration_score = 0.0

    # - Sectors (0-3 points)
    sector_score = min(3.0, len(sectors) * 0.3)

    # - Geographic (0-3 points)
    geo_score = min(3.0, len(zones) * 0.75)

    total_score = round(concentration_score + sector_score + geo_score, 1)
    total_score = min(10, total_score)

    # Rating
    if total_score <= 3:
        rating = "Insuffisant"
    elif total_score <= 5:
        rating = "Moyen"
    elif total_score <= 7:
        rating = "Correct"
    else:
        rating = "Bon"

    return {
        "score": total_score,
        "max_score": 10,
        "rating": rating,
        "details": {
            "num_positions": len(positions),
            "num_sectors": len(sectors),
            "num_countries": len(countries),
            "num_zones": len(zones),
            "zones": sorted(zones),
            "max_weight_pct": round(max_w, 1),
            "max_weight_ticker": max_ticker,
            "top3_weight_pct": round(top3, 1),
            "top5_weight_pct": round(top5, 1),
            "hhi": round(hhi),
        },
        "breakdown": {
            "concentration": {"score": concentration_score, "max": 4, "hhi": round(hhi)},
            "sectoral": {"score": round(sector_score, 1), "max": 3, "sectors": len(sectors)},
            "geographic": {"score": round(geo_score, 1), "max": 3, "zones": len(zones)},
        },
    }


# ─── Loan vs Inflation Analysis ───────────────────────────────────────────────

def _infer_rate(borrowed: float, remaining: float, monthly: float, loan_type: str | None) -> float | None:
    """Compute annual interest rate from loan amortization data.
    
    Strategy:
    1. If monthly ≈ interest-only on remaining → rate = (monthly*12)/remaining
    2. If total_paid ≈ borrowed → rate ≈ 0%
    3. Binary search for amortizing rate
    """
    if monthly <= 0 or remaining <= 0:
        return None

    # Check if payments are interest-only (PAS in différé, IO mortgages)
    implied_annual = (monthly * 12) / remaining * 100
    if 0.1 < implied_annual < 8.0:
        # Verify: if this were interest-only, principal unchanged → borrowed ≈ remaining or small amort
        principal_paid = borrowed - remaining if borrowed > remaining else 0
        if borrowed > 0 and principal_paid / borrowed < 0.25:
            return round(implied_annual, 2)

    # Check near-zero rate: total payments ≈ borrowed amount
    if borrowed > 0 and monthly > 0:
        total_months_guess = remaining / monthly
        total_paid_est = (borrowed - remaining) + remaining  # = borrowed
        actual_total = ((borrowed - remaining) / monthly + remaining / monthly) * monthly
        if abs(actual_total - borrowed) / borrowed < 0.05:
            return 0.01  # effectively 0%

    # Binary search for standard amortizing rate
    for rate_bp in range(1, 2000):
        annual_rate = rate_bp / 10000.0
        r = annual_rate / 12
        try:
            inner = 1 - (borrowed * r / monthly)
            if inner <= 0:
                continue
            total_months = int(round(-math.log(inner) / math.log(1 + r)))
            if total_months < 6 or total_months > 480:
                continue
            # Find elapsed months from remaining balance
            for elapsed in range(0, total_months + 1):
                bal = borrowed * (1 + r) ** elapsed - monthly * ((1 + r) ** elapsed - 1) / r
                if abs(bal - remaining) < remaining * 0.02:
                    return round(annual_rate * 100, 2)
        except (ValueError, OverflowError):
            continue

    return None

def analyze_loans(loans: list[dict]) -> list[dict]:
    """Enrich loans with inflation analysis & recommendations."""
    # Default rates for known French loan types
    TYPE_DEFAULTS = {"PTZ": 0.0, "PAS": 0.98}
    results = []
    for loan in loans:
        rate_str = loan.get("rate")
        rate = _parse_rate(rate_str)
        # Infer rate from loan type if not explicitly set
        if rate is None and loan.get("type") in TYPE_DEFAULTS:
            rate = TYPE_DEFAULTS[loan["type"]]

        remaining = loan.get("remaining", 0)
        monthly = loan.get("monthly_payment") or 0
        borrowed = loan.get("borrowed") or remaining

        # --- Compute rate from amortization data when missing ---
        if rate is None and monthly > 0 and remaining > 0:
            rate = _infer_rate(borrowed, remaining, monthly, loan.get("type"))

        # For Bourso personal loans with no monthly/rate, use typical rates
        if rate is None and loan.get("institution") == "Boursobank" and loan.get("type") in ("consumer", "CONSUMER"):
            rate = 0.75  # Bourso prêt perso typical 0.75%

        remaining = loan.get("remaining", 0)
        monthly = loan.get("monthly_payment") or 0
        borrowed = loan.get("borrowed") or remaining

        # Remaining duration (months)
        if rate is not None and rate > 0 and monthly and monthly > 0 and remaining > 0:
            # Check if interest-only (monthly ≈ interest on remaining)
            monthly_interest = remaining * (rate / 100) / 12
            if abs(monthly - monthly_interest) / monthly < 0.15:
                # Interest-only — estimate from typical PAS/mortgage duration
                remaining_months = 300 if loan.get("type") == "PAS" else 240
            else:
                # Amortizing — compute from rate
                r = rate / 100 / 12
                try:
                    inner = 1 - (remaining * r / monthly)
                    if inner > 0:
                        remaining_months = int(math.ceil(-math.log(inner) / math.log(1 + r)))
                    else:
                        remaining_months = math.ceil(remaining / monthly)
                except (ValueError, OverflowError):
                    remaining_months = math.ceil(remaining / monthly)
        elif monthly and monthly > 0 and remaining > 0:
            remaining_months = math.ceil(remaining / monthly)
        else:
            remaining_months = None

        # Total cost (remaining interest + insurance)
        if monthly and remaining_months:
            total_payments_remaining = monthly * remaining_months
            total_interest_remaining = total_payments_remaining - remaining
        else:
            total_interest_remaining = None
            total_payments_remaining = None

        # Insurance cost estimate (typically 0.1-0.4% of borrowed)
        insurance_annual = borrowed * 0.002 if borrowed else 0  # conservative 0.2%
        insurance_remaining = insurance_annual * (remaining_months / 12) if remaining_months else None

        # Real rate = nominal - inflation
        real_rate = (rate - INFLATION_RATE * 100) if rate is not None else None

        # Recommendation
        if rate is not None:
            if rate == 0:
                reco = "bouclier_inflation"
                reco_text = "Taux 0% — bouclier parfait contre l'inflation. Rembourser le plus tard possible."
                reco_detail = f"Votre prêt vous fait gagner {INFLATION_RATE*100:.1f}%/an en pouvoir d'achat sur {remaining:,.0f}€."
            elif rate < INFLATION_RATE * 100:
                reco = "bouclier_inflation"
                reco_text = f"Taux {rate:.2f}% < inflation {INFLATION_RATE*100:.1f}% — bouclier inflation."
                reco_detail = f"Gain réel: {abs(real_rate):.2f}%/an. Gardez ce crédit le plus longtemps possible."
            elif rate < INFLATION_RATE * 100 + 1:
                reco = "neutre"
                reco_text = f"Taux {rate:.2f}% ≈ inflation — coût réel quasi nul."
                reco_detail = "Ni urgent à rembourser, ni profitable à garder."
            else:
                reco = "rembourser"
                reco_text = f"Taux {rate:.2f}% > inflation — coût réel positif."
                reco_detail = f"Coût réel: +{real_rate:.2f}%/an. Remboursez en priorité si capital disponible."
        elif loan.get("type") == "margin":
            rate = 5.83  # IBKR benchmark
            real_rate = rate - INFLATION_RATE * 100
            reco = "rembourser"
            reco_text = f"Marge IBKR ~{rate}% — taux très supérieur à l'inflation."
            reco_detail = "Réduisez le levier si possible, sauf si rendement attendu > 6%."
        else:
            reco = "inconnu"
            reco_text = "Taux inconnu — vérifiez vos documents."
            reco_detail = ""

        results.append({
            **loan,
            "rate_numeric": rate,
            "real_rate": round(real_rate, 2) if real_rate is not None else None,
            "inflation_rate": INFLATION_RATE * 100,
            "vs_inflation": reco,
            "recommendation": reco_text,
            "recommendation_detail": reco_detail,
            "remaining_months": remaining_months,
            "total_interest_remaining": round(total_interest_remaining, 2) if total_interest_remaining else None,
            "total_payments_remaining": round(total_payments_remaining, 2) if total_payments_remaining else None,
            "insurance_remaining_est": round(insurance_remaining, 2) if insurance_remaining else None,
        })
    return results


def _parse_rate(rate_str) -> float | None:
    if rate_str is None:
        return None
    if isinstance(rate_str, (int, float)):
        return float(rate_str)
    s = str(rate_str).strip()
    # "1.68%" or "5.83% USD / 4.83% EUR" → take first number
    import re
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", s)
    if m:
        return float(m.group(1).replace(",", "."))
    try:
        return float(s)
    except ValueError:
        return None


# ─── Fee Analysis ─────────────────────────────────────────────────────────────

# TER (Total Expense Ratio) for known ETFs
ETF_TER = {
    "IE00B3WJKG14": 0.15,  # S&P 500 IT UCITS ETF
}

def compute_fees(patrimoine: dict, positions: list[dict]) -> dict:
    """Compute real fee breakdown."""
    tr = patrimoine.get("trade_republic", {})
    ibkr = patrimoine.get("ibkr", {})

    # TR: 1€ per trade, count positions as proxy (each was at least 1 trade)
    tr_positions = len(tr.get("positions", []))
    tr_trading_fees = tr_positions * 1.0  # minimum, 1 trade per position

    # TR PFOF (Payment for Order Flow) spread cost estimate: ~0.1-0.3% per trade
    tr_total_invested = tr.get("total_invested", 0) or 0
    tr_pfof_est = tr_total_invested * 0.002  # ~0.2% spread cost on total invested

    # IBKR commissions (tiered: ~$0.0035/share min $0.35, or ~$1/trade for small trades)
    ibkr_positions = len(ibkr.get("positions", []))
    ibkr_commission_est = ibkr_positions * 2.0  # ~$2/trade average estimate

    # IBKR margin interest (real)
    margin_usd = abs(ibkr.get("margin_loan_usd", 0))
    margin_rate_str = ibkr.get("margin_interest_rate", "5.83%")
    margin_rate = _parse_rate(margin_rate_str) or 5.83
    margin_interest_annual = margin_usd * margin_rate / 100  # in USD
    # Convert USD -> EUR
    eur_usd = patrimoine.get("_eur_usd", 1.19)
    margin_interest_annual_eur = margin_interest_annual / eur_usd

    # ETF TER costs (annual, proportional to holding value)
    ter_total = 0
    ter_details = []
    for p in positions:
        isin = p.get("isin")
        if isin and isin in ETF_TER:
            ter = ETF_TER[isin]
            cost = p["value_eur"] * ter / 100
            ter_total += cost
            ter_details.append({"isin": isin, "name": p.get("name"), "ter": ter, "annual_cost": round(cost, 2)})

    # Portfolio-weighted average TER (assume stocks = 0 TER, only ETFs matter)
    total_value = sum(p["value_eur"] for p in positions)
    weighted_ter = (ter_total / total_value * 100) if total_value > 0 else 0

    annual_total = tr_trading_fees + tr_pfof_est + ibkr_commission_est + margin_interest_annual_eur + ter_total

    # Monthly costs (from loans)
    monthly_loan = patrimoine.get("totals", {}).get("monthly_loan_payments", 0)
    monthly_margin = patrimoine.get("totals", {}).get("monthly_margin_cost", 0)
    monthly_total = monthly_loan + monthly_margin

    # ETF average TER benchmark
    benchmark_ter = 0.20  # low-cost ETF benchmark
    potential_savings = max(0, (weighted_ter - benchmark_ter) / 100 * total_value)

    return {
        "monthly_total": round(monthly_total, 2),
        "breakdown": [
            {"name": "PAS 2 (immo)", "amount": 90.32, "type": "credit", "category": "immobilier"},
            {"name": "PACP (conso)", "amount": 73.69, "type": "credit", "category": "consommation"},
            {"name": f"Marge IBKR (~{margin_rate:.1f}%)", "amount": round(monthly_margin, 2), "type": "margin", "category": "investissement"},
        ],
        "annual_fees": {
            "tr_trading": round(tr_trading_fees, 2),
            "tr_pfof_spread_est": round(tr_pfof_est, 2),
            "ibkr_commissions_est": round(ibkr_commission_est, 2),
            "margin_interest_annual": round(margin_interest_annual_eur, 2),
            "etf_ter_total": round(ter_total, 2),
            "total": round(annual_total, 2),
        },
        "ter_details": ter_details,
        "weighted_avg_ter": round(weighted_ter, 3),
        "benchmark_ter": benchmark_ter,
        "potential_savings": round(potential_savings, 2),
        "pct_of_patrimoine": round(annual_total / max(1, total_value) * 100, 3),
    }


# ─── Rules-based Insights Engine ─────────────────────────────────────────────

def generate_insights(patrimoine: dict, positions: list[dict], diversification: dict, fees: dict, loans_analysis: list[dict]) -> list[dict]:
    """Generate actionable insights with severity levels."""
    insights = []
    total_value = sum(p["value_eur"] for p in positions)
    net_worth = patrimoine.get("totals", {}).get("net_worth", 0)
    total_debt = patrimoine.get("totals", {}).get("total_debt", 0)

    # 1. Concentration risk
    div_details = diversification.get("details", {})
    top1 = div_details.get("max_weight_pct", 0)
    top1_ticker = div_details.get("max_weight_ticker", "")
    if top1 > 40:
        insights.append({
            "id": "concentration_extreme",
            "severity": "critical",
            "category": "diversification",
            "title": f"Concentration extrême : {top1_ticker} = {top1:.0f}%",
            "description": f"Une seule position représente {top1:.0f}% de votre portefeuille. Règle : max 25% par position.",
            "action": f"Diversifier en vendant progressivement {top1_ticker} et en réinvestissant en ETF World.",
            "impact_eur": round(total_value * (top1 - 25) / 100, 0),
        })
    elif top1 > 25:
        insights.append({
            "id": "concentration_high",
            "severity": "warn",
            "category": "diversification",
            "title": f"Concentration élevée : {top1_ticker} = {top1:.0f}%",
            "description": f"{top1_ticker} pèse {top1:.0f}% du portefeuille. Risque idiosyncratique.",
            "action": "Rééquilibrer progressivement vers un ETF diversifié.",
        })

    top3 = div_details.get("top3_weight_pct", 0)
    if top3 > 80:
        insights.append({
            "id": "top3_concentrated",
            "severity": "warn",
            "category": "diversification",
            "title": f"Top 3 positions = {top3:.0f}% du portefeuille",
            "description": "Trop de dépendance aux 3 premières lignes.",
            "action": "Diversifier vers des secteurs sous-représentés.",
        })

    # 2. Loan vs inflation
    for loan in loans_analysis:
        if loan.get("vs_inflation") == "bouclier_inflation":
            insights.append({
                "id": f"loan_inflation_shield_{loan.get('name', '')[:20]}",
                "severity": "info",
                "category": "credit",
                "title": f"🛡️ {loan['name']} — bouclier inflation",
                "description": loan["recommendation"],
                "action": loan["recommendation_detail"],
            })
        elif loan.get("vs_inflation") == "rembourser" and loan.get("type") != "margin":
            insights.append({
                "id": f"loan_costly_{loan.get('name', '')[:20]}",
                "severity": "warn",
                "category": "credit",
                "title": f"💸 {loan['name']} — coût réel positif",
                "description": loan["recommendation"],
                "action": loan["recommendation_detail"],
            })

    # 3. IBKR margin risk
    margin_eur = abs(patrimoine.get("ibkr", {}).get("cash", {}).get("total_eur", 0))
    if margin_eur > 0:
        margin_pct = margin_eur / max(1, net_worth) * 100
        if margin_pct > 10:
            insights.append({
                "id": "margin_high",
                "severity": "critical",
                "category": "risque",
                "title": f"Levier marge = {margin_pct:.0f}% du patrimoine net",
                "description": f"Emprunt sur marge de {margin_eur:,.0f}€ à ~5.8%. Risque de margin call en cas de correction.",
                "action": "Réduire le levier en vendant des positions ou en injectant du cash.",
            })
        elif margin_pct > 5:
            insights.append({
                "id": "margin_moderate",
                "severity": "warn",
                "category": "risque",
                "title": f"Levier marge modéré ({margin_pct:.0f}%)",
                "description": f"Marge IBKR de {margin_eur:,.0f}€. Coût ~{margin_eur * 0.058:,.0f}€/an.",
                "action": "Surveillez le ratio, réduisez si le marché baisse.",
            })

    # 4. Savings rate
    monthly_costs = patrimoine.get("totals", {}).get("monthly_loan_payments", 0) + patrimoine.get("totals", {}).get("monthly_margin_cost", 0)
    if monthly_costs > 0 and net_worth > 0:
        annual_costs = fees.get("annual_fees", {}).get("total", 0) + monthly_costs * 12
        cost_ratio = annual_costs / net_worth * 100
        if cost_ratio > 5:
            insights.append({
                "id": "cost_ratio_high",
                "severity": "warn",
                "category": "frais",
                "title": f"Coûts = {cost_ratio:.1f}% du patrimoine net",
                "description": f"Coût annuel total de {annual_costs:,.0f}€ sur un patrimoine de {net_worth:,.0f}€.",
                "action": "Réduire les frais de marge ou renégocier les crédits.",
            })

    # 5. Fee efficiency
    pct_patri = fees.get("pct_of_patrimoine", 0)
    if pct_patri > 1.0:
        insights.append({
            "id": "fees_high",
            "severity": "warn",
            "category": "frais",
            "title": f"Frais d'investissement = {pct_patri:.2f}% du portefeuille",
            "description": "Supérieur à la moyenne des investisseurs particuliers (~0.5%).",
            "action": "Privilégier des ETF à faible TER (<0.20%) et réduire la marge.",
        })

    # 6. Dividend yield
    total_div = sum(p.get("value_eur", 0) * (p.get("dividend_yield_pct", 0) or 0) / 100 for p in positions)
    div_yield = total_div / total_value * 100 if total_value > 0 else 0
    if div_yield < 0.5 and total_value > 10000:
        insights.append({
            "id": "low_passive_income",
            "severity": "info",
            "category": "revenus",
            "title": f"Rendement passif faible ({div_yield:.2f}%)",
            "description": f"Projection dividendes: {total_div:,.0f}€/an. Portefeuille orienté croissance.",
            "action": "Normal pour un profil growth. Ajoutez des REITs/aristocrates si revenu passif désiré.",
        })

    # 7. Debt-to-equity
    if total_debt > 0 and net_worth > 0:
        dte = total_debt / net_worth * 100
        if dte > 300:
            insights.append({
                "id": "high_leverage_total",
                "severity": "info",
                "category": "bilan",
                "title": f"Ratio dette/patrimoine = {dte:.0f}%",
                "description": f"Endettement total: {total_debt:,.0f}€ vs patrimoine net: {net_worth:,.0f}€.",
                "action": "Ceci inclut les prêts immobiliers (SCA). Le ratio est élevé mais normal avec de l'immobilier.",
            })

    # 8. Emergency fund check
    liquid = patrimoine.get("totals", {}).get("total_bank_liquid", 0)
    if liquid < monthly_costs * 3 and monthly_costs > 0:
        insights.append({
            "id": "emergency_fund_low",
            "severity": "critical",
            "category": "sécurité",
            "title": "Épargne de précaution insuffisante",
            "description": f"Liquidités: {liquid:,.0f}€ < 3 mois de charges ({monthly_costs * 3:,.0f}€).",
            "action": "Constituez un fonds d'urgence de 3-6 mois de dépenses.",
        })

    # 9. Sector analysis
    sectors = {}
    for p in positions:
        s = p.get("sector", "Other")
        sectors[s] = sectors.get(s, 0) + p["value_eur"]
    tech_pct = sum(v for k, v in sectors.items() if k in ("Technology", "Semiconductors")) / max(1, total_value) * 100
    if tech_pct > 60:
        insights.append({
            "id": "tech_overweight",
            "severity": "warn",
            "category": "diversification",
            "title": f"Surexposition Tech: {tech_pct:.0f}% du portefeuille",
            "description": "Très exposé au secteur technologique. Risque de correction sectorielle.",
            "action": "Diversifier vers santé, industrie, énergie, immobilier.",
        })

    # 10. PEA utilization
    bourso = patrimoine.get("boursobank", {})
    pea_balance = None
    for acc_data in bourso.get("accounts", {}).values():
        if acc_data.get("type", "").lower() == "pea":
            pea_balance = acc_data.get("balance", 0)
    if pea_balance is not None and pea_balance < 1000 and total_value > 10000:
        insights.append({
            "id": "pea_underutilized",
            "severity": "info",
            "category": "optimisation_fiscale",
            "title": f"PEA sous-utilisé ({pea_balance:,.0f}€)",
            "description": "Le PEA offre une fiscalité avantageuse après 5 ans (17.2% vs 30% flat tax).",
            "action": "Transférez vos achats ETF Europe vers le PEA pour économiser ~13% d'impôt sur les plus-values.",
        })

    # Sort by severity
    severity_order = {"critical": 0, "warn": 1, "info": 2}
    insights.sort(key=lambda x: severity_order.get(x["severity"], 9))

    return insights


# ─── Budget Projections ───────────────────────────────────────────────────────

def compute_projections(monthly_data: list[dict], patrimoine: dict) -> dict:
    """Compute M+1, M+2, M+3, Y+1 projections from historical monthly data."""
    if not monthly_data or len(monthly_data) < 2:
        return {"months": [], "year": None}

    # Use last 3 months average for short-term projection
    recent = monthly_data[-3:] if len(monthly_data) >= 3 else monthly_data
    avg_income = sum(m.get("income", 0) for m in recent) / len(recent)
    avg_expenses = sum(m.get("expenses", 0) for m in recent) / len(recent)
    avg_savings = avg_income - avg_expenses

    # Monthly costs (fixed)
    monthly_loan = patrimoine.get("totals", {}).get("monthly_loan_payments", 0)
    monthly_margin = patrimoine.get("totals", {}).get("monthly_margin_cost", 0)
    fixed_costs = monthly_loan + monthly_margin

    # Projection months
    from datetime import date
    today = date.today()
    projections = []
    for i in range(1, 4):
        m = today.month + i
        y = today.year
        while m > 12:
            m -= 12
            y += 1
        projections.append({
            "month": f"{y}-{m:02d}",
            "projected_income": round(avg_income, 2),
            "projected_expenses": round(avg_expenses, 2),
            "projected_savings": round(avg_savings, 2),
            "fixed_costs": round(fixed_costs, 2),
            "confidence": "high" if len(monthly_data) >= 6 else "low",
        })

    # Year projection
    annual = {
        "projected_income": round(avg_income * 12, 2),
        "projected_expenses": round(avg_expenses * 12, 2),
        "projected_savings": round(avg_savings * 12, 2),
        "fixed_costs_annual": round(fixed_costs * 12, 2),
        "net_savings_after_fixed": round((avg_savings - fixed_costs) * 12, 2),
    }

    # Passive income projection
    positions = []  # would be passed in real implementation
    dividend_annual = patrimoine.get("_dividend_annual", 0)
    margin_cost_annual = monthly_margin * 12

    annual["passive_income"] = round(dividend_annual, 2)
    annual["investment_costs"] = round(margin_cost_annual, 2)

    return {"months": projections, "year": annual}


# ─── Transaction storage helpers ──────────────────────────────────────────────

def load_transactions(months: int = 12) -> list[dict]:
    """Load transactions from unified storage."""
    TX_DIR.mkdir(parents=True, exist_ok=True)
    all_txs = []
    today = date.today()
    for i in range(months):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        fname = TX_DIR / f"{y}-{m:02d}.json"
        if fname.exists():
            with open(fname) as f:
                all_txs.extend(json.load(f))
    return sorted(all_txs, key=lambda x: x.get("date", ""), reverse=True)


def save_transactions(transactions: list[dict]):
    """Save transactions to monthly files."""
    TX_DIR.mkdir(parents=True, exist_ok=True)
    by_month: dict[str, list] = {}
    for tx in transactions:
        d = tx.get("date", "")
        month_key = d[:7] if len(d) >= 7 else "unknown"
        if month_key not in by_month:
            by_month[month_key] = []
        by_month[month_key].append(tx)

    for month_key, txs in by_month.items():
        if month_key == "unknown":
            continue
        fname = TX_DIR / f"{month_key}.json"
        # Merge with existing
        existing = []
        if fname.exists():
            with open(fname) as f:
                existing = json.load(f)
        # Deduplicate by hash
        seen = set()
        for tx in existing:
            h = _tx_hash(tx)
            seen.add(h)
        merged = list(existing)
        for tx in txs:
            h = _tx_hash(tx)
            if h not in seen:
                merged.append(tx)
                seen.add(h)
        with open(fname, "w") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)


def _tx_hash(tx: dict) -> str:
    import hashlib
    key = f"{tx.get('date', '')}-{tx.get('amount', '')}-{tx.get('description', '')}-{tx.get('bank', '')}"
    return hashlib.md5(key.encode()).hexdigest()


def categorize_transaction(description: str) -> str:
    """Categorize a transaction by description."""
    import re
    desc_lower = description.lower()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, desc_lower):
            return category
    return "autre"


def aggregate_monthly_budget(transactions: list[dict]) -> list[dict]:
    """Aggregate transactions into monthly budget summaries."""
    from collections import defaultdict
    monthly: dict[str, dict] = {}

    for tx in transactions:
        d = tx.get("date", "")
        month = d[:7] if len(d) >= 7 else None
        if not month:
            continue
        if month not in monthly:
            monthly[month] = {"income": 0, "expenses": 0, "categories": defaultdict(float)}

        amount = tx.get("amount", 0)
        category = tx.get("category", "autre")

        # Skip internal transfers
        if category == "virement_interne":
            continue

        if category == "revenu" or amount > 0:
            monthly[month]["income"] += abs(amount)
        else:
            monthly[month]["expenses"] += abs(amount)
            monthly[month]["categories"][category] += abs(amount)

    result = []
    for month in sorted(monthly.keys()):
        m = monthly[month]
        income = m["income"]
        expenses = m["expenses"]
        savings_rate = ((income - expenses) / income * 100) if income > 0 else 0
        result.append({
            "month": month,
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "savings_rate": round(savings_rate, 1),
            "categories": {k: round(v, 2) for k, v in m["categories"].items()},
        })
    return result
