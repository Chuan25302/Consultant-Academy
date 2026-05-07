"""
Calendar Planner Agent — auto-extends the Drive calendar when it runs low.

Triggered automatically by main.py after each successful run if the
calendar has fewer than `lookahead_days` days of entries ahead.
Generates next 4 weeks of topics (Mon–Fri content + Sat RECAP) using
Pro 2.5 by default (override via GEMINI_MODEL_PLANNER), then writes
back to the Drive calendar file.

Manual trigger: `python src/main.py --plan-next` (skips daily pipeline).

Cost: only triggered when calendar runs low — typically once a month.
~$0.05 per planning event with Pro 2.5.
"""
import logging
import re
from datetime import datetime, timedelta

from src.config.settings import now_bangkok
from src.integrations.drive_api import DriveAPI
from src.integrations.gemini_client import GeminiClient
from src.utils.calendar_parser import CalendarParser

logger = logging.getLogger(__name__)

DEFAULT_LOOKAHEAD_DAYS = 14
DEFAULT_NEW_WEEKS = 4
HISTORY_LINES = 30

PROMPT = """
คุณคือ Curriculum Planner ของ PTT NGR ESP Consultant Academy

จุดประสงค์: สร้างปฏิทินต่อจากปัจจุบัน {num_weeks} สัปดาห์ใหม่
เริ่มวันจันทร์: {start_date}

หัวข้อล่าสุดที่เคยเรียน (history):
{history}

อุตสาหกรรมที่ระบบครอบคลุม (10 ครอบครัว):
1. Food/Pharma + Cold Storage
2. General Manufacturing
3. Petrochem & Chemical
4. Heavy: Steel/Cement/Glass
5. Automotive (Full vehicle + EV)
6. Electronics (HDD/Semi packaging)
7. Hospitals
8. SPP/Biomass/Cogen
9. Large Buildings (incl Data Center)
10. Waste Management
+ niche ที่อยากครอบคลุม: Pulp/Paper, Rubber/Glove, Tire, Ceramics,
  Battery Manufacturing, Seafood/Frozen Food

เครื่องจักรหลัก: motor, pump, compressor, chiller, cooling tower,
boiler, kiln, furnace, glass melting, BESS, heat pump, refrigeration, VFD

Pillar / day pattern (Mon-Sat):
- Mon TECHNICAL — equipment depth
- Tue INDUSTRY — sector deep-dive
- Wed FRAMEWORK or COMPLIANCE
- Thu SOFTSKILL or COMPLIANCE
- Fri SUSTAINABILITY — carbon/ESG (TGO/T-VER/CBAM/SBTi/RE100/Scope 1-2-3)
- Sat RECAP (ใส่ "RECAP | สรุปสัปดาห์ที่ N | General | recap" ไม่ต้องคิดเนื้อหา)

หลักการเลือกหัวข้อ:
1. หลีกเลี่ยงหัวข้อซ้ำกับ history — ถ้าเคยมี chiller 101 → ขึ้น chiller selection L2
2. รุก sector ที่ยังครอบคลุมน้อย (เช่น niche ข้างบน)
3. SOFTSKILL ใช้ named framework หลากหลาย: BANT/MEDDIC/SPIN/Sandler/
   Challenger/5 Whys/RACI/AIDA/Decision Matrix/TCO/Stakeholder Map
4. SUSTAINABILITY เลือกให้สอดคล้อง sector ของสัปดาห์
5. COMPLIANCE อ้างมาตรฐานจริงเท่านั้น (DEDE/TIS/มอก./ISO 14001/14064/14067/
   50001/50002/45001, IATF 16949, IPC, ASME, ASHRAE, GMP, HACCP, BRCGS)

Output format — ตอบกลับ Markdown ตรงๆ ไม่มี code fence ไม่มีคำอธิบายนำ:

### Week N — Theme name
- **YYYY-MM-DD**: PILLAR | หัวข้อ | Sector | k1,k2 | cluster=X | level=N
- **YYYY-MM-DD**: PILLAR | หัวข้อ | Sector | k1,k2 | cluster=X | level=N
- ... (Mon-Fri = 5 lines)
- **YYYY-MM-DD**: RECAP | สรุปสัปดาห์ที่ N | General | recap

### Week N+1 — ...
... (ทำซ้ำให้ครบ {num_weeks} สัปดาห์ × 6 วัน = {total_lines} บรรทัด)

ห้ามแต่งชื่อบริษัท/ตัวเลขเฉพาะ/มาตรฐานปลอม — ในหัวข้อใส่แค่ชื่อ topic
ละเอียดเรื่องตัวเลขปล่อยให้ Expert agent ดู
"""

DATE_LINE_RE = re.compile(r"^\s*-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*:\s*(.+)$")
ANY_DATE_RE = re.compile(r"\*\*(\d{4}-\d{2}-\d{2})\*\*")
VALID_PILLARS = {"TECHNICAL", "INDUSTRY", "FRAMEWORK", "SOFTSKILL",
                 "COMPLIANCE", "SUSTAINABILITY", "RECAP"}


