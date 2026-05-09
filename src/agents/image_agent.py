"""
Image Agent — generates an executive consulting infographic for each
daily article using Vertex AI's Gemini 2.5 Flash Image model.

The model receives the full Thai article plus the McKinsey/BCG-style
visual brief verbatim — Gemini Flash Image's ~32k-token context easily
fits both, so we no longer need a separate Gemini-text brief generator
to summarize first. The image model translates Thai facts to English
while rendering, and the same brief continues to constrain it from
inventing numbers.

Model is overridable via the IMAGE_MODEL env var so we can A/B with
imagen-4.0-* etc. without code changes.

Output is non-blocking: any failure (Vertex not configured, API error,
safety filter trip) returns None and the daily run continues without
an image rather than miss the email entirely.

Cost: ~$0.039/image (Gemini 2.5 Flash Image, single call per day).
"""
import logging
import os

from google import genai
from google.genai import types
from google.oauth2 import service_account

from src.config.settings import Settings

logger = logging.getLogger(__name__)

VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
# Default to Gemini Flash Image: it accepts ~32k tokens of prompt, which
# lets us send the full McKinsey-style brief verbatim. Imagen 4 has the
# better text rendering reputation but a hard ~480-token cap that
# truncates the layout instructions before they get a chance to apply.
# Override via IMAGE_MODEL env to A/B with imagen-4.0-* etc.
DEFAULT_MODEL = "gemini-2.5-flash-image"

# Image prompt — kept in the user's original McKinsey/BCG framing,
# but the Output Structure is spelled out section by section so the
# model treats it as an executive briefing card (information-dense
# but scannable), not a sparse marketing slide. The full Thai article
# is appended below; the image model translates Thai facts into
# English while rendering. Image models handle Latin script far more
# reliably than Thai, and the full Thai version lives in the email
# body where browser rendering is perfect.
IMAGE_PROMPT = """Transform this industrial consulting article into a premium executive consulting infographic.

Style:
- McKinsey + BCG style business infographic
- Clean and modern consulting presentation
- Dark blue + white + subtle energy green palette
- Balanced information density (executive briefing card, NOT a sparse marketing slide)
- Strong visual hierarchy
- Executive-friendly and insight-rich

Goal:
Executives should understand the core message in 5 seconds, then discover deeper business insights within 30 seconds.

Visual Direction:
- Premium industrial / energy consulting aesthetic
- Design it like a premium consulting slide, not a marketing poster
- Clear section separation
- Combination of business visuals and concise explanations under each visual
- Modern dashboard-like layout
- Professional typography
- Balanced whitespace with structured information flow

Use layered information hierarchy:
- Level 1: headline + 3 KPI badges
- Level 2: 4-step strategy flow + comparison chart + business case summary
- Level 3: consultant insight quote + key formulas / takeaways

Business Storytelling Flow:
Problem -> Hidden Cost -> Solution -> Business Impact

Output Structure (every section below MUST appear in the final image with real content drawn from the article — not just headings, not blank placeholders):

1. HERO PANEL
   - Bold English headline (one strong sentence) on a navy background
   - One short English subtitle line beneath it
   - One realistic industrial photo on the right (steam pipes, cooling tower, valves)

2. KPI ROW (three big metric badges side-by-side)
   - Each badge: a large number / range + a 2-3 word English label + a 1-line English context note
     (e.g., "≈ 1M baht / month", "vs 15+ year old system", "investment: 25M baht")

3. FOUR-STEP STRATEGY FLOW with arrows connecting the steps
   - Step titles in English uppercase: PROBLEM, HIDDEN COST, SOLUTION, BUSINESS IMPACT
   - Under each step title, place 2-3 short English bullet sentences (5-9 words each)
     drawn directly from the article's facts for that step
   - A small flat-style icon in green sits beside each step title

4. COMPARISON CHART
   - Stacked-bar titled "10-YEAR TOTAL COST OF OWNERSHIP"
   - Two bars: "Old System" (taller, mostly navy) vs "New Efficient System" (shorter, mostly green)
   - Stack categories labeled in English: CapEx, Energy (OpEx), Maintenance, Downtime & Others
   - Green callout arrow showing the savings percentage from the article

5. BUSINESS CASE SUMMARY (compact table on the right or below the chart)
   - 5 rows: Industry / Investment / Energy Saving / Maintenance Reduction / Payback Period
   - Values pulled from the article (use ranges where the article uses ranges)

6. CONSULTANT INSIGHT (pull-quote card)
   - The article's consultant question, translated into a clean professional English
     sentence, displayed inside a soft cream callout
   - Add 1-line English context underneath explaining why this question works

7. KNOWLEDGE CAPTURE (dedicated callout panel near the bottom — this
   is the "remember this" card that defines the article as a piece of
   knowledge sharing, and must be visually distinct from the rest of
   the infographic — set on a soft amber or pale-yellow background)
   - Panel title in English uppercase: KNOWLEDGE CAPTURE
   - One short English summary sentence at the top of the panel
     (the article's KC summary, e.g., "TCO shifts the conversation
     from price to lifetime value")
   - Beneath it, 2-3 small inline reference cards each labeled with a
     short English title (e.g., "TCO Formula", "Payback Rule",
     "Downtime Cost Trick") containing the formula or rule of thumb
     in plain text on a single line

Content Rules:
- Every section above MUST be filled with actual content from the article — not empty boxes, not stub labels
- Per-section text density: aim for 2-3 short English sentences in body sections (PROBLEM, HIDDEN COST, SOLUTION, IMPACT, KNOWLEDGE CAPTURE); one rich sentence in HERO subtitle and INSIGHT quote
- Total visible body text across all sections should comfortably fill the canvas without crowding (think "executive one-page summary")
- Keep each individual sentence concise (5-9 words) so it stays readable at thumbnail size
- Avoid crowded crammed-together text AND avoid empty whitespace; aim for the balanced density of a premium consulting deliverable
- Avoid tiny unreadable text — body bullets should be readable at half-page size
- Prioritize strategic clarity over decoration
- Focus on one main business narrative
- Use executive-level communication style
- Make charts simple and visually clean
- Highlight financial and operational impact clearly with bold numbers

First identify (do this internally before laying out the canvas):
- Main business insight
- Key financial impact (with exact numbers from the article)
- Hidden cost drivers (specific drivers from the article, not generic)
- Best visual metaphor
- Executive takeaway

Then create the infographic — fill every section with real article content, in English.

Critical typography rule:
Use generously large typography throughout. The hero headline fills
most of the panel width. KPI numbers are very large and bold (the
single most prominent element on the canvas after the headline).
Body bullets, chart axis labels, table cells, and Knowledge Capture
formulas are large enough to be comfortably readable when the
infographic is viewed as a thumbnail inside an email or on a phone
screen. Avoid ANY tiny or cramped text — if a section can't fit at
a readable size, prefer fewer words over shrinking the type.

Critical language rule:
ALL TEXT IN THE FINAL IMAGE MUST BE ENGLISH ONLY. The article below
is in Thai — translate the salient facts into clean professional
English when placing them on the canvas. Do NOT render any Thai
characters or any other non-Latin script anywhere in the image.

Critical accuracy rule:
Use ONLY numbers and facts that appear in the article below. If the
article says "25-30%", show "25-30%" — do not invent a more specific
"27%". Do not fabricate company names, person names, or timelines.

Critical branding rule:
Do NOT place any logo, watermark, brand mark, color hex code, or
font name anywhere in the image.

Article:
{article}"""


