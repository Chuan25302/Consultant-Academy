"""
Per-pillar email format profiles (spec 2026-09-29, A2/A6).

Data plus pure selection helpers (no I/O, no prompt assembly logic).
Editing data or helper functions cannot break prompt assembly.
TranslatorAgent reads data and calls helpers; EditorAgent enforces the result.
"""
import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class KitSpec:
    label: str
    instructions: str


@dataclass(frozen=True)
class Profile:
    sections: tuple[tuple[str, str], ...]
    kit: str
    scenes: tuple[str, ...]


KIT_SPECS = {
    "checklist": KitSpec(
        label="Checklist เดินหน้างาน",
        instructions=(
            "6–8 ข้อ ขึ้นต้นด้วย '- ☐ ' (ห้ามใช้ '- [ ]')\n"
            "แต่ละข้อต้องครบ 3 ส่วน: ตรวจอะไร / ค่าปกติควรเป็นเท่าไร (ตัวเลข+หน่วย) / "
            "ถ้าผิดปกติแปลว่าอะไร\n"
            "อย่างน้อย 3 ข้อต้องมีตัวเลข+หน่วย"
        ),
    ),
    "questions": KitSpec(
        label="ชุดคำถามเจาะลูกค้า",
        instructions=(
            "4–5 คำถาม เรียงจากกว้างไปลึก แต่ละบรรทัดลงท้ายด้วย '?'\n"
            "ตามด้วย objection ที่เจอบ่อย 2 ข้อ รูปแบบ:\n"
            "**ลูกค้า:** \"...\"\n**ตอบ:** \"...\"\n"
            "คำตอบต้องอ้างตัวเลขหรือความเสี่ยงที่จับต้องได้"
        ),
    ),
    "calculator": KitSpec(
        label="สูตรคำนวณพร้อมใช้",
        instructions=(
            "สูตร 1–2 บรรทัด เขียนเป็นข้อความธรรมดา (ห้าม LaTeX) มีเครื่องหมาย '='\n"
            "ระบุตัวแปรที่ต้องถามลูกค้า\n"
            "ตัวเลขอ้างอิงจากรายการ 'ข้อมูลอ้างอิง' ต้องมี '— ที่มา: ...' ตามที่ระบุในรายการ\n"
            "ตัวเลขที่มาจาก 'เนื้อหาเทคนิค' (ตรวจข้อเท็จจริงแล้ว) ใช้ได้ตามเดิม "
            "ห้ามแต่งที่มาเพิ่ม\n"
            "ตัวเลขอื่นนอกสองแหล่งนี้ ให้เขียนว่า 'ประมาณการ' โดย**ไม่ใส่ที่มา "
            "และไม่อ้างชื่อมาตรฐานใด ๆ**\n"
            "ปิดท้ายด้วยตัวอย่างแทนค่าจริง 1 ชุด"
        ),
    ),
}

# Owner-approved 2026-10-01 (Tanet). Open question kept on the record: the
# IPCC 2006 natural-gas default of 56.1 t/TJ is normally cited as CO2, not
# CO2e — correct both this constant and the doc together if that is confirmed
# (a test fails if they drift). Do not add figures without a source.
# Human-readable copy: docs/references/th-energy-reference.md
REFERENCE_FIGURES = """
ตัวเลขอ้างอิงไทยที่อนุญาตให้ใช้ (ห้ามกุตัวเลขอื่นแล้วอ้างว่าเป็นมาตรฐาน):
- ค่าไฟเฉลี่ยภาคอุตสาหกรรม 4.2 บาท/kWh — ที่มา: PEA/MEA tariff 2569
- Emission factor ไฟฟ้า grid ไทย 0.4999 tCO2e/MWh — ที่มา: TGO CFO 2568
- Emission factor ก๊าซธรรมชาติ 56.1 tCO2e/TJ — ที่มา: IPCC 2006 Vol.2
- ค่าความร้อนก๊าซธรรมชาติ 39 MJ/m3 — ที่มา: PTT NGR spec sheet 2568
- อายุใช้งานหม้อไอน้ำอุตสาหกรรม 15–20 ปี — ที่มา: ASHRAE Equipment Life
ถ้าต้องใช้ตัวเลขนอกรายการนี้ ให้เขียนว่า "ประมาณการ" และห้ามอ้างมาตรฐานใด ๆ
"""

