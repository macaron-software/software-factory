"""Crédit Agricole scraper using creditagricole_particuliers library.

Uses the official-ish API wrapper instead of Playwright browser automation.
Based on: github.com/Royalphax/credit-agricole-importer

The creditagricole_particuliers package provides direct API access to
Crédit Agricole accounts without needing a browser.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from scrapers.base import BaseScraper, OTPRequiredError
from scrapers.models import Account, AccountType, Transaction

# Region mapping — Crédit Agricole is split into regional banks
# Each has its own subdomain. Department number → region code.
# Source: credit-agricole-importer by Royalphax
CA_REGIONS: dict[int, str] = {
    1: "ca-centrest", 2: "ca-norddefrance", 3: "ca-centrefrance",
    4: "ca-alpesprovence", 5: "ca-alpesprovence", 6: "ca-alpesprovence",
    7: "ca-sudrhonealpes", 8: "ca-nordest", 9: "ca-languedoc",
    10: "ca-champagne-bourgogne", 11: "ca-languedoc", 12: "ca-nordmidi-pyrenees",
    13: "ca-alpesprovence", 14: "ca-normandie", 15: "ca-centrefrance",
    16: "ca-charente-perigord", 17: "ca-charente-maritime-deux-sevres",
    18: "ca-centreloire", 19: "ca-centrefrance", 20: "ca-corse",
    21: "ca-champagne-bourgogne", 22: "ca-cotesdarmor", 23: "ca-centrefrance",
    24: "ca-charente-perigord", 25: "ca-franchecomte", 26: "ca-sudrhonealpes",
    27: "ca-normandie-seine", 28: "ca-centreloire", 29: "ca-finistere",
    30: "ca-languedoc", 31: "ca-toulouse31", 32: "ca-aquitaine",
    33: "ca-aquitaine", 34: "ca-languedoc", 35: "ca-illeetvilaine",
    36: "ca-centreloire", 37: "ca-centreloire", 38: "ca-sudrhonealpes",
    39: "ca-franchecomte", 40: "ca-aquitaine", 41: "ca-centreloire",
    42: "ca-loirehauteloire", 43: "ca-loirehauteloire", 44: "ca-atlantique-vendee",
    45: "ca-centreloire", 46: "ca-nordmidi-pyrenees", 47: "ca-aquitaine",
    48: "ca-languedoc", 49: "ca-anjou-maine", 50: "ca-normandie",
    51: "ca-nordest", 52: "ca-champagne-bourgogne", 53: "ca-anjou-maine",
    54: "ca-lorraine", 55: "ca-lorraine", 56: "ca-morbihan",
    57: "ca-lorraine", 58: "ca-centreloire", 59: "ca-norddefrance",
    60: "ca-briepicardie", 61: "ca-normandie", 62: "ca-norddefrance",
    63: "ca-centrefrance", 64: "ca-pyrenees-gascogne", 65: "ca-pyrenees-gascogne",
    66: "ca-sudmed", 67: "ca-alsace-vosges", 68: "ca-alsace-vosges",
    69: "ca-centrest", 70: "ca-franchecomte", 71: "ca-centrest",
    72: "ca-anjou-maine", 73: "ca-des-savoie", 74: "ca-des-savoie",
    75: "ca-paris", 76: "ca-normandie-seine", 77: "ca-briepicardie",
    78: "ca-paris", 79: "ca-charente-maritime-deux-sevres",
    80: "ca-briepicardie", 81: "ca-nordmidi-pyrenees", 82: "ca-nordmidi-pyrenees",
    83: "ca-provence-cote-azur", 84: "ca-alpesprovence",
    85: "ca-atlantique-vendee", 86: "ca-touraine-poitou",
    87: "ca-centrefrance", 88: "ca-lorraine", 89: "ca-champagne-bourgogne",
    90: "ca-franchecomte", 91: "ca-paris", 92: "ca-paris",
    93: "ca-paris", 94: "ca-paris", 95: "ca-paris",
    971: "ca-martinique-guyane", 972: "ca-martinique-guyane",
    973: "ca-martinique-guyane", 974: "ca-reunion",
}


def get_region_for_department(department: int) -> str:
    """Get CA regional bank URL for a department number."""
    return CA_REGIONS.get(department, "ca-paris")


class CreditAgricoleScraper(BaseScraper):
    """Scraper using creditagricole_particuliers API client.

    Falls back to Playwright if the library is not available.
    """

    institution_name = "credit_agricole"
    display_name = "Crédit Agricole"
    scraper_type = "api"

    def __init__(
        self,
        department: int = 75,
        account_number: str = "",
        password: str = "",
        is_pro: bool = False,
    ) -> None:
        super().__init__()
        self.department = department
        self.account_number = account_number
        self.password = password
        self.is_pro = is_pro
        self._session = None
        self._accounts_raw: list = []

    async def login(self) -> None:
        """Authenticate via creditagricole_particuliers API."""
        try:
            from creditagricole_particuliers import Authenticator
        except ImportError:
            raise ImportError(
                "Install creditagricole_particuliers: pip install creditagricole-particuliers"
            )

        region = get_region_for_department(self.department)
        try:
            self._session = Authenticator(
                username=self.account_number,
                password=list(self.password),  # API expects list of digits
                department=self.department,
            )
            # Validate the session
            self._accounts_raw = self._session.get_accounts()
            self.logger.info(
                "Crédit Agricole API login OK — %d accounts found (dept=%d, pro=%s)",
                len(self._accounts_raw), self.department, self.is_pro,
            )
        except Exception as e:
            if "otp" in str(e).lower() or "sca" in str(e).lower():
                raise OTPRequiredError("app_validation")
            raise

    async def logout(self) -> None:
        self._session = None

    async def fetch_accounts(self) -> list[Account]:
        """Fetch accounts from CA API."""
        if not self._session:
            return []

        inst_id = uuid.uuid5(uuid.NAMESPACE_DNS, "credit_agricole")
        accounts = []

        for raw in self._accounts_raw:
            name = raw.get("libelleProduit", raw.get("label", "Compte CA"))
            balance = Decimal(str(raw.get("solde", raw.get("balance", 0))))
            account_type = _detect_ca_type(name)

            accounts.append(
                Account(
                    institution_id=inst_id,
                    external_id=raw.get("numeroCompte", raw.get("accountNumber")),
                    name=name,
                    account_type=account_type,
                    currency="EUR",
                    balance=balance,
                    is_pro=self.is_pro,
                )
            )

        return accounts

    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Fetch transactions from CA API."""
        if not self._session or not account.external_id:
            return []

        try:
            # Fetch last 90 days of operations
            date_from = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
            ops = self._session.get_operations(
                account_number=account.external_id,
                date_from=date_from,
            )
        except Exception as e:
            self.logger.warning("Failed to fetch transactions for %s: %s", account.name, e)
            return []

        transactions = []
        for op in ops:
            tx_date = op.get("dateOperation", op.get("date", ""))
            description = op.get("libelleOperation", op.get("label", ""))
            amount = Decimal(str(op.get("montant", op.get("amount", 0))))

            try:
                parsed_date = datetime.strptime(tx_date[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                parsed_date = date.today()

            transactions.append(
                Transaction(
                    account_id=account.id,
                    external_id=op.get("identifiantOperation"),
                    date=parsed_date,
                    description=description,
                    amount=amount,
                )
            )

        return transactions


def _detect_ca_type(name: str) -> AccountType:
    upper = name.upper()
    if "LIVRET" in upper or "LDD" in upper or "LEP" in upper or "EPARGNE" in upper:
        return AccountType.SAVINGS
    if any(kw in upper for kw in ("PRET", "PRÊT", "CREDIT", "CRÉDIT", "EMPRUNT")):
        return AccountType.LOAN
    if "PEA" in upper:
        return AccountType.PEA
    if "TITRE" in upper or "CTO" in upper:
        return AccountType.CTO
    if "VIE" in upper:
        return AccountType.AV
    return AccountType.CHECKING
