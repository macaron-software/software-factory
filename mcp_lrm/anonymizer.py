"""
Anonymizer — Regex-based PII stripping for RLM content.
Inspired by PSY/LiACT anonymization (RGPD Art. 25 Privacy by Design).

Strips: names, emails, phones, SSN, addresses, postal codes, IPs, URLs with tokens.
Consistent replacement mapping per session (same entity → same placeholder).
No LLM dependency — pure regex + dictionaries.
"""

import re
from collections import defaultdict
from typing import Optional


# French first names (top 100 most common)
_FRENCH_FIRST_NAMES = {
    "jean", "pierre", "marie", "jacques", "philippe", "michel", "alain", "claude",
    "bernard", "christiane", "sylvie", "nathalie", "isabelle", "catherine", "nicole",
    "dominique", "patrick", "daniel", "franck", "olivier", "nicolas", "stéphane",
    "thierry", "laurent", "eric", "david", "thomas", "julien", "alexandre", "sylvain",
    "maxime", "antoine", "hugo", "lucas", "gabriel", "louis", "arthur", "léo",
    "emma", "jade", "louise", "alice", "chloé", "lina", "mila", "léa", "manon",
    "camille", "sarah", "laura", "julie", "marine", "aurélie", "sophie", "anna",
    "mathieu", "vincent", "romain", "guillaume", "sébastien", "jérôme", "frédéric",
    "pascal", "rené", "henri", "charles", "paul", "françois", "yves", "robert",
    "andré", "christian", "gérard", "roger", "marcel", "serge", "denis",
    "nadia", "patricia", "sandrine", "véronique", "christine", "monique",
    "valérie", "brigitte", "anne", "florence", "hélène", "martine", "cécile",
    "virginie", "delphine", "caroline", "emilie", "claire", "margaux",
}

# Common French last names (top 80)
_FRENCH_LAST_NAMES = {
    "martin", "bernard", "thomas", "petit", "robert", "richard", "durand", "dubois",
    "moreau", "laurent", "simon", "michel", "lefebvre", "leroy", "roux", "david",
    "bertrand", "morel", "fournier", "girard", "bonnet", "dupont", "lambert",
    "fontaine", "rousseau", "vincent", "muller", "lefevre", "faure", "andre",
    "mercier", "blanc", "guerin", "boyer", "garnier", "chevalier", "francois",
    "legrand", "gauthier", "garcia", "perrin", "robin", "clement", "morin",
    "nicolas", "henry", "roussel", "mathieu", "gautier", "masson", "marchand",
    "duval", "denis", "dumont", "marie", "lemaire", "noel", "meyer", "dufour",
    "meunier", "brun", "blanchard", "giraud", "joly", "riviere", "lucas",
    "brunet", "gaillard", "barbier", "arnaud", "martinez", "gerard", "roche",
    "renault", "schmitt", "roy", "leroux", "colin", "vidal", "caron", "picard",
}


