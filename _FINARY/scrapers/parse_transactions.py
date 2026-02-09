"""Parse all bank transaction data into unified DuckDB tables.

Sources:
- IBKR Activity Statements 2024+2025 (CSV)
- Boursobank export (CSV, ; separator)
- Trade Republic transactions (raw text)
"""

import csv
import io
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import duckdb

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "transactions.duckdb"


def init_db(con: duckdb.DuckDBPyConnection):
    """Create tables."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS ibkr_trades (
            date TIMESTAMP,
            symbol VARCHAR,
            asset_class VARCHAR,
            currency VARCHAR,
            quantity DOUBLE,
            price DOUBLE,
            proceeds DOUBLE,
            commission DOUBLE,
            realized_pnl DOUBLE,
            codes VARCHAR,
            year INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ibkr_dividends (
            date DATE,
            symbol VARCHAR,
            isin VARCHAR,
            currency VARCHAR,
            description VARCHAR,
            amount DOUBLE,
            year INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ibkr_interest (
            date DATE,
            currency VARCHAR,
            description VARCHAR,
            amount DOUBLE,
            year INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ibkr_fees (
            date DATE,
            currency VARCHAR,
            description VARCHAR,
            amount DOUBLE,
            year INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS budget_transactions (
            date DATE,
            amount DOUBLE,
            description VARCHAR,
            category VARCHAR,
            category_parent VARCHAR,
            merchant VARCHAR,
            bank VARCHAR,
            account VARCHAR,
            type VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ibkr_summary (
            year INTEGER,
            total_commissions DOUBLE,
            total_interest_debit DOUBLE,
            total_interest_credit DOUBLE,
            total_dividends DOUBLE,
            total_fees DOUBLE,
            total_realized_pnl DOUBLE,
            trade_count INTEGER
        )
    """)


def parse_ibkr_csv(filepath: Path, year: int, con: duckdb.DuckDBPyConnection):
    """Parse IBKR Activity Statement CSV."""
    print(f"\n{'='*60}")
    print(f"Parsing IBKR {year}: {filepath.name}")

    text = filepath.read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    trades = []
    dividends = []
    interests = []
    fees = []
    total_commissions = 0.0
    total_realized_pnl = 0.0

    for row in rows:
        if len(row) < 3:
            continue

        section = row[0]
        data_type = row[1]

        # TRADES (Transactions section)
        if section == "Transactions" and data_type == "Data" and row[2] == "Order":
            try:
                asset_class = row[3]
                currency = row[4]
                symbol = row[5]
                dt_str = row[6].strip('"')
                quantity = float(row[7])
                price = float(row[8])
                proceeds = float(row[10])
                commission = float(row[11])
                realized_pnl = float(row[13]) if row[13] else 0.0
                codes = row[15] if len(row) > 15 else ""

                dt = datetime.strptime(dt_str, "%Y-%m-%d, %H:%M:%S")

                trades.append((dt, symbol, asset_class, currency, quantity, price,
                               proceeds, commission, realized_pnl, codes, year))
                total_commissions += commission
                total_realized_pnl += realized_pnl
            except (ValueError, IndexError) as e:
                pass  # Skip malformed rows

        # DIVIDENDS
        elif section == "Dividendes" and data_type == "Data" and row[2] not in ("Total", "Total en EUR", "Total Dividendes en EUR"):
            try:
                currency = row[2]
                dt = datetime.strptime(row[3], "%Y-%m-%d").date()
                desc = row[4]
                amount = float(row[5])
                # Extract ISIN from description
                isin_match = re.search(r'\(([A-Z]{2}\w+)\)', desc)
                isin = isin_match.group(1) if isin_match else ""
                # Extract symbol
                sym_match = re.match(r'(\w+)\(', desc)
                sym = sym_match.group(1) if sym_match else ""

                dividends.append((dt, sym, isin, currency, desc, amount, year))
            except (ValueError, IndexError):
                pass

        # INTEREST
        elif section == "Intérêt" and data_type == "Data" and len(row) >= 6:
            try:
                if row[2] in ("Total", "Total en EUR", "Total Intérêt en EUR"):
                    continue
                currency = row[2]
                dt = datetime.strptime(row[3], "%Y-%m-%d").date()
                desc = row[4]
                amount = float(row[5])
                interests.append((dt, currency, desc, amount, year))
            except (ValueError, IndexError):
                pass

        # FEES (Frais)
        elif section == "Frais" and data_type == "Data":
            try:
                if row[2] in ("Total", "Total en EUR"):
                    continue
                currency = row[3]
                dt = datetime.strptime(row[4], "%Y-%m-%d").date()
                desc = row[5]
                amount = float(row[6])
                fees.append((dt, currency, desc, amount, year))
            except (ValueError, IndexError):
                pass

    # Insert into DB
    con.execute("DELETE FROM ibkr_trades WHERE year = ?", [year])
    con.execute("DELETE FROM ibkr_dividends WHERE year = ?", [year])
    con.execute("DELETE FROM ibkr_interest WHERE year = ?", [year])
    con.execute("DELETE FROM ibkr_fees WHERE year = ?", [year])
    con.execute("DELETE FROM ibkr_summary WHERE year = ?", [year])

    if trades:
        con.executemany("INSERT INTO ibkr_trades VALUES (?,?,?,?,?,?,?,?,?,?,?)", trades)
    if dividends:
        con.executemany("INSERT INTO ibkr_dividends VALUES (?,?,?,?,?,?,?)", dividends)
    if interests:
        con.executemany("INSERT INTO ibkr_interest VALUES (?,?,?,?,?)", interests)
    if fees:
        con.executemany("INSERT INTO ibkr_fees VALUES (?,?,?,?,?)", fees)

    # Compute summary
    interest_debit = sum(a for _, _, _, a, _ in interests if a < 0)
    interest_credit = sum(a for _, _, _, a, _ in interests if a > 0)
    total_dividends = sum(a for _, _, _, _, _, a, _ in dividends)
    total_fees = sum(a for _, _, _, a, _ in fees)

    con.execute("INSERT INTO ibkr_summary VALUES (?,?,?,?,?,?,?,?)",
                [year, total_commissions, interest_debit, interest_credit,
                 total_dividends, total_fees, total_realized_pnl, len(trades)])

    print(f"  Trades: {len(trades)}")
    print(f"  Commissions: {total_commissions:,.2f}")
    print(f"  Realized P&L: {total_realized_pnl:,.2f}")
    print(f"  Dividends: {len(dividends)} entries, {total_dividends:,.2f}")
    print(f"  Interest debit: {interest_debit:,.2f}, credit: {interest_credit:,.2f}")
    print(f"  Fees: {len(fees)} entries, {total_fees:,.2f}")


