"""Notification service — Email, Slack, Webhook, WhatsApp, and Browser Push notifications.

Configure via environment variables:
  NOTIFY_SLACK_WEBHOOK=https://hooks.slack.com/services/...
  NOTIFY_EMAIL_SMTP_HOST=smtp.gmail.com
  NOTIFY_EMAIL_SMTP_PORT=587
  NOTIFY_EMAIL_FROM=noreply@example.com
  NOTIFY_EMAIL_PASSWORD=...
  NOTIFY_EMAIL_TO=team@example.com
  NOTIFY_WEBHOOK_URL=https://your-server.com/webhook
  NOTIFY_TWILIO_ACCOUNT_SID=ACxxxxx
  NOTIFY_TWILIO_AUTH_TOKEN=xxxxx
  NOTIFY_TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
  NOTIFY_WHATSAPP_TO=whatsapp:+33612345678  (comma-separated)
  NOTIFY_VAPID_PUBLIC_KEY=...  (base64url, for browser push)
  NOTIFY_VAPID_PRIVATE_KEY=... (base64url PEM)
  NOTIFY_VAPID_EMAIL=admin@example.com
"""
import asyncio
import json
import logging
import os
import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    event: str
    title: str
    message: str
    project_id: str = ""
    mission_id: str = ""
    severity: str = "info"  # info, warning, critical
    url: str = ""


@dataclass
class PushSubscription:
    endpoint: str
    keys: dict = field(default_factory=dict)  # auth + p256dh


