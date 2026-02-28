"""Web Push service — VAPID-based browser push notifications.

VAPID keys are auto-generated on first use and stored in the `platform_settings`
table (keys: `vapid_public_key`, `vapid_private_key`, `vapid_email`).
The generated keys are also injected into the process environment so that the
existing :class:`NotificationService` picks them up automatically.

Usage::

    from platform.services.push import send_push, send_push_to_project, broadcast_push
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VAPID key management
# ---------------------------------------------------------------------------


def _get_or_create_vapid_keys() -> tuple[str, str, str]:
    """Return (public_key_b64url, private_key_b64url, email).

    Keys are loaded from env vars first; if absent they are generated and
    persisted in ``platform_settings``.
    """
    pub = os.environ.get("NOTIFY_VAPID_PUBLIC_KEY", "")
    priv = os.environ.get("NOTIFY_VAPID_PRIVATE_KEY", "")
    email = os.environ.get("NOTIFY_VAPID_EMAIL", "admin@macaron-software.com")

    if pub and priv:
        return pub, priv, email

    # Try loading from DB
    try:
        from ..db.migrations import get_db

        db = get_db()
        try:
            db.execute(
                """CREATE TABLE IF NOT EXISTS platform_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now'))
                )"""
            )
            db.commit()
            rows = db.execute(
                "SELECT key, value FROM platform_settings WHERE key IN (?,?,?)",
                ("vapid_public_key", "vapid_private_key", "vapid_email"),
            ).fetchall()
            settings = {r["key"]: r["value"] for r in rows}
            pub = settings.get("vapid_public_key", "")
            priv = settings.get("vapid_private_key", "")
            email = settings.get("vapid_email", email)
        finally:
            db.close()
    except Exception as e:
        logger.warning("push: could not load settings from DB: %s", e)

    if pub and priv:
        os.environ["NOTIFY_VAPID_PUBLIC_KEY"] = pub
        os.environ["NOTIFY_VAPID_PRIVATE_KEY"] = priv
        os.environ["NOTIFY_VAPID_EMAIL"] = email
        return pub, priv, email

    # Generate new VAPID keys
    try:
        from py_vapid import Vapid
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
            PrivateFormat,
            NoEncryption,
        )

        v = Vapid()
        v.generate_keys()
        pub_bytes = v.public_key.public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )
        pub = base64.urlsafe_b64encode(pub_bytes).decode().rstrip("=")
        priv_pem = v.private_key.private_bytes(
            Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
        ).decode()
        priv = base64.urlsafe_b64encode(priv_pem.encode()).decode()
        logger.info("push: generated new VAPID key pair")
    except Exception as e:
        logger.warning(
            "push: pywebpush not available, cannot generate VAPID keys: %s", e
        )
        return "", "", email

    # Persist to DB
    try:
        from ..db.migrations import get_db

        db = get_db()
        try:
            for k, val in [
                ("vapid_public_key", pub),
                ("vapid_private_key", priv),
                ("vapid_email", email),
            ]:
                db.execute(
                    "INSERT OR REPLACE INTO platform_settings (key, value) VALUES (?, ?)",
                    (k, val),
                )
            db.commit()
            logger.info("push: VAPID keys persisted to platform_settings")
        finally:
            db.close()
    except Exception as e:
        logger.warning("push: could not persist VAPID keys: %s", e)

    os.environ["NOTIFY_VAPID_PUBLIC_KEY"] = pub
    os.environ["NOTIFY_VAPID_PRIVATE_KEY"] = priv
    os.environ["NOTIFY_VAPID_EMAIL"] = email
    return pub, priv, email


def get_vapid_public_key() -> str:
    """Return the VAPID public key (base64url), generating if needed."""
    pub, _, _ = _get_or_create_vapid_keys()
    return pub


def ensure_vapid_keys() -> bool:
    """Initialise VAPID keys on startup. Returns True if keys are available."""
    pub, priv, _ = _get_or_create_vapid_keys()
    return bool(pub and priv)


# ---------------------------------------------------------------------------
# Send helpers
# ---------------------------------------------------------------------------


def _build_payload(
    title: str, body: str, url: str = "", icon: str = "/static/icons/icon-192.png"
) -> str:
    return json.dumps(
        {
            "title": title,
            "body": body,
            "icon": icon,
            "url": url or "/",
            "tag": "sf-mission",
        }
    )


async def send_push(
    subscription_info: dict,
    title: str,
    body: str,
    url: str = "",
    icon: str = "/static/icons/icon-192.png",
) -> bool:
    """Send a Web Push notification to a single subscription.

    Returns True on success, False on failure (expired/gone subscriptions are
    silently ignored).
    """
    try:
        from pywebpush import webpush  # noqa: PLC0415
    except ImportError:
        logger.debug("push: pywebpush not installed, skipping")
        return False

    pub, priv, email = _get_or_create_vapid_keys()
    if not (pub and priv):
        return False

    try:
        priv_pem = base64.urlsafe_b64decode(priv + "==").decode()
    except Exception:
        priv_pem = priv  # already PEM

    import asyncio

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: webpush(
                subscription_info=subscription_info,
                data=_build_payload(title, body, url, icon),
                vapid_private_key=priv_pem,
                vapid_claims={"sub": f"mailto:{email}"},
            ),
        )
        return True
    except Exception as exc:
        if "410" in str(exc) or "404" in str(exc):
            # Subscription expired — caller should remove it
            return False
        logger.warning("push: send failed: %s", exc)
        return False


async def send_push_to_project(
    project_id: str,
    title: str,
    body: str,
    url: str = "",
) -> int:
    """Send a push notification to all subscriptions for *project_id*.

    Falls back to broadcasting to all subscriptions when no project-scoped ones
    are found (e.g. subscriptions created before project_id support was added).
    Returns the number of successful sends.
    """
    subs = _load_subscriptions(project_id=project_id)
    if not subs:
        subs = _load_subscriptions()  # fallback: all subscriptions

    sent = 0
    failed_endpoints: list[str] = []
    for sub in subs:
        ok = await send_push(sub, title, body, url)
        if ok:
            sent += 1
        else:
            ep = sub.get("endpoint", "")
            if ep:
                failed_endpoints.append(ep)

    _remove_subscriptions(failed_endpoints)
    return sent


async def broadcast_push(title: str, body: str, url: str = "") -> int:
    """Send a push notification to all active subscriptions.

    Returns the number of successful sends.
    """
    subs = _load_subscriptions()
    sent = 0
    failed_endpoints: list[str] = []
    for sub in subs:
        ok = await send_push(sub, title, body, url)
        if ok:
            sent += 1
        else:
            ep = sub.get("endpoint", "")
            if ep:
                failed_endpoints.append(ep)
    _remove_subscriptions(failed_endpoints)
    return sent


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _load_subscriptions(project_id: Optional[str] = None) -> list[dict]:
    try:
        from ..db.migrations import get_db

        db = get_db()
        try:
            if project_id:
                rows = db.execute(
                    "SELECT subscription_json FROM push_subscriptions WHERE project_id=?",
                    (project_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT subscription_json FROM push_subscriptions"
                ).fetchall()
            return [json.loads(r["subscription_json"]) for r in rows]
        except Exception as e:
            logger.debug("push: load subscriptions: %s", e)
            return []
        finally:
            db.close()
    except Exception as e:
        logger.debug("push: DB unavailable: %s", e)
        return []


def _remove_subscriptions(endpoints: list[str]) -> None:
    if not endpoints:
        return
    try:
        from ..db.migrations import get_db

        db = get_db()
        try:
            for ep in endpoints:
                db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (ep,))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug("push: remove subscriptions: %s", e)
