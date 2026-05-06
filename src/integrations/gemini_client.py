"""
Gemini Flash client using new google-genai SDK.
gemini-2.0-flash = $0.075/1M tokens (200x cheaper than Claude Opus)
"""
import json
import re
import logging
from google import genai
from google.genai import types
from src.config.settings import Settings

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings):
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model = settings.GEMINI_MODEL
        self.max_tokens = settings.MAX_TOKENS_PER_AGENT
        logger.info(f"✅ Gemini initialized ({self.model})")

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens or self.max_tokens,
                    temperature=0.7
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return f"[Error: {e}]"

    def generate_json(self, prompt: str) -> dict:
        raw = self.generate(prompt + "\n\nReturn ONLY valid JSON. No markdown fences.", max_tokens=1500)
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed — returning empty dict")
            return {}
