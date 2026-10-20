"""Optional email delivery.

If SMTP settings are not configured the service logs instead of sending —
the application never depends on an external paid provider for basic operation.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from backend.app.core.config import settings

logger = logging.getLogger("mpis.email")


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.email_from_address)


def send_email(*, to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True if sent, False if logged-only."""
    if not email_configured():
        logger.info("[email:disabled] to=%s subject=%s", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = settings.email_from_address
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    logger.info("[email:sent] to=%s subject=%s", to, subject)
    return True
