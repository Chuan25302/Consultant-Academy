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
TAKEAWAY_RE = re.compile(r"Takeaways?|ทีม\s*Sales|ทีม\s*Technical", re.IGNORECASE)

# Anti-hallucination spot check — catches leftover specifics the FactChecker
# might have missed. Person-name detection in Thai is unreliable (no spaces
# between title and name; "คุณ" is also a regular word) so we leave that to
# the LLM-powered FactChecker upstream and only check company patterns here.
SPECIFIC_COMPANY_RE = re.compile(
    # [บห]จก: bare "จก" also ends "เรือนกระจก" (greenhouse) — false positive.
    r"(?:บริษัท|บมจ\.?|[บห]จก\.?|จำกัด|Co\.?,?\s*Ltd\.?|Inc\.?|Corp\.?)\s+[A-Za-zก-๙][A-Za-zก-๙\s]{1,20}"
)

# Inline LaTeX ($...$ containing a \command). gemini-3.x emits units and
# formulas this way (e.g. $\text{tCO}_2\text{e}$) and email clients show it
# raw. Requiring a backslash leaves plain dollar amounts ("$100") alone.
LATEX_INLINE_RE = re.compile(r"\$([^$\n]*?\\[A-Za-z]+[^$\n]*?)\$")
_LATEX_SYMBOLS = {
    "times": "×", "cdot": "·", "sum": "Σ", "Sigma": "Σ", "approx": "≈",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "pm": "±", "Delta": "Δ",
    "rightarrow": "→", "to": "→",
}


def _delatex(expr: str) -> str:
    prev = None
    while prev != expr:  # unwrap nested \text{...} etc.
        prev = expr
        expr = re.sub(r"\\(?:text|mathrm|mathbf|textbf|operatorname)\{([^{}]*)\}",
                      r"\1", expr)
        expr = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", expr)
    expr = re.sub(r"\\([A-Za-z]+)",
                  lambda m: _LATEX_SYMBOLS.get(m.group(1), m.group(1)), expr)
    expr = re.sub(r"_\{([^{}]*)\}|_(\w)", lambda m: m.group(1) or m.group(2), expr)
    expr = re.sub(r"\^\{([^{}]*)\}", r"^\1", expr)
    expr = expr.replace(r"\%", "%").replace("{", "").replace("}", "")
    return re.sub(r"\s{2,}", " ", expr).strip()


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
- ความยาวรวมไม่เกิน 1,000 คำ

เนื้อหาเดิม:
{content}
"""


class EditorAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    @staticmethod
    def strip_latex(md: str) -> str:
        return LATEX_INLINE_RE.sub(lambda m: _delatex(m.group(1)), md)

    def review(self, md: str) -> str:
        md = self.strip_latex(md)
        issues = self.check(md)
        if not issues:
            logger.info("✓ Editor: content passes all checks (no LLM call)")
            return md

        logger.info(f"✏️  Editor: regenerating to fix {len(issues)} issue(s): {issues}")
        bullet_issues = "\n".join(f"- {i}" for i in issues)
        improved = self.gemini.generate(
            PROMPT.format(issues=bullet_issues, content=md),
            agent_tag="editor",
        )
        if improved and not improved.startswith("[Error"):
            return self.strip_latex(improved)
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
        if word_count > 1200:
            issues.append(f"เนื้อหายาว {word_count} คำ ต้องการไม่เกิน 1,000")
        # Anti-hallucination spot check (FactChecker should have cleaned this,
        # but Editor catches anything that slipped through).
        if SPECIFIC_COMPANY_RE.search(md):
            issues.append("พบชื่อบริษัทเฉพาะ — เปลี่ยนเป็น 'โรงงานขนาด X แห่งหนึ่ง'")
        return issues
