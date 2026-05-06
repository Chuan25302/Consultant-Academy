"""
Local 7-day cache for research data.
Cache hit = zero API cost for same topic within 7 days.
"""
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
CACHE_DIR = Path("data/research_cache")


class ResearchCache:
    def __init__(self, ttl_days: int = 7):
        self.ttl = timedelta(days=ttl_days)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _key(self, topic: str, industry: str = None) -> str:
        raw = f"{topic.lower()}:{(industry or 'general').lower()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, topic: str, industry: str = None) -> dict | None:
        f = CACHE_DIR / f"{self._key(topic, industry)}.json"
        if not f.exists():
            return None
        age = datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)
        if age > self.ttl:
            return None
        data = json.loads(f.read_text(encoding="utf-8"))
        logger.info(f"💾 Cache hit: '{topic}' (saved API call)")
        return data.get("research")

    def set(self, topic: str, research: dict, industry: str = None):
        f = CACHE_DIR / f"{self._key(topic, industry)}.json"
        f.write_text(json.dumps({
            "topic": topic, "industry": industry,
            "cached_at": datetime.now().isoformat(),
            "research": research
        }, ensure_ascii=False, indent=2), encoding="utf-8")
