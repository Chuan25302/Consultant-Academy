import os


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    GOOGLE_TOKEN_FILE: str = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    CALENDAR_FILE_ID: str = os.getenv("CALENDAR_FILE_ID", "")
    FOLDER_EMAIL_ARCHIVES: str = os.getenv("FOLDER_EMAIL_ARCHIVES", "")
    FOLDER_KNOWLEDGE_BASE: str = os.getenv("FOLDER_KNOWLEDGE_BASE", "")
    FOLDER_PROGRAM_MGMT: str = os.getenv("FOLDER_PROGRAM_MGMT", "")

    GEMINI_MODEL: str = "gemini-2.0-flash"
    MAX_TOKENS_PER_AGENT: int = 2000
    RESEARCH_CACHE_TTL_DAYS: int = 7