class NotificationService:
    """Sends notifications via Slack, email, webhook, WhatsApp (Twilio), and Browser Push."""

    def __init__(self):
        self.slack_webhook = os.environ.get("NOTIFY_SLACK_WEBHOOK", "")
        self.webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL", "")
        self.email_host = os.environ.get("NOTIFY_EMAIL_SMTP_HOST", "")
        self.email_port = int(os.environ.get("NOTIFY_EMAIL_SMTP_PORT", "587"))
        self.email_from = os.environ.get("NOTIFY_EMAIL_FROM", "")
        self.email_password = os.environ.get("NOTIFY_EMAIL_PASSWORD", "")
        self.email_to = os.environ.get("NOTIFY_EMAIL_TO", "")
        # Twilio WhatsApp
        self.twilio_sid = os.environ.get("NOTIFY_TWILIO_ACCOUNT_SID", "")
        self.twilio_token = os.environ.get("NOTIFY_TWILIO_AUTH_TOKEN", "")
        self.twilio_from = os.environ.get("NOTIFY_TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.whatsapp_to = [
            t.strip() for t in os.environ.get("NOTIFY_WHATSAPP_TO", "").split(",") if t.strip()
        ]
        # Browser Web Push (VAPID)
        self.vapid_public = os.environ.get("NOTIFY_VAPID_PUBLIC_KEY", "")
        self.vapid_private = os.environ.get("NOTIFY_VAPID_PRIVATE_KEY", "")
        self.vapid_email = os.environ.get("NOTIFY_VAPID_EMAIL", "admin@macaron-software.com")
        # In-memory push subscriptions (persisted to SQLite separately)
        self._push_subscriptions: list[dict] = []

    @property
    def has_slack(self) -> bool:
        return bool(self.slack_webhook)

    @property
    def has_email(self) -> bool:
        return bool(self.email_host and self.email_from and self.email_to)

    @property
    def has_webhook(self) -> bool:
        return bool(self.webhook_url)

    @property
    def has_whatsapp(self) -> bool:
        return bool(self.twilio_sid and self.twilio_token and self.whatsapp_to)

    @property
    def has_browser_push(self) -> bool:
        return bool(self.vapid_public and self.vapid_private)

    @property
    def is_configured(self) -> bool:
        return self.has_slack or self.has_email or self.has_webhook or self.has_whatsapp or self.has_browser_push

    def add_push_subscription(self, subscription: dict) -> None:
        """Register a browser push subscription."""
        endpoint = subscription.get("endpoint", "")
        # Replace existing subscription for same endpoint
        self._push_subscriptions = [s for s in self._push_subscriptions if s.get("endpoint") != endpoint]
        self._push_subscriptions.append(subscription)
        logger.info("Browser push subscription added: %s…", endpoint[:60])

    def remove_push_subscription(self, endpoint: str) -> None:
        self._push_subscriptions = [s for s in self._push_subscriptions if s.get("endpoint") != endpoint]

    def load_push_subscriptions(self, subscriptions: list[dict]) -> None:
        """Load persisted subscriptions from DB on startup."""
        self._push_subscriptions = subscriptions

    async def notify(self, payload: NotificationPayload):
        """Send notification through all configured channels."""
        tasks = []
        if self.has_slack:
            tasks.append(self._send_slack(payload))
        if self.has_email:
            tasks.append(self._send_email(payload))
        if self.has_webhook:
            tasks.append(self._send_webhook(payload))
        if self.has_whatsapp:
            tasks.append(self._send_whatsapp(payload))
        if self.has_browser_push and self._push_subscriptions:
            tasks.append(self._send_browser_push(payload))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error("Notification error: %s", r)

    async def _send_slack(self, payload: NotificationPayload):
        """Post to Slack incoming webhook."""
        color_map = {"info": "#36a64f", "warning": "#ff9900", "critical": "#ff0000"}
        color = color_map.get(payload.severity, "#36a64f")
        slack_msg = {
            "attachments": [{
                "color": color,
                "title": payload.title,
                "text": payload.message,
                "fields": [
                    {"title": "Event", "value": payload.event, "short": True},
                    {"title": "Project", "value": payload.project_id or "—", "short": True},
                ],
                "footer": "Software Factory",
            }]
        }
        if payload.url:
            slack_msg["attachments"][0]["title_link"] = payload.url
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(self.slack_webhook, json=slack_msg)
            r.raise_for_status()
            logger.info("Slack notification sent: %s", payload.title)

    async def _send_email(self, payload: NotificationPayload):
        """Send email via SMTP (runs in thread to avoid blocking)."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Macaron] {payload.title}"
        msg["From"] = self.email_from
        msg["To"] = self.email_to

        text = f"{payload.title}\n\n{payload.message}\n\nEvent: {payload.event}\nProject: {payload.project_id}\nMission: {payload.mission_id}"
        html = f"""<div style="font-family:sans-serif;max-width:600px">
        <h2 style="color:#7c3aed">{payload.title}</h2>
        <p>{payload.message}</p>
        <table style="margin-top:12px">
        <tr><td style="color:#888">Event</td><td>{payload.event}</td></tr>
        <tr><td style="color:#888">Project</td><td>{payload.project_id or '—'}</td></tr>
        <tr><td style="color:#888">Mission</td><td>{payload.mission_id or '—'}</td></tr>
        </table>
        {f'<p><a href="{payload.url}" style="color:#7c3aed">View in Macaron</a></p>' if payload.url else ''}
        <hr style="margin-top:20px;border:none;border-top:1px solid #eee">
        <p style="color:#aaa;font-size:12px">Software Factory</p>
        </div>"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._smtp_send, msg)
        logger.info("Email notification sent to %s: %s", self.email_to, payload.title)

    def _smtp_send(self, msg: MIMEMultipart):
        with smtplib.SMTP(self.email_host, self.email_port) as server:
            server.starttls()
            if self.email_password:
                server.login(self.email_from, self.email_password)
            server.send_message(msg)

    async def _send_webhook(self, payload: NotificationPayload):
        """POST to a custom webhook URL."""
        data = {
            "event": payload.event,
            "title": payload.title,
            "message": payload.message,
            "project_id": payload.project_id,
            "mission_id": payload.mission_id,
            "severity": payload.severity,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(self.webhook_url, json=data)
            r.raise_for_status()
            logger.info("Webhook notification sent: %s", payload.title)

    async def _send_whatsapp(self, payload: NotificationPayload):
        """Send WhatsApp message via Twilio API."""
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(payload.severity, "📋")
        body = f"{icon} *{payload.title}*\n{payload.message}"
        if payload.project_id:
            body += f"\n_Projet: {payload.project_id}_"
        if payload.url:
            body += f"\n{payload.url}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
        async with httpx.AsyncClient(timeout=15) as client:
            for to in self.whatsapp_to:
                r = await client.post(
                    url,
                    auth=(self.twilio_sid, self.twilio_token),
                    data={"From": self.twilio_from, "To": to, "Body": body},
                )
                if r.status_code not in (200, 201):
                    raise Exception(f"Twilio WhatsApp error {r.status_code}: {r.text[:200]}")
                logger.info("WhatsApp notification sent to %s: %s", to, payload.title)

    async def _send_browser_push(self, payload: NotificationPayload):
        """Send Web Push notification to all registered browser subscriptions."""
        try:
            from pywebpush import webpush, WebPushException
            import base64
        except ImportError:
            logger.warning("pywebpush not installed — browser push skipped")
            return

        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(payload.severity, "📋")
        data = json.dumps({
            "title": payload.title,
            "body": payload.message,
            "icon": "/static/img/icon-192.png",
            "badge": "/static/img/badge-72.png",
            "tag": payload.event,
            "url": payload.url or "/",
            "severity": payload.severity,
        })

        # Decode private key (base64url-encoded PEM)
        try:
            private_pem = base64.urlsafe_b64decode(self.vapid_private + "==").decode()
        except Exception:
            private_pem = self.vapid_private  # already PEM

        failed = []
        for sub in list(self._push_subscriptions):
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda s=sub: webpush(
                        subscription_info=s,
                        data=data,
                        vapid_private_key=private_pem,
                        vapid_claims={"sub": f"mailto:{self.vapid_email}"},
                    ),
                )
                logger.debug("Browser push sent to %s…", sub.get("endpoint", "")[:50])
            except Exception as e:
                logger.warning("Browser push failed for %s: %s", sub.get("endpoint", "")[:50], e)
                # Remove expired/gone subscriptions (410 = unsubscribed)
                if "410" in str(e) or "404" in str(e):
                    failed.append(sub.get("endpoint", ""))

        for ep in failed:
            self.remove_push_subscription(ep)
        if failed:
            logger.info("Removed %d expired push subscriptions", len(failed))


# Singleton
_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