def parse_bourso_csv(filepath: Path, con: duckdb.DuckDBPyConnection):
    """Parse Boursobank CSV export."""
    print(f"\n{'='*60}")
    print(f"Parsing Boursobank: {filepath.name}")

    text = filepath.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")

    txns = []
    for row in reader:
        try:
            dt = datetime.strptime(row["dateOp"], "%Y-%m-%d").date()
            amount_str = row["amount"].replace(",", ".").replace("\xa0", "")
            amount = float(amount_str)
            desc = row["label"].strip('"')
            category = row.get("category", "")
            cat_parent = row.get("categoryParent", "")
            merchant = row.get("supplierFound", "")
            account = row.get("accountLabel", "")

            # Determine type
            if amount > 0:
                tx_type = "income"
            elif "virement" in category.lower():
                tx_type = "transfer"
            else:
                tx_type = "expense"

            txns.append((dt, amount, desc, category, cat_parent, merchant,
                         "boursobank", account, tx_type))
        except (ValueError, KeyError) as e:
            pass

    # Only insert Bourso data (delete old)
    con.execute("DELETE FROM budget_transactions WHERE bank = 'boursobank'")
    if txns:
        con.executemany("INSERT INTO budget_transactions VALUES (?,?,?,?,?,?,?,?,?)", txns)

    print(f"  Transactions: {len(txns)}")
    if txns:
        dates = [t[0] for t in txns]
        print(f"  Period: {min(dates)} → {max(dates)}")
        expenses = sum(t[1] for t in txns if t[8] == "expense")
        income = sum(t[1] for t in txns if t[8] == "income")
        print(f"  Total expenses: {expenses:,.2f}€")
        print(f"  Total income: {income:,.2f}€")


