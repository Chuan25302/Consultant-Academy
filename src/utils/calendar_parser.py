"""
Parses Content-Calendar-YYYY.md from Google Drive.

Line format:
    - **YYYY-MM-DD**: PILLAR | หัวข้อ | Industry | k1,k2 [| cluster=X | level=N]

Optional kv fields after the standard 4:
    cluster=...   subfolder under the pillar (e.g. HVAC-Chillers, Motors-VFD)
    level=1|2|3   1=basics, 2=intermediate, 3=advanced (default 1)
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

            standard = parts[:4]
            extras = parts[4:]
            kv = {}
            for ex in extras:
                if "=" in ex:
                    k, v = ex.split("=", 1)
                    kv[k.strip().lower()] = v.strip()

            try:
                level = int(kv.get("level", "1"))
            except ValueError:
                level = 1

            return {
                "pillar": standard[0].upper(),
                "topic": standard[1] if len(standard) > 1 else "ทั่วไป",
                "industry": standard[2] if len(standard) > 2 else "General",
                "keywords": [k.strip() for k in standard[3].split(",")] if len(standard) > 3 else [],
                "cluster": kv.get("cluster", "General"),
                "level": level,
                "date": date,
            }
        logger.warning(f"No topic found for {date_key}")
        return None
