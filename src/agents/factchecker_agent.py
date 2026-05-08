"""
FactChecker Agent — anti-hallucination gate.

Runs after Expert + Industry, before Translator. Reviews technical content
against the original Research data to catch and soften:
- specific company names that weren't in the research input
- precise numbers (savings %, payback years, kWh) without a verifiable source
- citations of standards/laws (DEDE, TIS, มอก., ISO) that may be invented

Default model: gemini-2.5-pro (accuracy matters more than cost here).
Override with env GEMINI_MODEL_FACTCHECKER.
"""
import json
import logging
import re

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Heuristics for "this might be a hallucination" — fast pre-check.
# We only run the LLM if at least one heuristic flags content.
SUSPICIOUS_COMPANY_RE = re.compile(
    r"(?:บริษัท|บมจ\.?|จำกัด|จก\.?|Co\.?,?\s*Ltd\.?|Corp\.?|Inc\.?)\s*[A-Za-zก-๙][A-Za-zก-๙\s]{1,30}"
)
PRECISE_PERCENT_RE = re.compile(r"\b\d{2,}(?:\.\d+)?\s*%")  # 23%, 25.5%
PRECISE_PAYBACK_RE = re.compile(r"\b\d+\.\d+\s*(?:ปี|year)")  # 2.7 ปี
SPECIFIC_DATE_RE = re.compile(r"\b(?:พ\.ศ\.|ปี)\s*\d{4}\b")
# Thai often writes title+name with NO space (คุณสมชาย, นายสมหมาย).
# We accept some false positives — they just mean an extra LLM call,
# which is acceptable for the FactChecker trigger.
PERSON_TITLE_RE = re.compile(
    r"(?:^|\s)(?:คุณ|นาย|นาง|นางสาว)[ก-๙]{2,}(?=\s|[,.])"
    r"|(?:Mr|Ms|Mrs)\.?\s+[A-Z]"
)

PROMPT = """
คุณคือ Fact-Checker ของ PTT NGR ESP — ผู้เชี่ยวชาญพลังงานอุตสาหกรรมไทย
รู้จักมาตรฐาน DEDE, TIS, มอก., ISO 50001 และ พ.ร.บ. ส่งเสริมการอนุรักษ์พลังงาน 2535 ของจริง

หน้าที่: ตรวจเนื้อหาด้านล่างให้ "ปลอดภัยต่อการ publish" — ไม่มีคำกล่าวอ้างที่ไม่ verify ได้

Source data ที่ verify ได้ (จาก Research agent):
{research_json}

เนื้อหาที่ต้องตรวจ:
{content}

กฎที่ต้องบังคับ:
1. ชื่อบริษัทเฉพาะ ที่ไม่ปรากฏใน source → เปลี่ยนเป็น "โรงงาน{{อุตสาหกรรม}}ขนาด{{เล็ก/กลาง/ใหญ่}}แห่งหนึ่ง"
2. ตัวเลขเฉพาะ (23%, 2.7 ปี, 1,234 kWh) ที่ไม่มีใน source → ต้องเพิ่ม "ประมาณ" หรือเปลี่ยนเป็น range เช่น "15–25%"
3. ชื่อมาตรฐาน → ใช้เฉพาะที่มีจริง (DEDE, TIS, มอก., ISO 50001, พ.ร.บ. 2535) ถ้าไม่แน่ใจให้ใช้ "มาตรฐานที่เกี่ยวข้อง"
4. ชื่อบุคคล (คุณ X, นาย Y, ผู้บริหาร X) → ลบทิ้ง
5. การอ้างกฎหมาย → เฉพาะที่มีจริง อย่าอ้าง พ.ร.บ. ที่ไม่มี

ห้ามทำ:
- ห้ามแก้โครงสร้าง (## หัวข้อ ทั้งหมดต้องเหมือนเดิม)
- ห้ามลบ Case Study / Takeaways / glossary sections
- ห้ามแต่งเรื่องใหม่ — แค่ soften สิ่งที่มี

ตอบกลับ Markdown ฉบับแก้แล้ว เท่านั้น ไม่ต้องอธิบาย ไม่ต้องใส่ comment
ถ้าเนื้อหาเดิมผ่านเกณฑ์ทุกข้อ ตอบกลับเนื้อหาเดิมเป๊ะๆ ไม่แก้
"""


class FactCheckerAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def review(self, content: str, research: dict) -> str:
        flags = self._heuristic_flags(content, research)
        if not flags:
            logger.info("✓ FactChecker: no hallucination heuristics triggered (no LLM call)")
            return content

        logger.info(f"🔍 FactChecker: {len(flags)} suspicious pattern(s) — calling Pro for review")
        research_summary = {k: v for k, v in research.items()
                            if k in ("summary", "key_facts", "sources", "standards")}
        if not research_summary:
            research_summary = research
        improved = self.gemini.generate(
            PROMPT.format(
                research_json=json.dumps(research_summary, ensure_ascii=False)[:1500],
                content=content,
            ),
            max_tokens=2500,
            agent_tag="factchecker",
        )
        if improved and not improved.startswith("[Error"):
            return improved
        logger.warning("FactChecker LLM failed — keeping original (not safer, but no fabrication)")
        return content

    @staticmethod
    def _heuristic_flags(content: str, research: dict) -> list[str]:
        """Cheap regex pre-check. Returns list of triggered flags."""
        flags = []
        research_text = json.dumps(research, ensure_ascii=False).lower()

        for m in SUSPICIOUS_COMPANY_RE.finditer(content):
            snippet = m.group(0).strip()
            if snippet.lower() not in research_text:
                flags.append(f"company-mention:{snippet[:30]}")

        for m in PRECISE_PERCENT_RE.finditer(content):
            num = m.group(0).strip()
            if num not in research_text and "ประมาณ" not in content[max(0, m.start()-15):m.start()]:
                flags.append(f"precise-percent:{num}")

        for m in PRECISE_PAYBACK_RE.finditer(content):
            num = m.group(0).strip()
            if num not in research_text:
                flags.append(f"precise-payback:{num}")

        if PERSON_TITLE_RE.search(content):
            flags.append("person-name")

        return flags[:10]  # cap noise
