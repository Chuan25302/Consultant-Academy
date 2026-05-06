"""
Industry Agent — adds Thai sector context to technical content.
Knows the 6 main industry families PTT NGR ESP serves.
"""
import logging

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

INDUSTRY_KNOWLEDGE = """\
ครอบครัวอุตสาหกรรมที่ PTT NGR ESP ครอบคลุม:

1. **อาหารและยา + Cold Storage (Food / Pharma / Cold Chain)**
   - โรงงานแปรรูปอาหาร: cold chain, steam, CIP, HACCP
   - โรงงานผลิตยา: clean room, GMP/cGMP, WFI, critical uptime
   - โรงงานน้ำตาล: bagasse boiler, cogeneration, evaporator
   - Cold Storage / คลังห้องเย็น: refrigeration cycle, door loss, defrost, NH3/CO2

2. **อุตสาหกรรมทั่วไป (General Manufacturing)**
   - ชิ้นส่วนยานยนต์: stamping, paint shop, assembly line
   - เครื่องใช้ไฟฟ้า/อิเล็กทรอนิกส์: SMT, soldering, clean room
   - เฟอร์นิเจอร์: dust collection, paint, pressing

3. **ปิโตรเคมีและเคมีภัณฑ์ (Petrochemicals & Chemical)**
   - โรงกลั่นน้ำมัน: distillation, cracking, hydrogen plant
   - โรงงานพลาสติก: extrusion, injection mold, polymerization
   - โรงงานเคมีภัณฑ์: reactor, batch vs continuous, solvent recovery, scrubber

4. **อุตสาหกรรมหนัก (Heavy Industry)**
   - เหล็กกล้า: EAF, rolling mill, reheating furnace
   - ซีเมนต์: kiln, raw mill, finish mill, preheater
   - แก้ว (Glass Manufacturing): glass melting furnace, regenerator, oxy-fuel,
     float bath, annealing lehr, electric boost

5. **อาคารขนาดใหญ่ (Large Commercial Buildings)**
   - โรงแรม / โรงพยาบาล / ห้างสรรพสินค้า / อาคารสำนักงาน / Data Center
   - ใช้พลังงานหลัก: HVAC (chiller plant), lighting, plug load, lift/escalator
   - มาตรฐาน: ASHRAE 90.1, LEED, BREEAM, TREES (TGBI), อาคารควบคุมตาม พ.ร.บ. 2535

6. **จัดการสิ่งปฏิกูล (Waste Management)**
   - คัดแยก/ฝังกลบ (ประเภท 105): conveyor, shredder, baler
   - ปรับคุณภาพของเสียรวม: aeration blower, pump, mixer, biogas

KPI ที่แต่ละกลุ่มสนใจ (วัด energy intensity ตามนี้):
- Food: kWh/ton สินค้า | Pharma: kWh/batch | Sugar: kWh/ตันอ้อย
- Cold Storage: kWh/m³·day หรือ kWh/ton·day
- Manufacturing: kWh/หน่วย | Refinery: kWh/บาเรล | Plastic: kWh/kg
- Chemical: kWh/ton สารผลิต
- Steel: kWh/ตันเหล็ก | Cement: kWh/ตันปูน | Glass: kWh/ตันแก้วหลอม
- Buildings: kWh/m²·yr (EUI) | Data Center: PUE
- Waste: kWh/ตันของเสีย
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