# Category mapping for Trade Republic merchants
TR_CATEGORIES = {
    "carrefour": "Alimentation",
    "lidl": "Alimentation",
    "auchan": "Alimentation",
    "intermarche": "Alimentation",
    "monoprix": "Alimentation",
    "picard": "Alimentation",
    "leclerc": "Alimentation",
    "bio": "Alimentation",
    "boulangerie": "Alimentation",
    "amazon": "Shopping",
    "aliexpress": "Shopping",
    "shein": "Shopping",
    "temu": "Shopping",
    "ikea": "Shopping",
    "decathlon": "Shopping",
    "action": "Shopping",
    "burger king": "Restauration",
    "mcdonalds": "Restauration",
    "mcdonald": "Restauration",
    "kfc": "Restauration",
    "domino": "Restauration",
    "subway": "Restauration",
    "uber eats": "Restauration",
    "deliveroo": "Restauration",
    "sncf": "Transport",
    "ratp": "Transport",
    "uber": "Transport",
    "bolt": "Transport",
    "total": "Transport",
    "shell": "Transport",
    "bp ": "Transport",
    "netflix": "Abonnements",
    "spotify": "Abonnements",
    "disney": "Abonnements",
    "apple": "Abonnements",
    "google": "Abonnements",
    "pharmacie": "Santé",
    "doctolib": "Santé",
}


def categorize_tr(merchant: str) -> str:
    """Map TR merchant to category."""
    ml = merchant.lower()
    for key, cat in TR_CATEGORIES.items():
        if key in ml:
            return cat
    return "Autre"


def parse_tr_text(filepath: Path, con: duckdb.DuckDBPyConnection):
    """Parse Trade Republic transactions raw text.

    Format: merchant\\n\\nDD/MM[ - Status]\\n\\n€amount
    Month headers: "January 2025", "February 2026" etc.
    """
    print(f"\n{'='*60}")
    print(f"Parsing Trade Republic: {filepath.name}")

    text = filepath.read_text()
    lines = text.split("\n")

    txns = []
    current_year = 2026
    current_month_num = 2  # Default: Feb 2026

    MONTH_NAMES = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }

    # Find "This month" header to know where transactions start
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == "This month":
            start_idx = i + 1
            break

    i = start_idx
    while i < len(lines):
        line = lines[i].strip()

        # Month header
        month_match = re.match(
            r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})$",
            line
        )
        if month_match:
            current_month_num = MONTH_NAMES[month_match.group(1)]
            current_year = int(month_match.group(2))
            i += 1
            continue

        # Skip empty / nav lines
        if not line or line in ("Skip to content", "Search", "Wealth", "Orders", "Profile",
                                "S", "Transactions", "Activity", "Cash", "Deposit", "Withdraw",
                                "This month"):
            i += 1
            continue

        # Amount line (€XX.XX or X,XXX.XX €)
        if line.startswith("€") or re.match(r"^\d[\d,.]*\s*€$", line):
            i += 1
            continue

        # Try to parse as: merchant (this line), date (next non-empty), amount (next non-empty after that)
        merchant = line

        # Find date line
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            break

        date_line = lines[j].strip()
        date_match = re.match(r"(\d{2}/\d{2})\s*(?:-\s*(.+))?$", date_line)

        if not date_match:
            i += 1
            continue

        dd_mm = date_match.group(1)
        status = (date_match.group(2) or "").strip()

        # Find amount line
        k = j + 1
        while k < len(lines) and not lines[k].strip():
            k += 1
        if k >= len(lines):
            break

        amount_line = lines[k].strip()
        # Parse €XX.XX or XX,XXX.XX€
        amt_match = re.match(r"€\s*([\d,.]+)", amount_line) or re.match(r"([\d,.]+)\s*€", amount_line)
        if not amt_match:
            i += 1
            continue

        amount_str = amt_match.group(1).replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            i = k + 1
            continue

        # Build date
        day_str, month_str = dd_mm.split("/")
        try:
            dt = date(current_year, current_month_num, int(day_str))
        except ValueError:
            dt = date(current_year, current_month_num, 1)

        # Skip cancelled
        if "cancelled" in status.lower():
            i = k + 1
            continue

        # Classify
        desc_lower = merchant.lower()
        if "saving" in desc_lower or "round up" in status.lower():
            tx_type = "savings"
            category = "Épargne"
        elif "interest" in desc_lower:
            tx_type = "income"
            category = "Revenus financiers"
        elif "sent" in status.lower():
            tx_type = "transfer"
            category = "Virements"
            amount = -amount
        elif "received" in status.lower():
            tx_type = "transfer"
            category = "Virements"
        else:
            # Card purchase (expense)
            tx_type = "expense"
            category = categorize_tr(merchant)
            amount = -amount  # expenses negative

        txns.append((dt, amount, merchant, category, "", merchant,
                     "trade_republic", "TR Card", tx_type))
        i = k + 1

    # Delete old TR data
    con.execute("DELETE FROM budget_transactions WHERE bank = 'trade_republic'")
    if txns:
        con.executemany("INSERT INTO budget_transactions VALUES (?,?,?,?,?,?,?,?,?)", txns)

    print(f"  Transactions parsed: {len(txns)}")
    if txns:
        dates = [t[0] for t in txns]
        print(f"  Period: {min(dates)} → {max(dates)}")
        expenses = sum(t[1] for t in txns if t[8] == "expense")
        print(f"  Total expenses: {expenses:,.2f}€")


