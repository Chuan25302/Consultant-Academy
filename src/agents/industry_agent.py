import logging
from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

PROMPT = """
คุณคือผู้เชี่ยวชาญด้านอุตสาหกรรมไทย รู้จักกระบวนการผลิตแต่ละ sector เป็นอย่างดี

Sectors ที่รู้จัก:
- โรงแรม: cooling load, occupancy, peak/off-peak, RevPAR
- โรงงานเหล็ก: EAF, rolling mill, high load factor, demand charge
- โรงงานเบฟเวอร์เรจ: chilling, compressed air, CIP, filling line
- โรงงานยา: clean room, GMP, critical uptime, FDA compliance
- โรงงานปูน: kiln, grinding, thermal recovery, heavy machinery
- โรงงานอาหาร: cold chain, steam, HACCP, CIP
- โรงงานน้ำ: pumping, aeration, membrane, municipal vs industrial
- โรงงานพลาสติก: extrusion, injection mold, cooling, cycle time

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
เนื้อหาเทคนิค: {expert_content}

เพิ่ม Markdown ภาษาไทย (ไม่เกิน 300 คำ):

## บริบท{industry}
[กระบวนการผลิตคร่าวๆ + ใช้พลังงานส่วนไหนมาก %]

## ความสำคัญของ{topic}ใน{industry}
[เชื่อมเทคโนโลยีกับ KPI ของ{industry}]

## ตัวอย่างโรงงาน{industry}
[scenario หรือ case จริงในไทย]
"""


class IndustryAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def contextualize(self, topic: str, industry: str, expert_content: str) -> str | None:
        if not industry or industry.lower() in ["general", "ทั่วไป"]:
            return None
        logger.info(f"🏭 Industry: {industry}")
        return self.gemini.generate(
            PROMPT.format(
                topic=topic, industry=industry,
                expert_content=expert_content[:1200]
            ),
            max_tokens=1500
        )
