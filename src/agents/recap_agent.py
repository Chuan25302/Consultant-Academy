"""
Recap Agent — runs on RECAP days (typically Saturday) via the daily routine.
Downloads Mon–Fri [Email] archive bodies, turns them into a retrieval
recap (5 questions / Knowledge Capture / answers)
via Gemini, uploads [Recap] HTML to Drive, and emails it to the team.
"""
import html as html_module
import logging
import re
from datetime import datetime, timedelta

from src.agents.designer_agent import DesignerAgent
from src.config.settings import now_bangkok
from src.integrations.drive_api import DriveAPI
from src.integrations.gemini_client import GeminiClient, require_ok
from src.utils.email_sender import EmailNotSentError, email_configured, send_daily_email

logger = logging.getLogger(__name__)

_STYLE_OR_SCRIPT_RE = re.compile(
    r"<(style|script)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_CHROME_DIV_RE = re.compile(
    r'<div\s+class="(?:preheader|km-banner|ftr|meta)"[^>]*>.*?</div>',
    re.DOTALL | re.IGNORECASE,
)
_BLOCK_CLOSE_RE = re.compile(
    r"</(p|h1|h2|h3|h4|h5|h6|li|div)\s*>", re.IGNORECASE
)
_BR_OR_HR_RE = re.compile(r"<(br|hr)\s*/?>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_INLINE_WS_RE = re.compile(r"[ \t]+")


def _strip_html_to_text(html_str: str | None) -> str:
    """Convert an email-style HTML document to plain text suitable as
    LLM input.

    - Removes <style>/<script> blocks entirely (their content is not
      article content; feeding CSS to Gemini wastes tokens).
    - Replaces block-level closing tags with newlines so section
      structure (H2 headings, paragraphs, list items) survives the
      tag strip and the LLM can see where one section ends.
    - Decodes HTML entities so `&amp;` reads as `&`.
    - Collapses internal runs of spaces/tabs and drops blank lines.
    """
    if not html_str:
        return ""
    text = _CHROME_DIV_RE.sub("", html_str)
    text = _STYLE_OR_SCRIPT_RE.sub("", text)
    text = _BLOCK_CLOSE_RE.sub("\n", text)
    text = _BR_OR_HR_RE.sub("\n", text)
    text = _ANY_TAG_RE.sub("", text)
    text = html_module.unescape(text)
    lines = [_INLINE_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _build_day_digest(file_meta: dict, drive) -> str | None:
    """Download a Mon–Fri email archive and return its body as plain
    text. Returns None when the download fails or the file is empty,
    so the caller can simply skip that day rather than crashing the
    whole recap run."""
    try:
        raw = drive.download_file(file_meta["id"])
    except Exception as e:
        logger.warning(
            f"Could not download {file_meta.get('name', file_meta.get('id'))} for recap: {e}"
        )
        return None
    if not raw:
        return None
    text = _strip_html_to_text(raw)
    return text or None


WEEKDAY_TH_SHORT = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]

PROMPT = """คุณคือผู้สรุปและจับใจความเชิงลึกของ PTT NGR ESP Consultant Academy

นี่คือเนื้อหาบทความ Mon–Fri สัปดาห์ที่ {week}:

{day_digests}

---

จงเขียน Markdown ภาษาไทย ไม่เกิน 500 คำรวมทั้งหมด ตามโครงนี้:

## สรุปสัปดาห์ที่ {week}

## 🔁 ทวนสัปดาห์นี้

[5 คำถามจากเนื้อหาสัปดาห์นี้ — ถามให้ตอบจากความจำ ห้ามเฉลยตรงนี้
แต่ละข้อขึ้นต้นด้วย "- " ลงท้ายด้วย "?" และอ้างวันสั้น ๆ เช่น (จ.)
ต้องถามจากเนื้อหาที่มีจริงข้างบนเท่านั้น ห้ามแต่งข้อเท็จจริงหรือตัวเลขที่ไม่มีในเนื้อหา]

## Knowledge Capture

[3–5 bullets — ศัพท์ ตัวเลข หรือ framework ที่ควรจำจากสัปดาห์นี้]

## 🔑 เฉลย

[เฉลย 5 ข้อตามลำดับ ข้อละ 1–2 ประโยค ขึ้นต้นด้วย "- " ต้องตรงกับเนื้อหาจริง]

ห้ามขอให้ผู้อ่านตอบกลับอีเมล ห้ามขอให้กรอกฟอร์ม — อีเมลนี้เป็นทางเดียว
ผู้อ่านลองตอบในใจแล้วเลื่อนลงมาดูเฉลยเองได้เลย
"""


class RecapAgent:
    def __init__(self, gemini: GeminiClient, drive: DriveAPI, settings):
        self.gemini = gemini
        self.drive = drive
        self.settings = settings

    def generate_and_upload(self, today: datetime = None, dry_run: bool = False):
        today = today or now_bangkok()
        week_start = today - timedelta(days=today.weekday())
        day_digests: list[str] = []
        daily_topics = []  # for the timeline strip in the recap layout

        for offset in range(5):  # Mon–Fri (recap runs Saturday)
            d = week_start + timedelta(days=offset)
            day = d.strftime("%Y-%m-%d")
            prefix = f"[Email] {day}"
            files = self.drive.list_files_by_prefix(prefix)
            day_topic = "—"
            day_bodies: list[str] = []
            for f in files:
                title = re.sub(r"\[Email\] \d{4}-\d{2}-\d{2} (.+)\.html",
                               r"\1", f["name"])
                day_topic = title  # last one wins if a day has multiple
                body_text = _build_day_digest(f, self.drive)
                if body_text:
                    day_bodies.append(body_text)

            if day_bodies:
                day_digests.append(
                    f"## {WEEKDAY_TH_SHORT[d.weekday()]} {d.day}/{d.month} — {day_topic}\n\n"
                    + "\n\n".join(day_bodies)
                )
            daily_topics.append({
                "date_th": f"{d.day}/{d.month}",
                "day_th":  WEEKDAY_TH_SHORT[d.weekday()],
                "topic":   day_topic,
            })

        if not day_digests:
            logger.warning("⚠️ No content extracted for recap")
            return

        week_num = today.isocalendar()[1]
        recap_md = require_ok("recap", self.gemini.generate(
            PROMPT.format(
                week=week_num,
                day_digests="\n\n---\n\n".join(day_digests),
            ),
            agent_tag="recap",
        ))

        recap_html = DesignerAgent.create_recap_email(
            content=recap_md,
            week_num=week_num,
            daily_topics=daily_topics,
            date=today,
        )

        date_str = today.strftime("%Y-%m-%d")
        month_path = today.strftime("%Y/%B").lower()
        filename = f"[Recap] {date_str} สัปดาห์ที่ {today.isocalendar()[1]}.html"

        if dry_run:
            logger.info(f"🧪 [dry-run] would upload: {filename}")
            return

        folder_id = self.drive.get_or_create_folder(
            path=f"Email Archives/{month_path}",
            root_id=self.settings.FOLDER_EMAIL_ARCHIVES,
        )
        self.drive.upload(
            filename=filename,
            content=recap_html,
            folder_id=folder_id,
            mime_type="text/html",
        )
        logger.info("✅ Weekly recap uploaded")

        subject = (
            f"[Consultant Academy] สรุปสัปดาห์ที่ {week_num} — {date_str}"
        )
        if not send_daily_email(subject, recap_html, attachments=None) \
                and email_configured():
            raise EmailNotSentError(f"recap email not delivered: {subject}")
