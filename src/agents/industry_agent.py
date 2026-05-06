"""
Industry Agent — adds Thai sector context to technical content.
Knows the 6 main industry families PTT NGR ESP serves.
"""
import logging

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

INDUSTRY_KNOWLEDGE = """\
6 ครอบครัวอุตสาหกรรมที่ PTT NGR ESP ครอบคลุม:

1. **อาหารและยา (Food & Medicine)**
   - โรงงานแปรรูปอาหาร: cold chain, steam, CIP, HACCP
   - โรงงานผลิตยา: clean room, GMP, WFI, critical uptime
   - โรงงานน้ำตาล: bagasse boiler, cogeneration, evaporator

2. **อุตสาหกรรมทั่วไป (General Manufacturing)**
   - ชิ้นส่วนยานยนต์: stamping, paint shop, assembly line
   - เครื่องใช้ไฟฟ้า/อิเล็กทรอนิกส์: SMT, soldering, clean room
   - เฟอร์นิเจอร์: dust collection, paint, pressing

3. **ปิโตรเคมีและเคมีภัณฑ์ (Petrochemicals)**
   - โรงกลั่นน้ำมัน: distillation, cracking, hydrogen plant
   - โรงงานพลาสติก: extrusion, injection mold, polymerization

4. **อุตสาหกรรมหนัก (Heavy Industry)**
   - เหล็กกล้า: EAF, rolling mill, reheating furnace
   - ซีเมนต์: kiln, raw mill, finish mill, preheater

5. **เหมืองแร่ (Mining)**
   - โม่/บด/ย่อยหิน: crusher, ball mill, conveyor
   - คัดแยกแร่: flotation, magnetic separator, dryer

6. **จัดการสิ่งปฏิกูล (Waste Management)**
   - คัดแยก/ฝังกลบ (ประเภท 105): conveyor, shredder, baler
   - ปรับคุณภาพของเสียรวม: aeration, pump, mixer, biogas

KPI ที่แต่ละกลุ่มสนใจ (วัด energy intensity ตามนี้):
- Food: kWh/ton สินค้า | Pharma: kWh/batch | Sugar: kWh/ตันอ้อย
- Manufacturing: kWh/หน่วย | Refinery: kWh/บาเรล | Plastic: kWh/kg
- Steel: kWh/ตันเหล็ก | Cement: kWh/ตันปูน
- Mining: kWh/ตันสินแร่ | Waste: kWh/ตันของเสีย
"""

ANTI_HALLUC = """\
ข้อห้าม:
- ห้ามแต่งชื่อโรงงานเฉพาะ → ใช้ "โรงงานในนิคมXXX" หรือ "โรงงานขนาด Y"
- ตัวเลขเฉพาะที่ไม่มีใน expert content → ใช้ range หรือ "ประมาณ"
- ห้ามอ้างกฎหมายที่ไม่มีจริง — เฉพาะ พ.ร.บ. ส่งเสริมการอนุรักษ์พลังงาน 2535, DEDE, TIS, มอก., ISO 50001
"""

PROMPT = """
คุณคือผู้เชี่ยวชาญด้านอุตสาหกรรมไทย ใส่บริบท sector ให้เนื้อหาเทคนิค

หัวข้อ: {topic}
อุตสาหกรรมเป้าหมาย: {industry}
เนื้อหาเทคนิคเดิม: {expert_content}

{industry_knowledge}

{anti_halluc}

เพิ่ม Markdown ภาษาไทย ขยายเฉพาะส่วนของอุตสาหกรรม{industry} (ไม่เกิน 300 คำ):

## บริบทอุตสาหกรรม {industry}
[กระบวนการผลิตคร่าวๆ + เครื่องจักรหลักที่ใช้พลังงาน + sub-sectors ที่เกี่ยวข้องในกลุ่มนี้]

## ทำไม{topic}สำคัญในอุตสาหกรรมนี้
[เชื่อมเทคโนโลยีกับ KPI ของ sector — production rate, downtime cost, compliance]

## บริบทการ apply ในไทย
[scenario ตัวอย่าง: โรงงานไหน ขนาดไหน เจอปัญหานี้บ่อยที่สุด — ใช้คำกว้างๆ ห้ามชื่อบริษัท]
"""


class IndustryAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def contextualize(self, topic: str, industry: str,
                      expert_content: str) -> str | None:
        if not industry or industry.lower() in ["general", "ทั่วไป"]:
            return None
        logger.info(f"🏭 Industry: {industry}")
        return self.gemini.generate(
            PROMPT.format(
                topic=topic, industry=industry,
                expert_content=expert_content[:1200],
                industry_knowledge=INDUSTRY_KNOWLEDGE,
                anti_halluc=ANTI_HALLUC,
            ),
            max_tokens=1500,
            agent_tag="industry",
        )
