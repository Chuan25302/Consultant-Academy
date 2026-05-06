"""
Recap Agent — runs every Friday.
Finds [Email] files from Mon–Thu in Drive, summarizes, uploads [Recap].
"""
import re
import logging
from datetime import datetime, timedelta

from src.integrations.gemini_client import GeminiClient
from src.integrations.drive_api import DriveAPI
from src.agents.designer_agent import DesignerAgent

logger = logging.getLogger(__name__)

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

    def generate_and_upload(self):
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        summaries = []

        for offset in range(4):  # Mon–Thu
            prefix = f"[Email] {(week_start + timedelta(days=offset)).strftime('%Y-%m-%d')}"
            files = self.drive.list_files_by_prefix(prefix)
            for f in files:
                title = re.sub(r"\[Email\] \d{4}-\d{2}-\d{2} (.+)\.html", r"\1", f["name"])
                summaries.append(f"- {title}")

        if not summaries:
            logger.warning("⚠️ No emails found for recap")
            return

        recap_md = self.gemini.generate(
            PROMPT.format(
                week=today.isocalendar()[1],
                summaries="\n".join(summaries)
            ),
            max_tokens=1500
        )

        recap_html = DesignerAgent.create_email(
            content=recap_md,
            metadata={
                "pillar": "RECAP",
                "topic": f"สรุป สัปดาห์ที่ {today.isocalendar()[1]} — Consultant Toolkit",
                "date": today, "industry": None
            }
        )

        date_str = today.strftime("%Y-%m-%d")
        month_path = today.strftime("%Y/%B").lower()
        folder_id = self.drive.get_or_create_folder(
            path=f"Email Archives/{month_path}",
            root_id=self.settings.FOLDER_EMAIL_ARCHIVES
        )
        self.drive.upload(
            filename=f"[Recap] {date_str} สัปดาห์ที่ {today.isocalendar()[1]}.html",
            content=recap_html,
            folder_id=folder_id,
            mime_type="text/html"
        )
        logger.info("✅ Weekly recap uploaded")
