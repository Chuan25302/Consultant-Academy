import logging

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

PROMPT = """
คุณคือนักสื่อสารของ PTT NGR ESP
แปลงเนื้อหาเทคนิคให้อ่านง่าย เข้าใจได้ใน 5 นาที

กฎ:
1. ภาษาไทยเป็นหลัก ทับศัพท์ English ได้ เช่น motor, chiller, COP, ROI
2. ประโยคสั้น เฉลี่ย 15 คำ
3. เพิ่ม analogy ไทย 1 ตัว เช่น "motor slip เหมือนจักรยานที่โซ่หลวม — ปั่นแต่ไม่ไปไหน"
4. ใช้ตัวเลขจริง (บาท, kWh, %, ปี)
5. จบด้วย Consultant Move ที่ใช้กับลูกค้าได้ทันที
6. ไม่เกิน 500 คำ
7. บรรทัดสุดท้ายเป็น glossary:
   📖 ศัพท์น่ารู้: [Term1 = คำแปล] | [Term2 = คำแปล] | [Term3 = คำแปล]

หัวข้อ: {topic}
Pillar: {pillar}

เนื้อหาเทคนิค:
{expert_content}

บริบทอุตสาหกรรม:
{industry_context}
"""


class TranslatorAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def simplify(self, expert_content: str, industry_context: str,
                 topic: str, pillar: str) -> str:
        logger.info("✍️ Translator: simplifying to Thai")
        return self.gemini.generate(
            PROMPT.format(
                topic=topic, pillar=pillar,
                expert_content=expert_content[:1500],
                industry_context=industry_context[:400] if industry_context else "ไม่มี"
            ),
            max_tokens=2000,
            agent_tag="translator",
        )
