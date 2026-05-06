"""Helpers for main.py — kept in a separate module so they can be unit-tested
without importing the heavy Drive/Gemini SDKs."""
import logging
from datetime import datetime

from src.config.settings import Settings

logger = logging.getLogger(__name__)


def parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD into a Bangkok-tz-aware datetime."""
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=Settings.TZ)


def validate_startup(s: Settings, drive) -> None:
    """Fail fast if any required Drive ID is missing or inaccessible.

    `drive` must expose .check_access(id) -> (ok, info_or_error).
    """
    targets = [
        ("CALENDAR_FILE_ID",       s.CALENDAR_FILE_ID),
        ("FOLDER_EMAIL_ARCHIVES",  s.FOLDER_EMAIL_ARCHIVES),
        ("FOLDER_KNOWLEDGE_BASE",  s.FOLDER_KNOWLEDGE_BASE),
        ("FOLDER_PROGRAM_MGMT",    s.FOLDER_PROGRAM_MGMT),
    ]
    errors = []
    for name, val in targets:
        ok, info = drive.check_access(val)
        if ok:
            logger.info(f"  ✓ {name} → {info}")
        else:
            errors.append(f"  ✗ {name}={val!r}: {info}")
    if errors:
        raise RuntimeError(
            "Startup validation failed — fix env vars and/or share "
            "folders with the service account email:\n" + "\n".join(errors)
        )
