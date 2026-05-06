"""
Parses Content-Calendar-YYYY.md from Google Drive.
Line format:
- **2024-05-06**: TECHNICAL | Chiller Efficiency 101 | Hospitality | chiller,COP,fouling
"""
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class CalendarParser:
    def __init__(self, content: str):
        self.content = content

    def get_topic(self, date: datetime) -> dict | None:
        date_key = date.strftime("%Y-%m-%d")
        for line in self.content.splitlines():
            if date_key not in line:
                continue
            line_clean = re.sub(r"\*\*|`", "", line).strip().lstrip("- ")
            match = re.match(r"\d{4}-\d{2}-\d{2}:\s*(.+)", line_clean)
            if not match:
                continue
            parts = [p.strip() for p in match.group(1).split("|")]
            if len(parts) < 2:
                continue
            return {
                "pillar": parts[0].upper(),
                "topic": parts[1] if len(parts) > 1 else "ทั่วไป",
                "industry": parts[2] if len(parts) > 2 else "General",
                "keywords": [k.strip() for k in parts[3].split(",")] if len(parts) > 3 else [],
                "date": date
            }
        logger.warning(f"No topic found for {date_key}")
        return None
