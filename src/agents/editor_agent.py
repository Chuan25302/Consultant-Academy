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

from src.agents.formats import KIT_SPECS
from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Look for numbers followed by typical engineering/finance units.
# Matches "300 kWh", "4.5 บาท", "20%", "2.5 ปี", "7 °C", "250 Pa", "1450 rpm".
NUMBER_WITH_UNIT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:"
    r"บาท|ชม|ชั่วโมง|ตัน|%|°C|℃|ปี"
    # Latin units must end the word: "2 parameters" / "3 barriers" are not readings.
    r"|(?:baht|THB|kWh|MWh|kW|MW|years?|hours?|kPa|Pa|bar|kg|tCO2e"
    r"|(?-i:Hz|rpm|ppm|RT|V|A|L/s|m3/h|m³/h))(?![A-Za-z])"
    r")",
    re.IGNORECASE,
)
KIT_HEADING_RE = re.compile(r"^##\s*🧰\s*\S", re.MULTILINE)
CHECKBOX_RE = re.compile(r"^- ☐ ", re.MULTILINE)
SQUARE_BOX_RE = re.compile(r"^- \[ ?\]", re.MULTILINE)
OBJECTION_RE = re.compile(r"\*\*ลูกค้า:\*\*")
FORMULA_RE = re.compile(r"^[^#\n]*=[^\n]*$", re.MULTILINE)
SOURCE_TAG_RE = re.compile(r"—\s*ที่มา\s*:")
RECALL_RE = re.compile(r"^##\s*🔁", re.MULTILINE)
ANSWER_RE = re.compile(r"^##\s*🔑", re.MULTILINE)
def _squash(text: str) -> str:
    """Whitespace-insensitive form for containment checks (multi-word scenes)."""
    return re.sub(r"\s+", "", text)


_H2_RE = re.compile(r"^## ", re.MULTILINE)
# The four anchors, mirroring the heading shapes designer_agent parses
# (CMOVE_RE / kcapture / glossary list form). Do not loosen.
ANCHOR_PATTERNS = {
    "💡 ประเด็นวันนี้": re.compile(r"^##\s*💡\s*ประเด็นวันนี้", re.MULTILINE),
    "Consultant Move": re.compile(r"^##\s*(?:\d+\.\s*)?Consultant Move\s*$", re.MULTILINE),
    "Knowledge Capture": re.compile(r"^##\s*(?:\d+\.\s*)?Knowledge Capture\s*$", re.MULTILINE),
    "📖 ศัพท์น่ารู้": re.compile(r"^##\s*📖\s*ศัพท์น่ารู้\s*$", re.MULTILINE),
}

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
- ความยาวรวมไม่เกิน 1,000 คำ และห้ามลบหัวข้อ 🧰 / 🔁 / 🔑 ที่มีอยู่

