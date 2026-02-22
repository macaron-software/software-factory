"""i18n — Lightweight internationalization for the Macaron platform.

Usage in Jinja2 templates:  {{ _('key') }}  or  {{ _('key', name='World') }}
Usage in Python:            from platform.i18n import t; t('key', lang='en')
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "fr", "zh", "es", "ja", "pt", "de", "ko")

# In-memory catalog: {"en": {"key": "value"}, "fr": {"key": "valeur"}}
_catalog: dict[str, dict[str, str]] = {}


def _load_catalog() -> None:
    """Load all locale JSON files into memory."""
    global _catalog
    _catalog = {}
    for lang in SUPPORTED_LANGS:
        fpath = LOCALES_DIR / f"{lang}.json"
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                _catalog[lang] = json.load(f)
            log.info("i18n: loaded %d keys for '%s'", len(_catalog[lang]), lang)
        else:
            _catalog[lang] = {}
            log.warning("i18n: missing locale file %s", fpath)


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    """Translate a key. Falls back to English, then to the key itself."""
    if not _catalog:
        _load_catalog()
    text = _catalog.get(lang, {}).get(key)
    if text is None and lang != DEFAULT_LANG:
        text = _catalog.get(DEFAULT_LANG, {}).get(key)
    if text is None:
        return key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def get_lang(request) -> str:
    """Detect language from request: cookie > Accept-Language > default."""
    # 1. Cookie
    cookie_lang = request.cookies.get("lang")
    if cookie_lang in SUPPORTED_LANGS:
        return cookie_lang
    # 2. Accept-Language header
    accept = request.headers.get("accept-language", "")
    for part in accept.split(","):
        code = part.strip().split(";")[0].strip()[:2].lower()
        if code in SUPPORTED_LANGS:
            return code
    return DEFAULT_LANG


def reload_catalog() -> None:
    """Force reload translations (e.g., after editing locale files)."""
    _load_catalog()


# Pre-load on import
_load_catalog()