# A listed figure is "<number><unit>": 4.2 บาท/kWh, 0.4999 tCO2e/MWh,
# 15–20 ปี. The unit is the non-space run right after the number, which is
# what the list actually writes. Parsed out of REFERENCE_FIGURES itself so
# the editor gate and the list can never drift apart.
_FIGURE_VALUE_RE = re.compile(
    r"(\d[\d,.]*(?:\s*[–—-]\s*\d[\d,.]*)?)\s*([A-Za-zก-๙][^\s]*)"
)
_SOURCE_MARK = "— ที่มา"


def _match_form(text: str) -> str:
    """Whitespace- and dash-insensitive form used to match figures inside
    prose (Thai has no spaces, and a range may use '-' or '–')."""
    return re.sub(r"\s+", "", text).replace("–", "-").replace("—", "-")


def reference_figure_values() -> tuple[str, ...]:
    """Every number+unit token listed in REFERENCE_FIGURES, in match form."""
    values: list[str] = []
    for line in REFERENCE_FIGURES.splitlines():
        if not line.lstrip().startswith("-") or _SOURCE_MARK not in line:
            continue
        figure_part = line.split(_SOURCE_MARK)[0]
        for number, unit in _FIGURE_VALUE_RE.findall(figure_part):
            unit = unit.strip(".,;:)?")
            if unit:
                values.append(_match_form(number + unit))
    return tuple(dict.fromkeys(values))


def listed_figures_in(text: str) -> tuple[str, ...]:
    """Which REFERENCE_FIGURES values `text` actually quotes.

    Only those need a '— ที่มา:' tag (A7 + Task 8). Figures taken from the
    fact-checked technical content, and 'ประมาณการ' values, must NOT be
    given an invented source — so the gate must not ask for one.
    """
    haystack = _match_form(text)
    return tuple(v for v in reference_figure_values() if v in haystack)


LEVEL_GUIDE = {
    1: "L1 — พบครั้งแรก: นิยามศัพท์ให้ชัด ยกตัวอย่างเดียวที่เห็นภาพ ไม่ต้องลงลึกข้อยกเว้น",
    2: "L2 — เอาไปใช้: ต้องมีตัวอย่างคำนวณหรือขั้นตอนที่ทำตามได้จริงพร้อมตัวเลข",
    3: "L3 — ตัดสินใจเป็น: เน้น trade-off ว่าเลือกอะไรแลกอะไร และกรณีที่วิธีนี้ใช้ไม่ได้",
}

_SCENES_PLANT = ("โรงงานอาหารแช่แข็ง", "โรงงานกระดาษ", "โรงงานชิ้นส่วนยานยนต์",
                 "โรงงานสิ่งทอ", "โรงงานเซรามิก", "โรงงานยางแปรรูป")
_SCENES_BUILDING = ("โรงพยาบาล 24 ชั่วโมง", "โรงแรมริมทะเล", "อาคารสำนักงานให้เช่า",
                    "ศูนย์การค้าชุมชน", "ดาต้าเซ็นเตอร์ขนาดกลาง", "คลังสินค้าห้องเย็น")
_SCENES_PEOPLE = ("ฝ่ายจัดซื้อโรงงานชิ้นส่วนยานยนต์", "CFO กลุ่มค้าปลีก",
                  "ผู้รับเหมางานระบบ M&E", "วิศวกรโรงงานกระดาษ",
                  "ผู้จัดการอาคารสำนักงาน", "เจ้าของโรงแรมขนาดกลาง")

