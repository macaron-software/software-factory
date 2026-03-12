"""
AWS SES email sender for password reset codes.

Config via env vars:
    AWS_SES_REGION        — AWS region (default: eu-west-1)
    AWS_SES_FROM_EMAIL    — verified sender (default: noreply@macaron-software.com)
    AWS_ACCESS_KEY_ID     — AWS credentials (or use IAM role)
    AWS_SECRET_ACCESS_KEY — AWS credentials (or use IAM role)
"""

import logging
import os

logger = logging.getLogger(__name__)

SES_REGION = os.environ.get("AWS_SES_REGION", "eu-west-1")
SES_FROM = os.environ.get("AWS_SES_FROM_EMAIL", "noreply@macaron-software.com")


def send_reset_code(to_email: str, code: str) -> bool:
    """Send password reset code via AWS SES. Returns True on success."""
    try:
        import boto3
    except ImportError:
        logger.error("boto3 not installed — cannot send email")
        return False

    subject = "Software Factory — Password Reset Code"
    body_text = (
        f"Your password reset code is: {code}\n\n"
        "This code expires in 15 minutes.\n"
        "If you did not request this, ignore this email."
    )
    body_html = (
        '<div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:2rem">'
        '<h2 style="color:#e6edf3;margin:0 0 1rem">Password Reset</h2>'
        f'<p style="color:#8b949e">Your verification code is:</p>'
        f'<div style="font-size:2rem;font-weight:700;letter-spacing:0.3em;color:#58a6ff;'
        f'background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem;'
        f'text-align:center;margin:1rem 0">{code}</div>'
        '<p style="color:#8b949e;font-size:0.875rem">This code expires in 15 minutes.</p>'
        '<p style="color:#484f58;font-size:0.8125rem;margin-top:2rem">'
        "If you did not request this, you can safely ignore this email.</p>"
        "</div>"
    )

    try:
        client = boto3.client("ses", region_name=SES_REGION)
        client.send_email(
            Source=SES_FROM,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("Reset code sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("SES send_email failed for %s: %s", to_email, e)
        return False
