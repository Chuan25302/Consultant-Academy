import os
from datetime import datetime
from zoneinfo import ZoneInfo


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json"
    )

    CALENDAR_FILE_ID: str = os.getenv("CALENDAR_FILE_ID", "")
    FOLDER_EMAIL_ARCHIVES: str = os.getenv("FOLDER_EMAIL_ARCHIVES", "")
    FOLDER_KNOWLEDGE_BASE: str = os.getenv("FOLDER_KNOWLEDGE_BASE", "")
    FOLDER_PROGRAM_MGMT: str = os.getenv("FOLDER_PROGRAM_MGMT", "")

    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    GEMINI_MODEL: str = "gemini-2.0-flash"
    MAX_TOKENS_PER_AGENT: int = 2000
    RESEARCH_CACHE_TTL_DAYS: int = 7

    TZ = ZoneInfo("Asia/Bangkok")


def now_bangkok() -> datetime:
    return datetime.now(Settings.TZ)