เนื้อหาเดิม:
{content}
"""


class EditorAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini
        self.last_repair_count = 0  # 1 when review() fired its repair call

    @staticmethod
    def strip_latex(md: str) -> str:
        return LATEX_INLINE_RE.sub(lambda m: _delatex(m.group(1)), md)

    def review(self, md: str, *, kit: str = "", scene: str = "",
               recall: bool = False) -> str:
        self.last_repair_count = 0
        md = self.strip_latex(md)
        issues = self.check(md, kit=kit, scene=scene, recall=recall)
        if not issues:
            logger.info("✓ Editor: content passes all checks (no LLM call)")
            return md

        logger.info(f"✏️  Editor: regenerating to fix {len(issues)} issue(s): {issues}")
        self.last_repair_count = 1
        bullet_issues = "\n".join(f"- {i}" for i in issues)
        improved = self.gemini.generate(
            PROMPT.format(issues=bullet_issues, content=md),
            agent_tag="editor",
        )
        if improved and not improved.startswith("[Error"):
            repaired = self.strip_latex(improved)
            # One re-check, no repair loop (cost): make a failed repair visible.
            remaining = self.check(repaired, kit=kit, scene=scene, recall=recall)
            if remaining:
                logger.warning(
                    f"Editor: repair still failing {len(remaining)} check(s): {remaining}")
            return repaired
        logger.warning("Editor regen failed — keeping original")
        return md

    @staticmethod
    def _kit_section(md: str) -> str:
        """Body of the '## 🧰' section, up to the next '## ' heading."""
        m = KIT_HEADING_RE.search(md)
        if not m:
            return ""
        rest = md[m.end():]
        nxt = _H2_RE.search(rest)
        return rest[:nxt.start()] if nxt else rest

    @staticmethod
    def _kit_issues(md: str, kit: str) -> list[str]:
        """Gates that enforce KIT_SPECS instructions, scoped to the kit section
        so lines elsewhere (glossary '=', recall '?') cannot satisfy them."""
        issues: list[str] = []
        section = EditorAgent._kit_section(md)
        if kit == "checklist":
            if SQUARE_BOX_RE.search(md):
                issues.append("checklist ใช้ '- [ ]' — ต้องใช้ '- ☐ ' เท่านั้น")
            boxes = CHECKBOX_RE.findall(section)
            if len(boxes) < 6:
                issues.append(f"checklist มี {len(boxes)} ข้อ ต้องการอย่างน้อย 6")
            with_numbers = [ln for ln in section.splitlines()
                            if ln.startswith("- ☐ ") and NUMBER_WITH_UNIT_RE.search(ln)]
            if len(with_numbers) < 3:
                issues.append("checklist ต้องมีข้อที่ระบุค่าปกติเป็นตัวเลข+หน่วย ≥3 ข้อ")
        elif kit == "questions":
            questions = [ln for ln in section.splitlines() if ln.strip().endswith("?")]
            if len(questions) < 4:
                issues.append(f"ชุดคำถามมี {len(questions)} ข้อ ต้องการอย่างน้อย 4")
            if len(OBJECTION_RE.findall(section)) < 2:
                issues.append("ต้องมี objection พร้อมคำตอบอย่างน้อย 2 ชุด (**ลูกค้า:**)")
        elif kit == "calculator":
            if not FORMULA_RE.search(section):
                issues.append("สูตรคำนวณต้องมีบรรทัดที่มีเครื่องหมาย '='")
            if not SOURCE_TAG_RE.search(section):
                issues.append("ตัวเลขอ้างอิงต้องมี '— ที่มา: ...' กำกับ")
        return issues

    @staticmethod
    def check(md: str, kit: str = "", scene: str = "",
              recall: bool = False) -> list[str]:
        issues = []
        for name, pattern in ANCHOR_PATTERNS.items():
            if not pattern.search(md):
                issues.append(f"ขาด anchor '{name}' — designer/recap จะพัง")

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

        if kit:
            spec = KIT_SPECS.get(kit)
            if spec is None:
                issues.append(f"ไม่รู้จัก kit '{kit}' — ตรวจ kit ไม่ได้")
            elif not KIT_HEADING_RE.search(md):
                issues.append(f"ขาดหัวข้อเครื่องมือ '## 🧰 {spec.label}'")
            else:
                issues += EditorAgent._kit_issues(md, kit)
        if scene and _squash(scene) not in _squash(md):
            issues.append(f"ไม่ได้ใช้ฉากที่กำหนด — ต้องอ้างถึง '{scene}'")
        if recall:
            if not RECALL_RE.search(md):
                issues.append("ขาดบล็อก '## 🔁 ทวนของเก่า' ทั้งที่มีของเก่าให้ทวน")
            if not ANSWER_RE.search(md):
                issues.append("ขาดกล่องเฉลย '## 🔑 เฉลย' ของบล็อกทวนของเก่า")
        elif RECALL_RE.search(md) and not ANSWER_RE.search(md):
            issues.append("มี '🔁 ทวนของเก่า' แต่ขาดกล่องเฉลย '## 🔑 เฉลย'")
        return issues
