"""Notification service — Email, Slack, and webhook notifications for mission events.

Plugs into the ReactionEngine to send notifications on mission lifecycle events.
Configure via environment variables:
  NOTIFY_SLACK_WEBHOOK=https://hooks.slack.com/services/...
  NOTIFY_EMAIL_SMTP_HOST=smtp.gmail.com
  NOTIFY_EMAIL_SMTP_PORT=587
  NOTIFY_EMAIL_FROM=noreply@example.com
  NOTIFY_EMAIL_PASSWORD=...
  NOTIFY_EMAIL_TO=team@example.com
  NOTIFY_WEBHOOK_URL=https://your-server.com/webhook
"""
import asyncio
import json
import logging
import os
import smtplib
from dataclasses import dataclass
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


class NotificationService:
    """Sends notifications via Slack, email, and/or webhook."""

    def __init__(self):
        self.slack_webhook = os.environ.get("NOTIFY_SLACK_WEBHOOK", "")
        self.webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL", "")
        self.email_host = os.environ.get("NOTIFY_EMAIL_SMTP_HOST", "")
        self.email_port = int(os.environ.get("NOTIFY_EMAIL_SMTP_PORT", "587"))
        self.email_from = os.environ.get("NOTIFY_EMAIL_FROM", "")
        self.email_password = os.environ.get("NOTIFY_EMAIL_PASSWORD", "")
        self.email_to = os.environ.get("NOTIFY_EMAIL_TO", "")

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
    def is_configured(self) -> bool:
        return self.has_slack or self.has_email or self.has_webhook

    async def notify(self, payload: NotificationPayload):
        """Send notification through all configured channels."""
        tasks = []
        if self.has_slack:
            tasks.append(self._send_slack(payload))
        if self.has_email:
            tasks.append(self._send_email(payload))
        if self.has_webhook:
            tasks.append(self._send_webhook(payload))
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
                "footer": "Macaron Software Factory",
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
        <p style="color:#aaa;font-size:12px">Macaron Software Factory</p>
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


# Singleton
_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
