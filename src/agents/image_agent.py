"""
Image Agent — generates an executive consulting infographic for each
daily article using Vertex AI's Gemini 2.5 Flash Image model.

Two-step flow:
  1. Brief generator (Gemini Flash text model) compresses the full
     article into ~300-word brief that lists the hard facts (numbers,
     ranges, named standards). The brief is the single source of
     truth the image model must respect — no fabricated numbers.
  2. Gemini 2.5 Flash Image renders the infographic from the brief
     plus the full McKinsey-style style template (kept verbatim from
     the original prompt brief because Gemini Image accepts ~32k
     tokens, far above Imagen 4's 480-token cap).

Output is non-blocking: any failure (Vertex not configured, API error,
safety filter trip) returns None and the daily run continues without
an image rather than miss the email entirely.

Cost: ~$0.039/image (Gemini 2.5 Flash Image) plus a tiny brief cost.
"""
import logging

from google import genai
from google.genai import types
from google.oauth2 import service_account

from src.config.settings import Settings
from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
IMAGE_MODEL = "gemini-2.5-flash-image"

# Brief generator — extracts hard facts, no fabrication. Output goes
# straight into the image prompt as the {brief} block.
BRIEF_PROMPT = """สกัดข้อเท็จจริงสำคัญที่สุดจากบทความที่ปรึกษานี้
ให้กลายเป็น visual brief สั้นๆ (≤300 คำ) สำหรับใช้สร้าง infographic

ใส่:
- English headline 1 บรรทัด (คล้าย "Stop Selling Price. Start Selling 10-Year Value.")
- 3 KPI numbers (ใช้ตัวเลขจาก article เท่านั้น ห้ามแต่ง)
- Problem 2-3 จุด, Hidden Cost 2-3 จุด, Solution 2-3 จุด, Business Impact 2-3 จุด
- Consultant Insight (ประโยคไทยสั้นๆ จาก article)
- Key Formula หรือ Rule of Thumb (ถ้ามี)

ห้ามแต่งตัวเลขที่ไม่อยู่ใน article — ถ้า article ใช้ range "25-30%"
brief ต้องใช้ "25-30%" ไม่ใช่ "27%"

Article:
{article}

ตอบเฉพาะ brief text ไม่ใส่ heading หรือ label"""

# Image prompt — full McKinsey/BCG style brief preserved verbatim from
# the original spec. Gemini 2.5 Flash Image accepts the long form.
IMAGE_PROMPT = """Transform this industrial consulting article into a premium executive consulting infographic.

ARTICLE FACTS (use ONLY numbers and statements from below — do NOT invent any percentages, costs, or timelines):
TOPIC: {topic}
INDUSTRY: {industry}
PILLAR: {pillar}

{brief}

Style:
- McKinsey + BCG style business infographic
- Clean and modern consulting presentation
- Dark blue (#0D2F5C) + white + subtle energy green (#1B5E20) palette
- Balanced information density
- Strong visual hierarchy
- Executive-friendly and insight-rich

Goal:
Executives should understand the core message in 5 seconds, then discover deeper business insights within 30 seconds.

Visual Direction:
- Premium industrial / energy consulting aesthetic
- Design it like a premium consulting slide, not a marketing poster
- Clear section separation
- Combination of business visuals and concise explanations
- Modern dashboard-like layout
- Professional sans-serif typography
- Balanced whitespace with structured information flow
- Vertical 3:4 portrait orientation (suitable for email embedding)

Use layered information hierarchy:
- Level 1: headline + KPI
- Level 2: chart + business impact
- Level 3: supporting consultant insight

Business Storytelling Flow:
Problem → Hidden Cost → Solution → Business Impact

Output Structure:
1. Strong business headline (English, 1-2 lines)
2. One hero industrial visual (right side or top of hero)
3. Three key KPI metrics (use exact numbers from article facts)
4. One comparison chart Old vs New (use only numbers from article facts)
5. One business case summary (table with article facts)
6. One consultant insight / takeaway (Thai quote box)
7. Small supporting annotations or micro-insights — Key Formula,
   Rule of Thumb, Downtime Cost Trick

Content Rules:
- Keep text concise but meaningful
- Avoid crowded infographic
- Avoid excessive whitespace
- Avoid tiny unreadable text
- Prioritize strategic clarity over decoration
- Focus on one main business narrative
- Use executive-level communication style
- Make charts simple and visually clean
- Highlight financial and operational impact clearly

Language Rules (critical):
- Big headlines and section labels must be in ENGLISH
  (e.g. "PROBLEM", "HIDDEN COST", "SOLUTION", "BUSINESS IMPACT",
   "CASE SUMMARY", "CONSULTANT INSIGHT", "KEY FORMULA",
   "RULE OF THUMB", "DOWNTIME COST TRICK")
- Body explanations and bullets must be in THAI — use a clean
  Sarabun-style sans-serif Thai font with sharp readable glyphs.
  No broken or scrambled Thai characters.
- Technical terms in parentheses are OK (e.g. "ต้นทุนรวม (TCO)")
- KPI values use numerals (language-neutral)

First identify:
- Main business insight
- Key financial impact (with EXACT numbers from article facts)
- Hidden cost drivers
- Best visual metaphor
- Executive takeaway

Then create the infographic. Include "PTT NGR ESP" branding in the
footer with tagline "Driving Energy Efficiency. Delivering Sustainable Value."""


