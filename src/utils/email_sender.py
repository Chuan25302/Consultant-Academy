"""
Email sender via Gmail SMTP.
Reads sender/password/recipients from env vars set in GitHub Secrets.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_daily_email(subject: str, html_body: str) -> bool:
    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_APP_PASSWORD", "")
    recipients_raw = os.getenv("EMAIL_RECIPIENTS", "")
    reply_to = os.getenv("EMAIL_REPLY_TO", "").strip()

    if not all([sender, password, recipients_raw]):
        logger.info("📧 Email skipped — EMAIL_SENDER/APP_PASSWORD/RECIPIENTS not set")
        return False

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender, password)
            smtp.sendmail(sender, recipients, msg.as_bytes())
        logger.info(f"📧 Email sent to {len(recipients)} recipients")
        return True
    except Exception as e:
        logger.error(f"📧 Email failed: {e}")
        return False
