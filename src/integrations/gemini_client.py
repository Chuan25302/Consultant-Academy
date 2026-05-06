"""
Gemini Flash client using new google-genai SDK.
Auto-tracks real token usage via cost_tracker (when provided).
"""
import json
import re
import logging
from typing import Optional

from google import genai
from google.genai import types

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings, cost_tracker=None):
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model = settings.GEMINI_MODEL
        self.max_tokens = settings.MAX_TOKENS_PER_AGENT
        self.cost_tracker = cost_tracker
        logger.info(f"✅ Gemini initialized ({self.model})")

    def generate(self, prompt: str, max_tokens: Optional[int] = None,
                 agent_tag: str = "unknown") -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens or self.max_tokens,
                    temperature=0.7,
                ),
            )
            self._track(response, agent_tag)
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini error ({agent_tag}): {e}")
            return f"[Error: {e}]"

    def generate_json(self, prompt: str, agent_tag: str = "unknown") -> dict:
        raw = self.generate(
            prompt + "\n\nReturn ONLY valid JSON. No markdown fences.",
            max_tokens=1500, agent_tag=agent_tag,
        )
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        # Strip stray prose before/after JSON object
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"JSON parse failed ({agent_tag}) — returning empty dict")
            return {}

    def _track(self, response, agent_tag: str):
        if not self.cost_tracker:
            return
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", 0) if usage else 0
        if tokens:
            self.cost_tracker.log("gemini-flash", agent_tag, tokens)
