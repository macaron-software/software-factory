"""Portfolio valuation service — multi-currency valuation with FX decomposition."""

from __future__ import annotations

from decimal import Decimal

from scrapers.models import AssetType, NetWorth, PortfolioValuation, Position


def value_positions(
    positions: list[Position],
    rates: dict[str, Decimal],
) -> tuple[list[PortfolioValuation], Decimal]:
    """
    Value all positions in EUR.

    Args:
        positions: list of Position objects
        rates: ECB rates {currency: rate_vs_eur} (1 EUR = X currency)

    Returns:
        (list of PortfolioValuation, total_eur)
    """
    results: list[PortfolioValuation] = []
    total_eur = Decimal("0")

    for p in positions:
        price = p.current_price or Decimal("0")
        value_native = p.quantity * price
        value_eur = _to_eur(value_native, p.currency, rates)

        cost_native = (p.quantity * p.avg_cost) if p.avg_cost else Decimal("0")
        pnl_native = value_native - cost_native
        pnl_eur = _to_eur(pnl_native, p.currency, rates)
        pnl_pct = (
            (pnl_native / cost_native * 100) if cost_native and cost_native != 0 else Decimal("0")
        )

        results.append(
            PortfolioValuation(
                ticker=p.ticker,
                name=p.name,
                quantity=p.quantity,
                current_price=price,
                currency=p.currency,
                value_native=value_native,
                value_eur=value_eur,
                avg_cost=p.avg_cost,
                pnl_native=pnl_native,
                pnl_eur=pnl_eur,
                pnl_pct=pnl_pct.quantize(Decimal("0.01")),
                asset_type=p.asset_type,
                sector=p.sector,
                country=p.country,
            )
        )
        total_eur += value_eur

    # Add weight %
    for r in results:
        if total_eur > 0:
            r.weight_pct = (r.value_eur / total_eur * 100).quantize(Decimal("0.01"))

    return results, total_eur


def compute_net_worth(
    accounts: list[dict],
    portfolio_total_eur: Decimal,
    real_estate: list[dict] | None = None,
    rates: dict[str, Decimal] | None = None,
) -> NetWorth:
    """
    Compute total net worth from all sources.

    Args:
        accounts: list of {name, type, balance, currency, institution, is_pro}
        portfolio_total_eur: total portfolio value in EUR
        real_estate: optional list of {estimated_value, loan_remaining}
        rates: FX rates for conversion
    """
    rates = rates or {"EUR": Decimal("1")}
    real_estate = real_estate or []

    cash = Decimal("0")
    savings = Decimal("0")
    loans = Decimal("0")
    by_institution: dict[str, Decimal] = {}
    by_currency: dict[str, Decimal] = {}

    for acc in accounts:
        balance = Decimal(str(acc.get("balance", 0)))
        currency = acc.get("currency", "EUR")
        balance_eur = _to_eur(balance, currency, rates)
        institution = acc.get("institution", "unknown")
        acc_type = acc.get("type", "checking")

        if acc_type in ("checking", "savings"):
            if acc_type == "savings":
                savings += balance_eur
            else:
                cash += balance_eur
        elif acc_type == "loan":
            loans += abs(balance_eur)

        by_institution[institution] = by_institution.get(institution, Decimal("0")) + balance_eur
        by_currency[currency] = by_currency.get(currency, Decimal("0")) + balance_eur

    # Real estate
    re_value = Decimal("0")
    re_loans = Decimal("0")
    for prop in real_estate:
        re_value += Decimal(str(prop.get("estimated_value", 0)))
        re_loans += Decimal(str(prop.get("loan_remaining", 0)))

    total_assets = cash + savings + portfolio_total_eur + re_value
    total_liabilities = loans + re_loans

    breakdown = {
        "cash": cash,
        "savings": savings,
        "investments": portfolio_total_eur,
        "real_estate": re_value,
    }

    return NetWorth(
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=total_assets - total_liabilities,
        breakdown=breakdown,
        by_institution=by_institution,
        by_currency=by_currency,
    )


def _to_eur(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Convert an amount to EUR using ECB rates."""
    if currency == "EUR":
        return amount
    rate = rates.get(currency, Decimal("1"))
    if rate == 0:
        return amount
    return (amount / rate).quantize(Decimal("0.01"))
