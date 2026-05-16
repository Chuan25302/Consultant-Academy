"""
Recap Agent — runs every Friday (or whenever pillar=RECAP).
Finds [Email] files from Mon–Thu in Drive, summarizes, uploads [Recap].
"""
import html as html_module
import logging
import re
from datetime import datetime, timedelta

from src.agents.designer_agent import DesignerAgent
from src.config.settings import now_bangkok
from src.integrations.drive_api import DriveAPI
from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

_STYLE_OR_SCRIPT_RE = re.compile(
    r"<(style|script)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
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
    text = _STYLE_OR_SCRIPT_RE.sub("", html_str)
    text = _BLOCK_CLOSE_RE.sub("\n", text)
    text = _BR_OR_HR_RE.sub("\n", text)
    text = _ANY_TAG_RE.sub("", text)
    text = html_module.unescape(text)
    lines = [_INLINE_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


WEEKDAY_TH_SHORT = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]

PROMPT = """
คุณคือผู้สรุปเนื้อหา PTT NGR ESP Consultant Academy

สรุปสัปดาห์นี้ให้ทีมที่ปรึกษา จากหัวข้อ Mon–Thu:
{summaries}

เขียน Markdown ภาษาไทย:

## สรุปประจำสัปดาห์ที่ {week}

### Insights ประจำวัน
{summaries}

### Key Takeaway
[1 ย่อหน้า — บทเรียนสำคัญที่สุดสัปดาห์นี้]

### นำไปใช้กับลูกค้าได้เลย
- [Consultant Move 1]
- [Consultant Move 2]
- [Consultant Move 3]

### สัปดาห์หน้า
[teaser 1 ประโยค]

ไม่เกิน 300 คำ
"""


class RecapAgent:
    def __init__(self, gemini: GeminiClient, drive: DriveAPI, settings):
        self.gemini = gemini
        self.drive = drive
        self.settings = settings

    def generate_and_upload(self, today: datetime = None, dry_run: bool = False):
        today = today or now_bangkok()
        week_start = today - timedelta(days=today.weekday())
        summaries = []
        daily_topics = []  # for the timeline strip in the recap layout

        for offset in range(5):  # Mon–Fri (recap runs Saturday)
            d = week_start + timedelta(days=offset)
            day = d.strftime("%Y-%m-%d")
            prefix = f"[Email] {day}"
            files = self.drive.list_files_by_prefix(prefix)
            day_topic = "—"
            for f in files:
                title = re.sub(r"\[Email\] \d{4}-\d{2}-\d{2} (.+)\.html",
                               r"\1", f["name"])
                summaries.append(f"- {title}")
                day_topic = title  # last one wins if a day has multiple
            daily_topics.append({
                "date_th": f"{d.day}/{d.month}",
                "day_th":  WEEKDAY_TH_SHORT[d.weekday()],
                "topic":   day_topic,
            })

        if not summaries:
            logger.warning("⚠️ No emails found for recap")
            return

        week_num = today.isocalendar()[1]
        recap_md = self.gemini.generate(
            PROMPT.format(
                week=week_num,
                summaries="\n".join(summaries),
            ),
            agent_tag="recap",
        )

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
