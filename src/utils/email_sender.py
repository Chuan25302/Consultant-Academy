"""
Email sender via Gmail SMTP.
Reads sender/password/recipients from env vars set in GitHub Secrets.

Supports inline + attached images via MIME multipart/related: pass
`attachments=[(filename, bytes, content_id), ...]` to send_daily_email
and the email body's <img src="cid:CONTENT_ID"> references will resolve
in Gmail / Outlook / Apple Mail. The attachment also shows up in the
recipient's attachment list, so the file is downloadable.
"""
import logging
import mimetypes
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _attach_part(filename: str, data: bytes, content_id: str | None):
    """Build a MIME attachment part. Uses MIMEImage for image/* so
    inline rendering via cid works correctly; falls back to a generic
    MIMEBase for everything else."""
    mime_type, _ = mimetypes.guess_type(filename)
    mime_type = mime_type or "application/octet-stream"
    main_type, sub_type = mime_type.split("/", 1)

    if main_type == "image":
        part = MIMEImage(data, _subtype=sub_type)
    else:
        part = MIMEBase(main_type, sub_type)
        part.set_payload(data)
        encoders.encode_base64(part)

    part.add_header(
        "Content-Disposition", "attachment", filename=filename,
    )
    if content_id:
        # Angle brackets are required by RFC 2392 for the cid: scheme.
        part.add_header("Content-ID", f"<{content_id}>")
    return part


def send_daily_email(subject: str, html_body: str,
                     attachments: list | None = None) -> bool:
    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_APP_PASSWORD", "")
    recipients_raw = os.getenv("EMAIL_RECIPIENTS", "")
    reply_to = os.getenv("EMAIL_REPLY_TO", "").strip()

    if not all([sender, password, recipients_raw]):
        logger.info("📧 Email skipped — EMAIL_SENDER/APP_PASSWORD/RECIPIENTS not set")
        return False

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    # multipart/related so cid: image references resolve, with an inner
    # multipart/alternative for the HTML body (and future plain-text
    # fallback). This is the standard Gmail/Outlook-compatible shape
    # for "HTML email with inline + attached images".
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    if reply_to:
        msg["Reply-To"] = reply_to

    body_alt = MIMEMultipart("alternative")
    body_alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body_alt)

    for filename, data, content_id in attachments or []:
        if not data:
            continue
        try:
            msg.attach(_attach_part(filename, data, content_id))
        except Exception as e:
            logger.warning(f"📧 Could not attach {filename}: {e}")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender, password)
            smtp.sendmail(sender, recipients, msg.as_bytes())
        logger.info(
            f"📧 Email sent to {len(recipients)} recipients "
            f"({len(attachments or [])} attachments)"
        )
        return True
    except Exception as e:
        logger.error(f"📧 Email failed: {e}")
        return False