FORMAT_PROFILES = {
    "TECHNICAL": Profile(
        sections=(
            ("หน้างานบอกอะไร",
             "อาการหรือค่าที่มักเจอหน้างาน (ตัวอย่างประกอบ ไม่ใช่ข้อมูลจากไซต์จริง) และวิธีอ่านค่านั้นว่าแปลว่าอะไร"),
            ("เคสสั้น: จากอาการสู่ทางแก้",
             "ย่อหน้าเดียว ปัญหา → สิ่งที่ทำ → ผลลัพธ์เป็นตัวเลขพร้อม qualifier"),
        ),
        kit="checklist",
        scenes=_SCENES_PLANT + _SCENES_BUILDING,
    ),
    "INDUSTRY": Profile(
        sections=(
            ("โปรไฟล์ธุรกิจและ Energy Profile",
             "ธุรกิจนี้หาเงินยังไง ต้นทุนพลังงานคิดเป็นสัดส่วนเท่าไร ใช้พลังงานไปกับอะไรมากสุด"),
            ("สามจุดปวดที่ขายได้",
             "จุดปวด 3 ข้อ แต่ละข้อมีสัญญาณที่สังเกตได้ตอนเดินดูหน้างาน"),
        ),
        kit="questions",
        scenes=_SCENES_BUILDING + _SCENES_PEOPLE,
    ),
    "FRAMEWORK": Profile(
        sections=(
            ("โจทย์ที่กรอบนี้แก้",
             "สถานการณ์ที่ตัดสินใจยากโดยไม่มีกรอบ และกรอบนี้เข้ามาช่วยตรงไหน"),
            ("ลองใช้กับตัวอย่างทีละขั้น",
             "worked example เดินทีละขั้นจนได้ข้อสรุป พร้อมตัวเลขประกอบ"),
        ),
        kit="calculator",
        scenes=_SCENES_PEOPLE + _SCENES_PLANT,
    ),
    "SOFTSKILL": Profile(
        sections=(
            ("บทสนทนาตัวอย่าง",
             "บทสนทนา 4–6 บรรทัดสลับ ลูกค้า/ที่ปรึกษา ใช้ blockquote '> ' ทุกบรรทัด"),
            ("ถอดบทเรียน: ทำไมประโยคนั้นได้ผล",
             "ชี้ว่าประโยคไหนเปลี่ยนทิศบทสนทนา และหลักการเบื้องหลังคืออะไร"),
        ),
        kit="questions",
        scenes=_SCENES_PEOPLE + _SCENES_BUILDING,
    ),
    "COMPLIANCE": Profile(
        sections=(
            ("ข้อกำหนดที่ต้องรู้",
             "ใครต้องทำ ต้องทำอะไร ภายในเมื่อไร อ้างชื่อกฎหมายหรือมาตรฐานให้ตรง"),
            ("ถ้าไม่ทำเกิดอะไร",
             "บทลงโทษหรือต้นทุนที่ตามมา พร้อมเคสสั้นหนึ่งย่อหน้า"),
        ),
        kit="checklist",
        scenes=_SCENES_PLANT + _SCENES_PEOPLE,
    ),
    "SUSTAINABILITY": Profile(
        sections=(
            ("กฎและขอบเขตที่กระทบลูกค้า",
             "ขอบเขตการรายงานครอบคลุมอะไร และกระทบธุรกิจลูกค้าทางไหน"),
            ("ตัวเลขที่ต้องเก็บ",
             "ข้อมูลที่ต้องเก็บ เก็บจากไหน และแปลงเป็นผลลัพธ์ด้วยวิธีใด"),
        ),
        kit="calculator",
        scenes=_SCENES_PLANT + _SCENES_BUILDING,
    ),
}


def profile_for(pillar: str) -> Profile:
    """Unknown pillar falls back to TECHNICAL, matching ExpertAgent."""
    return FORMAT_PROFILES.get(pillar, FORMAT_PROFILES["TECHNICAL"])


def scene_for(day: date, industry: str, scenes: Sequence[str],
              recent: Sequence[str] = ()) -> str:
    """Pick a case scene deterministically (spec A2 / v1 §4).

    Same (day, industry, pool) always yields the same scene so the choice
    is testable, and scenes used on recent days are skipped so the reader
    does not meet the same factory manager twice in a row. The model never
    chooses.
    """
    if not scenes:
        raise ValueError("scene pool must not be empty")
    digest = hashlib.sha256(industry.encode("utf-8")).digest()
    start = (day.toordinal() + digest[0]) % len(scenes)
    rotated = list(scenes[start:]) + list(scenes[:start])
    for scene in rotated:
        if scene not in recent:
            return scene
    return rotated[0]  # pool smaller than the recent window