def print_summary(con: duckdb.DuckDBPyConnection):
    """Print full summary."""
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    # IBKR summary
    rows = con.execute("SELECT * FROM ibkr_summary ORDER BY year").fetchall()
    for row in rows:
        yr, comm, int_d, int_c, divs, fees_t, pnl, cnt = row
        print(f"\nIBKR {yr}:")
        print(f"  Trades: {cnt}, Commissions: {comm:,.2f}€")
        print(f"  Interest: {int_d:,.2f}€ (debit) + {int_c:,.2f}€ (credit)")
        print(f"  Dividends: {divs:,.2f}€")
        print(f"  Data fees: {fees_t:,.2f}€")
        print(f"  Realized P&L: {pnl:,.2f}€")

    # Top traded symbols
    for year in [2024, 2025]:
        print(f"\nIBKR {year} Top Symbols:")
        syms = con.execute("""
            SELECT symbol, COUNT(*) as cnt, SUM(commission) as comm, SUM(realized_pnl) as pnl
            FROM ibkr_trades WHERE year = ?
            GROUP BY symbol ORDER BY cnt DESC LIMIT 10
        """, [year]).fetchall()
        for sym, cnt, comm, pnl in syms:
            print(f"  {sym:8s} {cnt:4d} trades, comm={comm:8.2f}, P&L={pnl:8.2f}")

    # Budget summary
    print(f"\nBudget Transactions:")
    banks = con.execute("""
        SELECT bank, COUNT(*), MIN(date), MAX(date), SUM(CASE WHEN type='expense' THEN amount ELSE 0 END)
        FROM budget_transactions GROUP BY bank
    """).fetchall()
    for bank, cnt, mn, mx, exp in banks:
        print(f"  {bank}: {cnt} txns ({mn} → {mx}), expenses: {exp:,.2f}€")

    # Top categories
    print(f"\nTop Budget Categories (expenses):")
    cats = con.execute("""
        SELECT category, COUNT(*), SUM(amount)
        FROM budget_transactions WHERE type = 'expense'
        GROUP BY category ORDER BY SUM(amount) ASC LIMIT 15
    """).fetchall()
    for cat, cnt, total in cats:
        print(f"  {cat:30s} {cnt:4d} txns  {total:10,.2f}€")

    # Monthly totals
    print(f"\nMonthly Budget (last 6 months):")
    months = con.execute("""
        SELECT strftime(date, '%Y-%m') as m,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as exp,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as inc
        FROM budget_transactions
        GROUP BY m ORDER BY m DESC LIMIT 6
    """).fetchall()
    for m, exp, inc in months:
        print(f"  {m}: expenses={exp:8,.2f}€  income={inc:8,.2f}€  net={exp+inc:8,.2f}€")


def main():
    con = duckdb.connect(str(DB_PATH))
    init_db(con)

    # Parse IBKR statements
    for year, fname in [(2024, "ibkr_activity_2024.csv"), (2025, "ibkr_activity_2025.csv")]:
        f = DATA_DIR / fname
        if f.exists():
            parse_ibkr_csv(f, year, con)

    # Parse Boursobank
    bourso = DATA_DIR / "bourso_export.csv"
    if bourso.exists():
        parse_bourso_csv(bourso, con)

    # Parse Trade Republic
    tr = DATA_DIR / "tr_transactions_raw.txt"
    if tr.exists():
        parse_tr_text(tr, con)

    print_summary(con)
    con.close()
    print(f"\n✅ Database saved: {DB_PATH}")


if __name__ == "__main__":
    main()
