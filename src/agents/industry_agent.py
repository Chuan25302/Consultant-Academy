"""
Industry Agent — adds Thai sector context to technical content.
Knows the 6 main industry families PTT NGR ESP serves.
"""
import logging

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

INDUSTRY_KNOWLEDGE = """\
ครอบครัวอุตสาหกรรมที่ PTT NGR ESP ครอบคลุม (Thai context):

1. **อาหาร / ยา / Cold Storage (Food / Pharma / Cold Chain)**
   - โรงงานแปรรูปอาหาร: cold chain, steam, CIP, HACCP
   - อาหารทะเลแปรรูป: blast freezer, IQF, brine
   - โรงงานยา: clean room, GMP/cGMP, WFI, critical uptime
   - โรงงานน้ำตาล: bagasse boiler, cogeneration, evaporator
   - Cold Storage: refrigeration cycle, door loss, defrost, NH3/CO2

2. **อุตสาหกรรมทั่วไป (General Manufacturing)**
   - เฟอร์นิเจอร์: dust collection, paint, pressing
   - เครื่องใช้ไฟฟ้า: stamping, paint, assembly
   - สิ่งทอ: dye house, drying

3. **ปิโตรเคมีและเคมีภัณฑ์ (Petrochem & Chemical)**
   - โรงกลั่นน้ำมัน: distillation, cracking, hydrogen plant
   - โรงงานพลาสติก: extrusion, injection mold, polymerization
   - โรงงานเคมีภัณฑ์: reactor, batch vs continuous, solvent recovery, scrubber

4. **อุตสาหกรรมหนัก (Heavy: Steel / Cement / Glass)**
   - เหล็กกล้า: EAF, rolling mill, reheating furnace
   - ซีเมนต์: kiln, raw mill, finish mill, preheater
   - แก้ว: melting furnace, regenerator, oxy-fuel, float bath, lehr

5. **ยานยนต์ครบวงจร (Automotive — OEM Full Vehicle + EV)** ⭐ Thailand "Detroit of Asia"
   - OEM assembly (Toyota/Honda/Isuzu/Mitsu/MG/BYD): stamping, body weld,
     paint shop (oven หลัก energy), trim, GA
   - EV plant: battery pack assembly, dry room, motor winding, dyno test
   - Engine plant: machining, heat treatment, casting
   - มาตรฐาน: IATF 16949 (QMS), VDA 6.3 (process audit)

6. **อิเล็กทรอนิกส์ขั้นสูง (Electronics — HDD / Semi packaging / PCB)** ⭐ ไทย world leader HDD
   - HDD plant (WD/Seagate): clean room class 100/1000, precision cooling
     (±0.5°C), magnetic shielding, ESD control
   - Semi packaging (ATP/OSAT): wire bond, mold, test, burn-in
   - PCB: SMT line, reflow oven, AOI, wave solder
   - มาตรฐาน: IPC, ESD S20.20, IATF (auto electronics)

7. **โรงพยาบาล (Hospitals)** ⭐ 24/7 critical, ต่างจากอาคารทั่วไป
   - Critical zones: OR (operating room), ICU, NICU — 100% backup, AIIR
   - HVAC pressurization (positive/negative), MERV/HEPA filtration
   - Medical gas: O2, vacuum, MA4 (medical air)
   - Sterilization: autoclave, ETO, hot water 70°C+
   - มาตรฐาน: ASHRAE 170, JCI, HA (สรพ.), WHO GMP

8. **โรงไฟฟ้า SPP/VSPP + Biomass/Biogas/Cogen** ⭐ energy producer
   - SPP cogeneration: gas turbine + HRSG + steam turbine (combined cycle)
   - Biomass: rice husk/bagasse boiler, fuel handling, ash
   - Biogas: anaerobic digester, gas cleaning, gen set
   - VSPP solar: PV, inverter, BESS
   - มาตรฐาน: ERC license, ASME I/IV, EHIA

9. **อาคารขนาดใหญ่ (Large Commercial Buildings + Data Center)**
   - โรงแรม / ห้าง / สำนักงาน: HVAC chiller plant, lighting, plug load
   - Data Center (Equinix/STT/AIS): cooling load 60-70% of total, PUE focus,
     UPS, redundancy N+1/2N
   - มาตรฐาน: ASHRAE 90.1, LEED, BREEAM, TREES (TGBI), Uptime Tier I-IV,
     อาคารควบคุมตาม พ.ร.บ. 2535, BEC

10. **จัดการสิ่งปฏิกูล (Waste Management)**
    - คัดแยก/ฝังกลบ (ประเภท 105): conveyor, shredder, baler, landfill gas
    - ปรับคุณภาพของเสียรวม: aeration blower, pump, mixer, biogas

KPI energy intensity ที่แต่ละกลุ่มสนใจ:
- Food: kWh/ton | Pharma: kWh/batch | Sugar: kWh/ตันอ้อย | Cold: kWh/m³·day
- Manufacturing: kWh/หน่วย | Refinery: kWh/บาเรล | Plastic: kWh/kg
- Chemical: kWh/ton สารผลิต
- Steel: kWh/ตันเหล็ก | Cement: kWh/ตันปูน | Glass: kWh/ตันแก้วหลอม
- Auto: kWh/คัน หรือ kWh/engine | EV: kWh/battery pack
- Electronics: kWh/wafer | HDD: kWh/drive
- Hospital: kWh/bed·day หรือ kWh/m²·yr
- SPP: heat rate (kJ/kWh), thermal efficiency %, capacity factor
- Buildings: EUI (kWh/m²·yr) | Data Center: PUE
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