class CalendarPlannerAgent:
    def __init__(self, gemini: GeminiClient, drive: DriveAPI, settings):
        self.gemini = gemini
        self.drive = drive
        self.settings = settings

    def needs_extension(self, calendar_text: str, today: datetime,
                        lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS) -> bool:
        """True if no calendar entries exist within `lookahead_days` of today."""
        parser = CalendarParser(calendar_text)
        for offset in range(1, lookahead_days + 1):
            if parser.get_topic(today + timedelta(days=offset)):
                return False
        return True

    def find_last_date(self, calendar_text: str) -> datetime | None:
        """Latest date appearing in the calendar (any week)."""
        dates = ANY_DATE_RE.findall(calendar_text)
        if not dates:
            return None
        parsed = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        return max(parsed)

    def extract_history(self, calendar_text: str,
                        count: int = HISTORY_LINES) -> str:
        """Return last `count` calendar entries as compact 'date pillar: topic' lines."""
        items = []
        for line in calendar_text.splitlines():
            m = DATE_LINE_RE.match(line)
            if not m:
                continue
            date_str, rest = m.groups()
            first_pipe = rest.find("|")
            if first_pipe < 0:
                continue
            pillar = rest[:first_pipe].strip()
            topic = rest[first_pipe + 1:].split("|")[0].strip()
            items.append(f"- {date_str} {pillar}: {topic}")
        return "\n".join(items[-count:])

    def _next_monday(self, after: datetime) -> datetime:
        d = after + timedelta(days=1)
        while d.weekday() != 0:  # 0 = Monday
            d += timedelta(days=1)
        return d

    def _validate(self, generated: str, expected_min_lines: int) -> str | None:
        """Drop malformed lines; reject output if too few valid entries."""
        valid = []
        for line in generated.splitlines():
            m = DATE_LINE_RE.match(line)
            if not m:
                # Keep section headers (### Week N) and blank lines as-is
                if line.startswith("###") or not line.strip():
                    valid.append(line)
                continue
            rest = m.group(2)
            pillar = rest.split("|")[0].strip().upper()
            if pillar not in VALID_PILLARS:
                logger.warning(f"Planner: invalid pillar in line, skipping: {line!r}")
                continue
            valid.append(line)
        valid_dated = sum(1 for line in valid if DATE_LINE_RE.match(line))
        if valid_dated < expected_min_lines:
            logger.warning(
                f"Planner output has only {valid_dated} valid dated lines, "
                f"need ≥{expected_min_lines} — rejecting"
            )
            return None
        return "\n".join(valid).strip()

    def generate(self, calendar_text: str,
                 num_weeks: int = DEFAULT_NEW_WEEKS) -> str | None:
        last_date = self.find_last_date(calendar_text)
        if not last_date:
            logger.error("No dates found in calendar — cannot extend")
            return None
        start = self._next_monday(last_date)
        history = self.extract_history(calendar_text)
        total_lines = num_weeks * 6  # Mon-Sat per week

        prompt = PROMPT.format(
            num_weeks=num_weeks,
            start_date=start.strftime("%Y-%m-%d"),
            history=history or "(ปฏิทินว่าง)",
            total_lines=total_lines,
        )
        raw = self.gemini.generate(
            prompt, max_tokens=3500, agent_tag="planner"
        )
        if not raw or raw.startswith("[Error"):
            logger.error("Planner LLM failed")
            return None
        # Require at least 4 dated lines per week (planner can skip weak days)
        cleaned = self._validate(raw, expected_min_lines=num_weeks * 4)
        return cleaned

    def append_to_drive(self, calendar_text: str, new_content: str) -> bool:
        if not self.settings.CALENDAR_FILE_ID:
            logger.error("CALENDAR_FILE_ID not set")
            return False
        updated = calendar_text.rstrip() + "\n\n" + new_content + "\n"
        result = self.drive.update_file_content(
            self.settings.CALENDAR_FILE_ID, updated,
            mime_type="text/markdown",
        )
        return result is not None

    def maybe_extend(self, calendar_text: str, today: datetime | None = None,
                     num_weeks: int = DEFAULT_NEW_WEEKS,
                     dry_run: bool = False) -> bool:
        """Auto-extend ONLY if calendar runs low. Non-blocking failure."""
        today = today or now_bangkok()
        if not self.needs_extension(calendar_text, today):
            return False
        logger.info(
            f"📅 Calendar runs low (<{DEFAULT_LOOKAHEAD_DAYS}d ahead) — "
            f"planning next {num_weeks} weeks..."
        )
        return self.force_extend(calendar_text, num_weeks, dry_run)

    def force_extend(self, calendar_text: str,
                     num_weeks: int = DEFAULT_NEW_WEEKS,
                     dry_run: bool = False) -> bool:
        """Always generate and append (used by --plan-next CLI flag)."""
        new_content = self.generate(calendar_text, num_weeks)
        if not new_content:
            return False
        if dry_run:
            logger.info(f"🧪 [dry-run] would append:\n{new_content}")
            return True
        ok = self.append_to_drive(calendar_text, new_content)
        if ok:
            logger.info(f"✅ Calendar extended by {num_weeks} weeks")
        return ok
