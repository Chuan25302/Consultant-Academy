import logging

from src.agents.formats import KIT_SPECS, LEVEL_GUIDE, REFERENCE_FIGURES, profile_for
from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

BASE_RULES = """
กฎ:
- **ห้ามใส่คำทักทาย** เช่น "สวัสดีทีมงาน Sales..." — เริ่มด้วย "## 💡 ประเด็นวันนี้" ตรง ๆ
- **ห้ามใส่ประโยคแนะนำตัวเอง** เช่น "ในฐานะ Senior Engineer", "ผมขอแบ่งปัน"
- **ห้ามใส่ tagline** เกี่ยวกับ "ยกระดับทีม" — Designer ใส่ใน footer แล้ว
- ภาษาไทยเป็นหลัก ทับศัพท์ English ได้
- **ห้ามใช้ LaTeX หรือ $...$** — เขียนหน่วยและสูตรเป็นข้อความธรรมดา เช่น tCO2e, kWh/ปี
- **ใช้ข้อเท็จจริงและตัวเลขจาก "เนื้อหาเทคนิค" ก่อนเสมอ** ถ้าประมาณเองให้ใส่ qualifier
- ห้ามใส่ชื่อบริษัทจริง
- **bullet ใช้ "- " เท่านั้น** ห้ามใช้ "*" หรือ "•" และทุก bullet ต้องอยู่บรรทัดของตัวเอง
- ความยาวเนื้อหาหลัก 600–700 คำ + เครื่องมือ ~150 คำ + ทวนของเก่า ~80 คำ
  ความยาวต้องมาจากสาระ ไม่ใช่คำฟุ่มเฟือย
"""

REFERENCE_LABEL = (
    "\nข้อมูลอ้างอิง (input เท่านั้น) — ห้ามคัดลอกทั้งตารางลงในอีเมล "
    "ใช้เฉพาะค่าที่เกี่ยวข้องกับหัวข้อ")

HEAD_TMPL = """
คุณคือ Consultant Trainer ของ PTT NGR ESP
เขียน Knowledge Sharing email เพื่อพัฒนาทีม Sales และ Technical

หัวข้อ: {topic}
Pillar: {pillar}
ระดับความลึก: {level_guide}
{scene_line}เนื้อหาเทคนิคที่ผ่านการตรวจแล้ว: {expert_content}
{reference_block}บริบทอุตสาหกรรม: {industry}

Output format — Markdown ตรง ๆ ห้ามมีคำนำหน้า:

## 💡 ประเด็นวันนี้

[1 ประโยค ≤25 คำ — ประเด็นเชิงกลยุทธ์ที่เอาไปใช้กับลูกค้าได้ทันที]

**หลักคิดวันนี้:** [≤2 ประโยค — หลักคิดเดียวที่ผู้อ่านต้องจำให้ได้
ทุกหัวข้อด้านล่างต้องรับใช้หลักคิดนี้ ถ้าอะไรไม่เกี่ยวให้ตัดทิ้ง]
"""

SECTION_TMPL = """
## {index}. {title}

[{intent}]
"""

TAIL_TMPL = """
## {cmove_index}. Consultant Move

[1–2 ประโยคพร้อมใช้กับลูกค้าวันนี้]

## 🧰 {kit_label}

{kit_instructions}

## {kc_index}. Knowledge Capture

[1–2 ประโยคสรุปหลักคิดวันนี้ให้จำได้]

**Key formulas / heuristics:**

- [formula หรือ rule of thumb 1]
- [formula หรือ rule of thumb 2]

## 📖 ศัพท์น่ารู้

- [Term1] = [นิยามสั้น]
- [Term2] = [นิยามสั้น]
- [Term3] = [นิยามสั้น]
"""

RECALL_TMPL = """
## 🔁 ทวนของเก่า

[2 คำถามจากบทความเก่าด้านล่าง — ถามให้ตอบจากความจำ ห้ามเฉลยตรงนี้
แต่ละคำถามขึ้นต้นด้วย "- " และลงท้ายด้วย "?"]

บทความเก่าที่ให้ใช้ตั้งคำถาม:
{recall_sources}

## 🔑 เฉลย

[เฉลย 2 ข้อตามลำดับ ข้อละ 1–2 ประโยค ขึ้นต้นด้วย "- "]
"""


def build_prompt(*, topic: str, pillar: str, level: int, industry: str,
                 expert_content: str, scene: str, recall_items=()) -> str:
    profile = profile_for(pillar)
    kit = KIT_SPECS[profile.kit]
    reference_block = (REFERENCE_LABEL + REFERENCE_FIGURES
                       if profile.kit == "calculator" else "")
    parts = [HEAD_TMPL.format(reference_block=reference_block,
        topic=topic, pillar=pillar,
        level_guide=LEVEL_GUIDE.get(int(level or 1), LEVEL_GUIDE[1]),
        scene_line=(f"ฉากที่ต้องใช้ในตัวอย่าง/เคส: **{scene}** "
                    "(ห้ามเปลี่ยนไปใช้ฉากอื่น)\n" if scene else ""),
        expert_content=expert_content[:12000],
        industry=industry or "ทั่วไป")]
    for i, (title, intent) in enumerate(profile.sections, start=1):
        parts.append(SECTION_TMPL.format(index=i, title=title, intent=intent))
    n = len(profile.sections)
    parts.append(TAIL_TMPL.format(cmove_index=n + 1, kc_index=n + 2,
                                  kit_label=kit.label,
                                  kit_instructions=kit.instructions))
    if recall_items:
        sources = "\n".join(
            f'- {it["title"]} ({it["date"]}): {it["tldr"]}' for it in recall_items)
        parts.append(RECALL_TMPL.format(recall_sources=sources))
    parts.append(BASE_RULES)
    return "\n".join(parts)


class TranslatorAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def simplify(self, expert_content: str, industry_context: str,
                 topic: str, pillar: str, *, level: int = 1,
                 industry: str = "ทั่วไป", scene: str = "",
                 recall_items=()) -> str:
        logger.info(f"✍️ Translator: {pillar} · L{level} · ฉาก {scene or '-'}")
        return self.gemini.generate(
            build_prompt(topic=topic, pillar=pillar, level=level,
                         industry=industry, expert_content=expert_content,
                         scene=scene, recall_items=recall_items),
            agent_tag="translator",
        )
