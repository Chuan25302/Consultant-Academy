import os
from datetime import datetime
from zoneinfo import ZoneInfo


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json"
    )
    GOOGLE_OAUTH_TOKEN_FILE: str = os.getenv(
        "GOOGLE_OAUTH_TOKEN_FILE", "oauth-token.json"
    )

    # Vertex AI — ถ้าตั้งค่า VERTEX_AI_PROJECT จะใช้ Vertex แทน API Key
    VERTEX_AI_PROJECT: str = os.getenv("VERTEX_AI_PROJECT", "")
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    VERTEX_AI_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "VERTEX_AI_SERVICE_ACCOUNT_FILE", "vertex-ai-service-key.json"
    )

    @property
    def use_vertex(self) -> bool:
        return bool(self.VERTEX_AI_PROJECT)

    CALENDAR_FILE_ID: str = os.getenv("CALENDAR_FILE_ID", "")
    FOLDER_EMAIL_ARCHIVES: str = os.getenv("FOLDER_EMAIL_ARCHIVES", "")
    FOLDER_KNOWLEDGE_BASE: str = os.getenv("FOLDER_KNOWLEDGE_BASE", "")
    FOLDER_PROGRAM_MGMT: str = os.getenv("FOLDER_PROGRAM_MGMT", "")
    # Optional: Drive folder for AI-generated infographics. When set,
    # ImageAgent uploads each rendered PNG here organized by month.
    # Leave empty to disable image generation entirely.
    FOLDER_IMAGES: str = os.getenv("FOLDER_IMAGES", "")

    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # KM site base URL (e.g. https://chuan25302.github.io/Consultant-Academy).
    # When set, email footer shows "อ่านบนเว็บ" + "คลังความรู้" buttons that
    # link into the static site. Leave empty to disable both buttons —
    # pipeline behavior is unchanged.
    SITE_BASE_URL: str = os.getenv("SITE_BASE_URL", "").rstrip("/")

    # Default model for all agents. Override per-agent with
    # GEMINI_MODEL_<AGENT> env vars (RESEARCH | EXPERT | INDUSTRY |
    # TRANSLATOR | RECAP). Any model the google-genai SDK accepts.
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    MAX_TOKENS_PER_AGENT: int = 2000  # legacy fallback when agent_tag unknown

    # Per-agent output budgets. Sized to the prompt's word target +
    # markdown overhead. Thai SentencePiece runs ~1.0–1.3 tok/char so
    # a 600-word article (~1.8k chars) plus headers, glossary, related
    # section comfortably fits in 4000.
    MAX_TOKENS = {
        "research":     2500,
        "expert":       3500,
        "industry":     2000,
        "factchecker":  5000,  # rewrites translator output (now 5 sections + KC)
        "translator":   5000,  # +1 section (Knowledge Capture) over base 4000
        "editor":       5000,
        "recap":        3500,  # deep extraction of Mon–Fri bodies → 4-section output
        "planner":      6000,
        # image_brief intentionally removed — ImageAgent now passes the
        # full article straight to Gemini Flash Image (32k-token window),
        # so a separate text-only brief generator is no longer needed.
    }

    RESEARCH_CACHE_TTL_DAYS: int = 7

    TZ = ZoneInfo("Asia/Bangkok")

    @classmethod
    def model_for(cls, agent_tag: str) -> str:
        """Resolve model for a given agent. Env override > default."""
        env_key = f"GEMINI_MODEL_{agent_tag.upper()}"
        return os.getenv(env_key) or os.getenv("GEMINI_MODEL") or cls.GEMINI_MODEL

    @classmethod
    def tokens_for(cls, agent_tag: str) -> int:
        return cls.MAX_TOKENS.get(agent_tag.lower(), cls.MAX_TOKENS_PER_AGENT)


def now_bangkok() -> datetime:
    return datetime.now(Settings.TZ)