class ImageAgent:
    """Renders an infographic per daily article. Vertex-only — falls
    back to None when VERTEX_AI_PROJECT is not configured."""

    def __init__(self, settings: Settings, gemini: GeminiClient):
        self.settings = settings
        self.gemini = gemini
        self.client = self._init_client()

    def _init_client(self):
        if not self.settings.use_vertex:
            logger.info("🎨 ImageAgent: Vertex AI not configured — disabled")
            return None
        try:
            creds = service_account.Credentials.from_service_account_file(
                self.settings.VERTEX_AI_SERVICE_ACCOUNT_FILE,
                scopes=VERTEX_SCOPES,
            )
            client = genai.Client(
                vertexai=True,
                project=self.settings.VERTEX_AI_PROJECT,
                location=self.settings.VERTEX_AI_LOCATION,
                credentials=creds,
            )
            logger.info(f"🎨 ImageAgent ready ({IMAGE_MODEL})")
            return client
        except Exception as e:
            logger.error(f"🎨 ImageAgent init failed: {e}")
            return None

    def generate(self, article_md: str, topic_meta: dict) -> bytes | None:
        """Returns PNG bytes, or None on failure / disabled."""
        if not self.client:
            return None
        try:
            brief = self._build_brief(article_md)
            if not brief or brief.startswith("[Error"):
                logger.warning("🎨 brief generation failed — skipping image")
                return None

            prompt = IMAGE_PROMPT.format(
                topic=topic_meta.get("topic", ""),
                industry=topic_meta.get("industry", "ทั่วไป") or "ทั่วไป",
                pillar=topic_meta.get("pillar", "TECHNICAL"),
                brief=brief.strip(),
            )
            logger.info(
                f"🎨 ImageAgent: generating infographic "
                f"(prompt {len(prompt)} chars, brief {len(brief)} chars)"
            )

            response = self.client.models.generate_content(
                model=IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )
            data = self._extract_image_bytes(response)
            if not data:
                logger.warning("🎨 model returned no image (safety filter?)")
                return None
            logger.info(f"🎨 image OK ({len(data) // 1024} KB)")
            return data
        except Exception as e:
            logger.error(f"🎨 image gen failed (non-blocking): {e}")
            return None

    @staticmethod
    def _extract_image_bytes(response) -> bytes | None:
        """Pull the first inline_data image bytes out of a Gemini Image
        response. Returns None when no image part is present."""
        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if not inline:
                    continue
                mime = getattr(inline, "mime_type", "") or ""
                if mime.startswith("image/"):
                    data = getattr(inline, "data", None)
                    if data:
                        return data
        return None

    def _build_brief(self, article_md: str) -> str:
        """Compress the full article into a ≤300-word brief. Reuses the
        text Gemini client (Flash) so the call is retried + cost-tracked
        like every other agent."""
        return self.gemini.generate(
            BRIEF_PROMPT.format(article=article_md[:2500]),
            agent_tag="image_brief",
        )
