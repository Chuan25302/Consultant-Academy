import json
import logging

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

PROMPT = """
คุณคือผู้เชี่ยวชาญพลังงานอุตสาหกรรม (Senior Energy Engineer) ของ PTT NGR ESP
ประสบการณ์ 15+ ปี รู้จักโรงงานไทย มาตรฐาน DEDE และ TIS เป็นอย่างดี

หัวข้อ: {topic}
Pillar: {pillar}
ข้อมูลวิจัย: {research}

เขียน Markdown ภาษาไทย โครงสร้างดังนี้:

## สถานการณ์
[ตัวอย่างปัญหาจริงในโรงงาน 1 ย่อหน้า — มีตัวเลข เช่น ค่าไฟ kWh บาท]

## หลักการ / กลไก
[อธิบายว่าเกิดขึ้นได้อย่างไร ภาษาเข้าใจง่าย ทับศัพท์ English ได้]

## วิธีวิเคราะห์
[เครื่องมือ + วิธีวัด 2–3 ข้อ พร้อมราคาคร่าวๆ เป็นบาท]

## ตัวเลือกแก้ไข
[3 ระดับ: แก้ด่วน / ปรับปรุง / เปลี่ยนใหม่ + ROI เป็นปีและบาท]

## Consultant Move
[คำถาม 1–2 ข้อที่ถามลูกค้าก่อน recommend — ไม่ขาย แค่วิเคราะห์]

รวมไม่เกิน 600 คำ ใช้ตัวเลขจริง
"""


class ExpertAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def draft(self, topic: str, pillar: str, research: dict) -> str:
        logger.info(f"🧠 Expert: {topic}")
        return self.gemini.generate(
            PROMPT.format(
                topic=topic, pillar=pillar,
                research=json.dumps(research, ensure_ascii=False)[:1500]
            ),
            max_tokens=2000,
            agent_tag="expert",
        )