def _is_imagen(model: str) -> bool:
    return model.startswith("imagen")


class ImageAgent:
    """Renders an infographic per daily article. Vertex-only — falls
    back to None when VERTEX_AI_PROJECT is not configured."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = os.getenv("IMAGE_MODEL", DEFAULT_MODEL)
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
            logger.info(f"🎨 ImageAgent ready ({self.model_name})")
            return client
        except Exception as e:
            logger.error(f"🎨 ImageAgent init failed: {e}")
            return None

    def generate(self, article_md: str, topic_meta: dict) -> bytes | None:
        """Returns PNG bytes, or None on failure / disabled."""
        if not self.client:
            return None
        try:
            # Pass the full Thai article straight into the image prompt.
            # Gemini 2.5 Flash Image's ~32k-token window comfortably
            # holds article + style template; a separate text-only
            # brief generator is no longer needed.
            article = (article_md or "").strip()[:6000]  # safety cap
            prompt = IMAGE_PROMPT.format(article=article)
            logger.info(
                f"🎨 ImageAgent: generating via {self.model_name} "
                f"(prompt {len(prompt)} chars)"
            )

            if _is_imagen(self.model_name):
                data = self._call_imagen(prompt)
            else:
                data = self._call_gemini_image(prompt)

            if not data:
                logger.warning("🎨 model returned no image (safety filter?)")
                return None
            logger.info(f"🎨 image OK ({len(data) // 1024} KB)")
            return data
        except Exception as e:
            logger.error(f"🎨 image gen failed (non-blocking): {e}")
            return None

    def _call_imagen(self, prompt: str) -> bytes | None:
        """Imagen 4 family uses the dedicated generate_images endpoint."""
        response = self.client.models.generate_images(
            model=self.model_name,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="3:4",
                output_mime_type="image/png",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="DONT_ALLOW",
            ),
        )
        images = getattr(response, "generated_images", None) or []
        if not images:
            return None
        return images[0].image.image_bytes

    def _call_gemini_image(self, prompt: str) -> bytes | None:
        """Gemini 2.5+/3.x Image models go through generate_content with
        an IMAGE response modality and embed bytes in inline_data parts."""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
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
