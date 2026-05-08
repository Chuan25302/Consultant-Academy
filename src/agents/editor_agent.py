"""
Editor Agent — quality gate before content goes out.

Two-stage check (cheap → expensive):
1. Programmatic pre-check (regex, no LLM cost): does the markdown have
   the structural elements every article should have?
2. If anything is missing, ONE LLM call asks Gemini to fix specifically
   those issues — content that already passes is returned untouched
   so good drafts don't get "improved" into worse drafts.
"""
import logging
import re

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Look for numbers followed by typical engineering/finance units.
# Matches "300 kWh", "4.5 บาท", "20%", "2.5 ปี", "5 kW", "1.2 MW".
NUMBER_WITH_UNIT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:บาท|baht|THB|kWh|MWh|kW|MW|%|ปี|year|hours?|ชม)",
    re.IGNORECASE,
)
GLOSSARY_RE = re.compile(r"📖|ศัพท์น่ารู้")
CASE_STUDY_RE = re.compile(r"Case\s*Study|Situation|Complication", re.IGNORECASE)
TAKEAWAY_RE = re.compile(r"Takeaway|ทีม\s*Sales|ทีม\s*Technical", re.IGNORECASE)

# Anti-hallucination spot check — catches leftover specifics the FactChecker
# might have missed. Person-name detection in Thai is unreliable (no spaces
# between title and name; "คุณ" is also a regular word) so we leave that to
# the LLM-powered FactChecker upstream and only check company patterns here.
SPECIFIC_COMPANY_RE = re.compile(
    r"(?:บริษัท|บมจ\.?|จก\.?|จำกัด|Co\.?,?\s*Ltd\.?|Inc\.?|Corp\.?)\s+[A-Za-zก-๙][A-Za-zก-๙\s]{1,20}"
)

PROMPT = """
คุณคือ Editor ของ PTT NGR ESP Consultant Academy
แก้เนื้อหาต่อไปนี้ให้ผ่านเกณฑ์ที่กำหนด — ไม่ต้องอธิบาย ไม่ใส่ comment
แค่ตอบกลับ Markdown ฉบับแก้แล้ว

เกณฑ์ที่ยังไม่ผ่าน:
{issues}

หมายเหตุ:
- เก็บโครงสร้างเดิมไว้ ภาษาไทยเป็นหลัก ทับศัพท์ English ได้
- เพิ่มสิ่งที่ขาด อย่าลบของที่มีอยู่
- ตัวเลขต้องสมเหตุสมผล (ไม่กุขึ้น)
- ความยาวรวมไม่เกิน 600 คำ

เนื้อหาเดิม:
{content}
"""


class EditorAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def review(self, md: str) -> str:
        issues = self.check(md)
        if not issues:
            logger.info("✓ Editor: content passes all checks (no LLM call)")
            return md

        logger.info(f"✏️  Editor: regenerating to fix {len(issues)} issue(s): {issues}")
        bullet_issues = "\n".join(f"- {i}" for i in issues)
        improved = self.gemini.generate(
            PROMPT.format(issues=bullet_issues, content=md),
            max_tokens=2000,
            agent_tag="editor",
        )
        if improved and not improved.startswith("[Error"):
            return improved
        logger.warning("Editor regen failed — keeping original")
        return md

    @staticmethod
    def check(md: str) -> list[str]:
        issues = []
        if not CASE_STUDY_RE.search(md):
            issues.append("ขาด Case Study section (Situation / Complication / Result)")
        if not TAKEAWAY_RE.search(md):
            issues.append("ขาด Takeaways section (ทีม Sales / ทีม Technical)")
        if not GLOSSARY_RE.search(md):
            issues.append("ขาด glossary บรรทัดสุดท้าย (📖 ศัพท์น่ารู้: ...)")
        nums = NUMBER_WITH_UNIT_RE.findall(md)
        if len(nums) < 3:
            issues.append(
                f"มีตัวเลขจริง+หน่วย {len(nums)} จุด ต้องการอย่างน้อย 3 "
                "(เช่น บาท / kWh / % / ปี)"
            )
        word_count = len(md.split())
        if word_count > 700:
            issues.append(f"เนื้อหายาว {word_count} คำ ต้องการไม่เกิน 600")
        # Anti-hallucination spot check (FactChecker should have cleaned this,
        # but Editor catches anything that slipped through).
        if SPECIFIC_COMPANY_RE.search(md):
            issues.append("พบชื่อบริษัทเฉพาะ — เปลี่ยนเป็น 'โรงงานขนาด X แห่งหนึ่ง'")
        return issues