class Anonymizer:
    """Regex-based PII anonymizer with consistent replacements."""

    def __init__(self):
        self._mapping: dict[str, str] = {}  # original → replacement
        self._counters: dict[str, int] = defaultdict(int)
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile all detection regex patterns."""
        # French phone numbers: 06 12 34 56 78, 01-23-45-67-89, +33 6 12 34 56 78
        self._re_phone = re.compile(
            r'(?:\+33\s?[1-9]|0[1-9])(?:[\s.\-]?\d{2}){4}'
        )
        # Email addresses
        self._re_email = re.compile(
            r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
        )
        # French SSN: 1 85 05 78 006 084 23
        self._re_ssn = re.compile(
            r'\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}(?:\s?\d{2})?\b'
        )
        # IP addresses
        self._re_ip = re.compile(
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        )
        # URLs with tokens/keys (api keys, tokens in query params)
        self._re_url_token = re.compile(
            r'(?:token|key|secret|password|api_key|apikey|auth)=\S+',
            re.IGNORECASE
        )
        # Bearer tokens
        self._re_bearer = re.compile(
            r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
            re.IGNORECASE
        )
        # API keys (long hex/base64 strings that look like keys)
        self._re_api_key = re.compile(
            r'\b(?:sk-|gsk_|xox[bpas]-|ghp_|glpat-)[A-Za-z0-9\-._]{20,}\b'
        )
        # French postal codes (5 digits, context-aware)
        self._re_postal = re.compile(
            r'\b(?:(?:75|77|78|91|92|93|94|95)\d{3}|(?:[0-9]{2}[0-9]{3}))\b'
        )
        # Street addresses (number + rue/avenue/boulevard)
        self._re_address = re.compile(
            r'\b\d{1,4}[\s,]+(?:rue|avenue|boulevard|place|impasse|chemin|allée|passage|cours|quai)\b[^,\n]{3,50}',
            re.IGNORECASE
        )
        # Capitalized names (2+ capitalized words in sequence — likely person names)
        self._re_cap_names = re.compile(
            r'\b([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)+)\b'
        )

    def _get_replacement(self, entity_type: str, original: str) -> str:
        """Get or create a consistent replacement for an entity."""
        key = f"{entity_type}:{original.lower().strip()}"
        if key in self._mapping:
            return self._mapping[key]
        self._counters[entity_type] += 1
        n = self._counters[entity_type]
        replacements = {
            "phone": f"[TEL-{n:03d}]",
            "email": f"[EMAIL-{n:03d}]",
            "ssn": "[SSN-XXX]",
            "ip": f"[IP-{n:03d}]",
            "token": "[TOKEN-REDACTED]",
            "api_key": "[API-KEY-REDACTED]",
            "address": f"[ADRESSE-{n:03d}]",
            "postal": f"[CP-{n:03d}]",
            "person": f"[PERSONNE-{n:03d}]",
            "first_name": f"[PRENOM-{n:03d}]",
            "last_name": f"[NOM-{n:03d}]",
        }
        replacement = replacements.get(entity_type, f"[{entity_type.upper()}-{n:03d}]")
        self._mapping[key] = replacement
        return replacement

    def _is_known_name(self, word: str) -> Optional[str]:
        """Check if a word is a known French name."""
        w = word.lower().strip()
        if w in _FRENCH_FIRST_NAMES:
            return "first_name"
        if w in _FRENCH_LAST_NAMES:
            return "last_name"
        return None

    def anonymize(self, text: str) -> str:
        """Anonymize PII in text. Returns cleaned text."""
        if not text:
            return text

        result = text

        # 1. API keys and bearer tokens (highest priority)
        result = self._re_api_key.sub(
            lambda m: self._get_replacement("api_key", m.group()), result
        )
        result = self._re_bearer.sub(
            lambda m: self._get_replacement("token", m.group()), result
        )
        result = self._re_url_token.sub(
            lambda m: self._get_replacement("token", m.group()), result
        )

        # 2. SSN (before phone to avoid partial matches)
        result = self._re_ssn.sub(
            lambda m: self._get_replacement("ssn", m.group()), result
        )

        # 3. Phone numbers
        result = self._re_phone.sub(
            lambda m: self._get_replacement("phone", m.group()), result
        )

        # 4. Email addresses
        result = self._re_email.sub(
            lambda m: self._get_replacement("email", m.group()), result
        )

        # 5. IP addresses
        result = self._re_ip.sub(
            lambda m: self._get_replacement("ip", m.group()), result
        )

        # 6. Street addresses
        result = self._re_address.sub(
            lambda m: self._get_replacement("address", m.group()), result
        )

        # 7. Known French names (word-level scan)
        words = result.split()
        for i, word in enumerate(words):
            clean = re.sub(r'[^\w\-àâäéèêëïîôùûüÿçœæ]', '', word.lower())
            name_type = self._is_known_name(clean)
            if name_type and len(clean) > 2:
                # Don't anonymize if it's clearly a common word used differently
                # (e.g., "martin" as surname vs "martin-pecheur")
                words[i] = word.replace(
                    re.sub(r'[^\w\-àâäéèêëïîôùûüÿçœæÀ-Ü]', '', word),
                    self._get_replacement(name_type, clean)
                )
        result = " ".join(words)

        return result

    def anonymize_dict(self, data: dict) -> dict:
        """Anonymize string values in a dict recursively."""
        out = {}
        for k, v in data.items():
            if isinstance(v, str):
                out[k] = self.anonymize(v)
            elif isinstance(v, dict):
                out[k] = self.anonymize_dict(v)
            elif isinstance(v, list):
                out[k] = [
                    self.anonymize(item) if isinstance(item, str)
                    else self.anonymize_dict(item) if isinstance(item, dict)
                    else item
                    for item in v
                ]
            else:
                out[k] = v
        return out

    @property
    def stats(self) -> dict:
        """Return anonymization statistics."""
        return {
            "entities_replaced": sum(self._counters.values()),
            "by_type": dict(self._counters),
            "unique_mappings": len(self._mapping),
        }

    def reset(self):
        """Reset mappings (new session)."""
        self._mapping.clear()
        self._counters.clear()


# Singleton per-session
_anonymizer: Optional[Anonymizer] = None


def get_anonymizer() -> Anonymizer:
    """Get or create the session anonymizer."""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = Anonymizer()
    return _anonymizer
