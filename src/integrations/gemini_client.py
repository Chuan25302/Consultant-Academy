"""
Gemini client using new google-genai SDK.
Model is resolved per agent via Settings.model_for(agent_tag), so each
agent can use a different model (e.g. cheap Flash for translator,
high-quality Pro for expert) by setting GEMINI_MODEL_<AGENT> env vars.
Auto-tracks input + output tokens via cost_tracker (per-model pricing).
Transient errors (5xx, rate limits) auto-retry with exponential backoff.
"""
import json
import logging
import re

from google import genai
from google.genai import types

from src.config.settings import Settings
from src.utils.retry import with_retries

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings, cost_tracker=None):
        self.settings = settings
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.max_tokens = settings.MAX_TOKENS_PER_AGENT
        self.cost_tracker = cost_tracker
        logger.info(f"✅ Gemini initialized (default: {settings.GEMINI_MODEL})")

    @with_retries
    def _call_model(self, prompt: str, max_tokens: int, model: str):
        return self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.7,
            ),
        )

    def generate(self, prompt: str, max_tokens: int | None = None,
                 agent_tag: str = "unknown") -> str:
        model = self.settings.model_for(agent_tag)
        try:
            response = self._call_model(prompt, max_tokens or self.max_tokens, model)
            self._track(response, agent_tag, model)
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini error ({agent_tag}, {model}) after retries: {e}")
            return f"[Error: {e}]"

    def generate_json(self, prompt: str, agent_tag: str = "unknown") -> dict:
        raw = self.generate(
            prompt + "\n\nReturn ONLY valid JSON. No markdown fences.",
            max_tokens=1500, agent_tag=agent_tag,
        )
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"JSON parse failed ({agent_tag}) — returning empty dict")
            return {}

    def _track(self, response, agent_tag: str, model: str):
        if not self.cost_tracker:
            return
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return
        in_tokens = getattr(usage, "prompt_token_count", 0) or 0
        out_tokens = getattr(usage, "candidates_token_count", 0) or 0
        if in_tokens or out_tokens:
            self.cost_tracker.log(model, agent_tag, in_tokens, out_tokens)
