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

    # Default model for all agents. Override per-agent with
    # GEMINI_MODEL_<AGENT> env vars (RESEARCH | EXPERT | INDUSTRY |
    # TRANSLATOR | RECAP). Any model the google-genai SDK accepts.
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    MAX_TOKENS_PER_AGENT: int = 2000
    RESEARCH_CACHE_TTL_DAYS: int = 7

    TZ = ZoneInfo("Asia/Bangkok")

    @classmethod
    def model_for(cls, agent_tag: str) -> str:
        """Resolve model for a given agent. Env override > default."""
        env_key = f"GEMINI_MODEL_{agent_tag.upper()}"
        return os.getenv(env_key) or os.getenv("GEMINI_MODEL") or cls.GEMINI_MODEL


def now_bangkok() -> datetime:
    return datetime.now(Settings.TZ)
