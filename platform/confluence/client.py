"""
Confluence REST API client for Server/Data Center.
PAT auth, CRUD pages, attachment upload.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_PAT_PATH = Path.home() / ".config" / "factory" / "confluence.key"

# Confluence Server base
CONFLUENCE_BASE = "https://wiki.net.extra.laposte.fr/confluence"
SPACE_KEY = "IAN"
HOMEPAGE_ID = "1330822346"  # Accueil IA NATIVE


def _load_pat() -> str:
    """Load PAT from config file."""
    if _PAT_PATH.exists():
        return _PAT_PATH.read_text().strip()
    raise FileNotFoundError(f"Confluence PAT not found at {_PAT_PATH}")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_load_pat()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _api(path: str) -> str:
    return f"{CONFLUENCE_BASE}/rest/api{path}"


class ConfluenceClient:
    """Sync client for Confluence Server REST API."""

    def __init__(self, base_url: str = CONFLUENCE_BASE, space_key: str = SPACE_KEY):
        self.base_url = base_url.rstrip("/")
        self.space_key = space_key
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _api(self, path: str) -> str:
        return f"{self.base_url}/rest/api{path}"

    def _headers(self, content_type: str = "application/json") -> dict:
        return {
            "Authorization": f"Bearer {_load_pat()}",
            "Content-Type": content_type,
            "Accept": "application/json",
        }

    # ── Page CRUD ──────────────────────────────────────────────

    def get_page(
        self, page_id: str, expand: str = "body.storage,version"
    ) -> Optional[dict]:
        """Get page by ID."""
        try:
            r = httpx.get(
                self._api(f"/content/{page_id}"),
                params={"expand": expand},
                headers=self._headers(),
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def find_page(self, title: str, space_key: str = None) -> Optional[dict]:
        """Find page by title in space."""
        sk = space_key or self.space_key
        r = httpx.get(
            self._api("/content"),
            params={
                "spaceKey": sk,
                "title": title,
                "expand": "version",
            },
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return results[0] if results else None

    def create_page(
        self, title: str, body_xhtml: str, parent_id: str = None, space_key: str = None
    ) -> dict:
        """Create a new page."""
        sk = space_key or self.space_key
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": sk},
            "body": {
                "storage": {
                    "value": body_xhtml,
                    "representation": "storage",
                }
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        r = httpx.post(
            self._api("/content"),
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        page = r.json()
        log.info("Created page %s: %s", page["id"], title)
        return page

    def update_page(
        self, page_id: str, title: str, body_xhtml: str, version: int = None
    ) -> dict:
        """Update existing page. Increments version automatically."""
        if version is None:
            existing = self.get_page(page_id, expand="version")
            if not existing:
                raise ValueError(f"Page {page_id} not found")
            version = existing["version"]["number"]

        payload = {
            "type": "page",
            "title": title,
            "version": {"number": version + 1},
            "body": {
                "storage": {
                    "value": body_xhtml,
                    "representation": "storage",
                }
            },
        }
        r = httpx.put(
            self._api(f"/content/{page_id}"),
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        log.info("Updated page %s v%d: %s", page_id, version + 1, title)
        return r.json()

    def create_or_update(
        self, title: str, body_xhtml: str, parent_id: str = None
    ) -> dict:
        """Idempotent: update if exists, create if not."""
        existing = self.find_page(title)
        if existing:
            return self.update_page(
                existing["id"], title, body_xhtml, existing["version"]["number"]
            )
        return self.create_page(title, body_xhtml, parent_id)

    def get_children(self, page_id: str) -> list[dict]:
        """List child pages."""
        r = httpx.get(
            self._api(f"/content/{page_id}/child/page"),
            params={"limit": 100},
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("results", [])

    # ── Attachments ────────────────────────────────────────────

    def upload_attachment(
        self,
        page_id: str,
        filename: str,
        data: bytes,
        content_type: str = "image/svg+xml",
    ) -> dict:
        """Upload or update attachment on a page."""
        headers = {
            "Authorization": f"Bearer {_load_pat()}",
            "X-Atlassian-Token": "nocheck",
        }
        files = {"file": (filename, data, content_type)}
        r = httpx.post(
            self._api(f"/content/{page_id}/child/attachment"),
            headers=headers,
            files=files,
            timeout=self.timeout,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        log.info("Uploaded attachment %s to page %s", filename, page_id)
        return results[0] if results else {}

    # ── Utility ────────────────────────────────────────────────

    def ensure_page_hierarchy(self, *titles: str, root_id: str = HOMEPAGE_ID) -> str:
        """Ensure a chain of pages exists (e.g. PROJETS / Macaron / Epic).
        Returns the ID of the deepest page."""
        parent_id = root_id
        for title in titles:
            existing = self.find_page(title)
            if existing:
                parent_id = existing["id"]
            else:
                page = self.create_page(title, "<p></p>", parent_id)
                parent_id = page["id"]
        return parent_id

    def search_cql(
        self, cql: str, limit: int = 10, expand: str = "body.storage,ancestors"
    ) -> list[dict]:
        """Search using CQL query."""
        try:
            r = httpx.get(
                self._api("/content/search"),
                params={"cql": cql, "limit": limit, "expand": expand},
                headers=self._headers(),
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            log.warning("CQL search failed: %s", e)
            return []

    def health_check(self) -> bool:
        """Check API connectivity."""
        try:
            r = httpx.get(
                self._api(f"/space/{self.space_key}"),
                headers=self._headers(),
                timeout=httpx.Timeout(10.0),
            )
            return r.status_code == 200
        except Exception:
            return False


# Singleton
_client: Optional[ConfluenceClient] = None


def get_confluence_client() -> ConfluenceClient:
    global _client
    if _client is None:
        _client = ConfluenceClient()
    return _client
