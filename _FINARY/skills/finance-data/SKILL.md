---
name: finance-data
description: Financial data modeling, calculations, and transaction categorization for personal wealth management. Use when working on database schema, P&L calculations, asset allocation, dividend tracking, net worth computation, or automatic transaction categorization with regex rules and LLM fallback.
---

# Finance Data

Modèles de données, calculs financiers et catégorisation pour gestion patrimoniale.

## Schéma DB

Voir `specs.md` section 3 pour le schéma complet. Points clés :

- **DECIMAL(15,2)** pour les montants (centimes)
- **DECIMAL(15,6)** pour les quantités (fractions d'actions)
- **DECIMAL(15,4)** pour les prix (précision cours)
- **UUID** pour toutes les PK (pas d'auto-increment)
- **TIMESTAMPTZ** pour tous les timestamps (UTC)
- **JSONB** pour les breakdowns flexibles (net worth par classe)

## Catégorisation Transactions

### Règles Regex (priorité haute → basse)

```python
CATEGORY_RULES = [
    # Revenus
    (r"(?i)virement.*salaire|paie|salary", "salary"),
    (r"(?i)dividende|dividend|coupon", "dividends"),
    (r"(?i)remboursement|refund", "refund"),
    (r"(?i)loyer.*recu|rent.*received", "rental_income"),
    
    # Logement
    (r"(?i)loyer|rent(?!.*car)", "rent"),
    (r"(?i)edf|engie|electricite|gaz|energy", "utilities"),
    (r"(?i)eau|water|veolia|suez", "utilities"),
    (r"(?i)orange|sfr|bouygues|free(?!.*lance)|internet|mobile", "telecom"),
    (r"(?i)assurance|maif|macif|axa|insurance", "insurance"),
    
    # Alimentation
    (r"(?i)carrefour|leclerc|auchan|lidl|monoprix|casino|inter\s?march", "groceries"),
    (r"(?i)deliveroo|uber\s?eats|just\s?eat", "food_delivery"),
    (r"(?i)restaurant|brasserie|pizz|sushi|burger", "restaurant"),
    
    # Transport
    (r"(?i)sncf|tgv|train|ratp|metro|navigo", "transport"),
    (r"(?i)uber(?!\s?eats)|taxi|bolt|blabla", "taxi"),
    (r"(?i)total\s?energies|station|essence|diesel|fuel", "fuel"),
    (r"(?i)parking|stationnement", "parking"),
    
    # Abonnements
    (r"(?i)netflix|spotify|disney|amazon\s?prime|canal\+|dazn", "subscriptions"),
    (r"(?i)apple|google\s?play|app\s?store", "subscriptions"),
    (r"(?i)gym|fitness|basic\s?fit|sport", "fitness"),
    
    # Santé
    (r"(?i)pharmacie|pharmacy|medecin|docteur|doctor", "health"),
    (r"(?i)mutuelle|cpam|ameli|remboursement.*soin", "health"),
    
    # Épargne & Investissement
    (r"(?i)virement.*livret|livret\s?a|ldds|pel", "savings"),
    (r"(?i)virement.*pea|cto|bourse", "investment"),
    
    # Shopping
    (r"(?i)amazon(?!\s?prime)|fnac|darty|ikea|zara|h&m", "shopping"),
    (r"(?i)aliexpress|shein|zalando", "shopping"),
]

def categorize(description: str, rules: list) -> str | None:
    for pattern, category in rules:
        if re.search(pattern, description):
            return category
    return None  # fallback LLM si None
```

### Fallback LLM (pour transactions ambiguës)

```python
async def categorize_with_llm(description: str, amount: float) -> str:
    """Catégorisation LLM pour transactions non matchées par regex."""
    prompt = f"""Catégorise cette transaction bancaire française.
Transaction: "{description}" | Montant: {amount}€

Catégories possibles: salary, dividends, rent, utilities, telecom, insurance,
groceries, restaurant, food_delivery, transport, taxi, fuel, subscriptions,
health, savings, investment, shopping, leisure, education, gifts, taxes, other

Réponds UNIQUEMENT avec le nom de la catégorie."""
    # Appel LLM (minimax ou local)
    ...
```

## Calculs Net Worth

```python
def compute_networth(accounts, positions, real_estate):
    assets = {
        "cash": sum(a.balance for a in accounts if a.account_type in ('checking', 'savings')),
        "stocks": sum(p.quantity * p.current_price for p in positions if p.asset_type == 'stock'),
        "etf": sum(p.quantity * p.current_price for p in positions if p.asset_type == 'etf'),
        "crypto": sum(p.quantity * p.current_price for p in positions if p.asset_type == 'crypto'),
        "bonds": sum(p.quantity * p.current_price for p in positions if p.asset_type == 'bond'),
        "real_estate": sum(r.estimated_value for r in real_estate),
    }
    liabilities = {
        "loans": sum(a.balance for a in accounts if a.account_type == 'loan'),
        "mortgages": sum(r.loan_remaining for r in real_estate if r.loan_remaining),
    }
    return {
        "total_assets": sum(assets.values()),
        "total_liabilities": sum(liabilities.values()),
        "net_worth": sum(assets.values()) - sum(liabilities.values()),
        "breakdown": {**assets, **liabilities},
    }
```

## Conversion Devises

```python
# Taux ECB (European Central Bank) — mis à jour quotidiennement
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

async def get_exchange_rates() -> dict[str, Decimal]:
    """Récupère les taux EUR→X depuis la BCE."""
    # Parse XML, retourne {"USD": 1.08, "GBP": 0.86, ...}
    ...

def convert_to_eur(amount: Decimal, currency: str, rates: dict) -> Decimal:
    if currency == "EUR":
        return amount
    rate = rates.get(currency)
    if rate:
        return amount / rate
    raise ValueError(f"Unknown currency: {currency}")
```

## Allocation Analysis

```python
def compute_allocation(positions, dimension: str = "sector"):
    """Calcule la répartition par dimension (sector, country, currency, asset_type)."""
    total = sum(p.quantity * p.current_price for p in positions)
    if total == 0:
        return []
    
    buckets = defaultdict(Decimal)
    for p in positions:
        value = p.quantity * p.current_price
        key = getattr(p, dimension, "unknown")
        buckets[key] += value
    
    return [
        {"name": k, "value": float(v), "pct": float(v / total * 100)}
        for k, v in sorted(buckets.items(), key=lambda x: -x[1])
    ]
```
