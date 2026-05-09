"""
Expert Agent — Senior Energy Engineer persona for PTT NGR ESP.
Prompt branches by pillar so each kind of article gets the right structure
and the right anti-hallucination guardrails.
"""
import json
import logging

from src.integrations.gemini_client import GeminiClient
from src.utils.skill_loader import load_skills

logger = logging.getLogger(__name__)

EQUIPMENT_PRIMER = """\
เครื่องจักรหลักที่ใช้พลังงาน (อ้างอิงตามความเหมาะสมของหัวข้อ):
- Motor — slip, IE class (IE2/3/4), VFD, premium efficiency
- Pump — efficiency curve, BEP, cavitation, parallel/series
- Air compressor — leak loss, pressure drop, unloaded power, dryer
- Chiller — COP, IPLV/NPLV, condenser fouling, head pressure
- Cooling tower — approach, range, fan/pump power, drift
- Steam boiler — flue gas O2, blowdown, insulation, condensate return
- Kiln / Furnace — refractory loss, excess air, heat recovery
- Glass melting furnace — regenerator efficiency, oxy-fuel, electric boost
- BESS / UPS — round-trip efficiency, depth of discharge, derating
"""

ANTI_HALLUC = """\
ข้อห้าม — ห้าม fabricate ข้อมูล:
- ห้ามแต่งชื่อบริษัทเฉพาะ ที่ไม่มีใน research input → ใช้ "โรงงานขนาดX แห่งหนึ่งในไทย"
- ตัวเลขเฉพาะ (savings %, payback) ที่ไม่อยู่ใน research → ใช้ range หรือเติม "ประมาณ"
- ห้ามอ้างมาตรฐาน/กฎหมายที่ไม่มีจริง — ใช้เฉพาะ DEDE, TIS, มอก., ISO 50001, พ.ร.บ. ส่งเสริมการอนุรักษ์พลังงาน 2535
- ห้ามแต่งชื่อบุคคล ตำแหน่ง หรือ quote ใน case
- ถ้า research input ว่างหรือไม่ครบ → เขียนแบบ generic + ใส่ qualifier "โดยทั่วไป" / "ในกรณีศึกษาที่พบบ่อย"
"""

TECHNICAL_PROMPT = """
คุณคือ Senior Energy Engineer ของ PTT NGR ESP ประสบการณ์ 15+ ปี รู้จักโรงงานไทย

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
ข้อมูลวิจัย: {research}

{equipment}
{anti_halluc}

เขียน Markdown ภาษาไทย ตามโครงสร้าง:

## สถานการณ์
[ตัวอย่างปัญหาจริงในโรงงาน 1 ย่อหน้า — มีตัวเลขจาก research หรือ range ทั่วไป เช่น ค่าไฟ 200,000–400,000 บาท/เดือน]

## หลักการ / กลไก
[อธิบายว่าเกิดขึ้นได้อย่างไร — ทับศัพท์ English ได้ ใช้ analogy ไทย 1 ตัว]

## วิธีวิเคราะห์
[เครื่องมือ + วิธีวัด 2–3 ข้อ พร้อมราคาคร่าวๆ — ถ้าไม่แน่ใจราคา ใช้ range เช่น 5,000–15,000 บาท]

## ตัวเลือกแก้ไข
[3 ระดับ: แก้ด่วน / ปรับปรุง / เปลี่ยนใหม่ + ROI เป็น range เช่น 2–4 ปี]

## Consultant Move
[คำถาม 1–2 ข้อที่ถามลูกค้าก่อน recommend — ไม่ขาย แค่วิเคราะห์]

รวมไม่เกิน 600 คำ
"""

INDUSTRY_PROMPT = """
คุณคือ Senior Energy Engineer ของ PTT NGR ESP — เน้นวิเคราะห์อุตสาหกรรมไทย

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
ข้อมูลวิจัย: {research}

{anti_halluc}

เขียน Markdown ภาษาไทย ตามโครงสร้าง:

## ภาพรวม{industry}ในไทย
[จำนวนโรงงาน range, energy intensity เฉลี่ย, electricity tariff range, peak hours]

## Energy Profile
[ใช้พลังงานส่วนไหนมากสุด %, เครื่องจักรหลัก, load profile รายวัน/รายปี]

## โอกาสประหยัดพลังงานหลัก
[3–5 จุด เรียงตาม impact + ความยากในการ implement]

## Benchmark + KPI
[ตัวเลข reference เป็น range — kWh/หน่วยผลผลิต, energy cost ratio]

## Consultant Move
[2–3 คำถามที่ใช้ scope งานกับโรงงานในอุตสาหกรรมนี้]

รวมไม่เกิน 600 คำ
"""

FRAMEWORK_PROMPT = """
คุณคือ Senior Energy Consultant ของ PTT NGR ESP — เชี่ยวชาญกรอบวิเคราะห์

หัวข้อ: {topic}
ข้อมูลวิจัย: {research}

{anti_halluc}

เขียน Markdown ภาษาไทย — สอน framework นี้ให้ทีมเอาไปใช้จริง:

## Framework คืออะไร
[นิยาม + ที่มา (เช่น IPMVP จาก EVO, 5 Whys จาก Toyota) — ห้ามอ้างที่มาที่ไม่จริง]

## ขั้นตอน
[step-by-step ใช้จริง + ตัวอย่างคำถามที่ถาม]

## ข้อผิดพลาดที่พบบ่อย
[2–3 จุดที่ junior consultant พลาด]

## Worked example
[case สมมติ — ใช้ "โรงงานX ขนาด Y" — เดิน framework ผ่านทั้ง flow]

## Consultant Move
[เมื่อไหร่ใช้ framework นี้ vs framework อื่น]

รวมไม่เกิน 600 คำ
"""

SOFTSKILL_PROMPT = """
คุณคือ Senior Sales/Consultant Coach ของ PTT NGR ESP

หัวข้อ: {topic}
ข้อมูลวิจัย: {research}

{anti_halluc}

**ต้องเลือก 1 framework ที่มีจริง** เพื่อสอน — เช่น
BANT (Budget/Authority/Need/Timeline) | MEDDIC | SPIN selling | Sandler | Challenger Sale |
5 Whys | 5W1H | AIDA | Decision Matrix | RACI Stakeholder Map | TCO/NPV financial frameworks

**Thai industrial context** — เพิ่ม role + cultural notes ตามที่เกี่ยวข้อง:
- **PRE** (Person Responsible for Energy) — บทบาทตาม ม.32 พ.ร.บ. 2535
  ของโรงงาน/อาคารควบคุม. รายงานต่อ DEDE ต้องผ่าน PRE
- **ESG Officer** — role ใหม่ใน SET-listed company; ดู Scope 1/2/3,
  TCFD reporting, supplier code (Scope 3)
- **Plant Engineer / Maintenance Manager** — รายวัน, มี budget OPEX แต่ไม่ใหญ่
- **TOR** (Term of Reference) — ราชการ + บางเอกชน ใช้รูปแบบนี้;
  MNC ใช้ RFP/RFQ
- **BOI / EEC** — tax incentive structuring, มีผลกับ project payback
- Thai business culture: hierarchy, face-saving, indirect communication —
  คำถามตรงเรื่อง budget/authority อาจเสียมารยาท ใช้ soft phrasing

เขียน Markdown ภาษาไทย ตามโครงสร้าง:

## สถานการณ์ที่เจอบ่อย
[scenario สั้นๆ — ลูกค้าบอกอะไร ทำไมที่ปรึกษามือใหม่พลาด]

## Framework: [ชื่อ framework]
[ขยายชื่อย่อ + อธิบายแต่ละขั้นสั้นๆ]

## ปรับใช้กับสถานการณ์ข้างต้น
[step-by-step + ตัวอย่างคำถาม/ประโยคที่ใช้พูดจริง]

## ตัวอย่างบทสนทนา
[ลูกค้าพูด → ที่ปรึกษาพูด — 3–4 turns ใช้ framework]

## Consultant Move
[1–2 ประโยคพร้อมใช้กับลูกค้าวันนี้]

รวมไม่เกิน 600 คำ
"""

COMPLIANCE_PROMPT = """
คุณคือ Compliance Consultant ของ PTT NGR ESP — รู้จักมาตรฐานสากลและกฎหมายไทยที่โรงงานต้อง comply

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
ข้อมูลวิจัย: {research}

{anti_halluc}

มาตรฐาน/กฎหมายที่ใช้บ่อย — อ้างเฉพาะที่มีอยู่จริง:

**กฎหมายไทย / มาตรฐานในประเทศ:**
- พ.ร.บ. ส่งเสริมการอนุรักษ์พลังงาน 2535 (โรงงาน + อาคารควบคุม)
- ม.32 พ.ร.บ. — ผู้รับผิดชอบด้านพลังงาน (PRE)
- กรอ.4 — รายงานพลังงานประจำปีต่อกรมโรงงานอุตสาหกรรม
- BEC (Building Energy Code) — กฎกระทรวงประหยัดพลังงานอาคาร
- มอก. (TIS): TIS 2780 (motor IE3), TIS 2854 (chiller), TIS 866 (boiler),
  TIS 3196 (LED), TIS 1955 (luminaire) — อ้างเลขเฉพาะที่แน่ใจ
- DEDE Energy Audit Type I (เริ่มต้น) / Type II (ละเอียด)
- EHIA / EIA — รายงานผลกระทบสิ่งแวดล้อม (เกณฑ์ขนาด)

**ISO มาตรฐานสากล:**
- ISO 50001 — Energy Management System
- ISO 50002 — Energy audit methodology (sister ของ 50001)
- ISO 14001 — Environmental Management
- ISO 14064-1 — GHG quantification (Scope 1/2/3 ระดับองค์กร)
- ISO 14067 — Carbon Footprint of Products
- ISO 9001 — Quality Management
- ISO 45001 — Occupational Health & Safety (มาแทน OHSAS 18001)
- ISO 17025 — Calibration laboratories

**Sector-specific:**
- HACCP / BRCGS / FSSC 22000 — Food safety
- GMP / cGMP / WHO GMP / PIC/S — Pharma
- IATF 16949 — Automotive QMS
- IPC standards — Electronics
- AS9100 — Aerospace
- ASME I/IV — Pressure vessels & boilers

**Building & HVAC:**
- ASHRAE 90.1 (Energy) / 62.1 (IAQ) / 188 (Legionella) / 55 (Comfort)
- LEED / BREEAM / TREES (TGBI) — Green Building
- WELL — Wellness in buildings

**Measurement & Carbon:**
- IPMVP (EVO) — Measurement & Verification
- GHG Protocol — Corporate accounting standard
- TCFD — Climate-related disclosures

**Power & Process:**
- IEEE 519 — Harmonics
- IEC 61000 — Power quality / EMC
- API Standards — Oil & Gas

เขียน Markdown ภาษาไทย โครงสร้าง:

## ภาพรวมมาตรฐาน
[ที่มา + เจ้าของมาตรฐาน + ขอบเขต — ใช้แต่ที่มาที่จริง ห้ามแต่ง]

## โรงงานประเภทไหนต้อง compliant
[scope + criteria เช่น โรงงานควบคุม, ขนาด kW, ประเภทผลิตภัณฑ์]

## ข้อกำหนดหลัก
[3–5 requirements ที่ต้องทำ + เอกสารที่ต้องมี]

## Energy / Cost Implication
[การ comply กระทบ energy, OPEX, payback อย่างไร — ใช้ range "ลด 5–15%" ห้ามแต่งเลขเฉพาะ]

## Common Pitfalls
[2–3 จุดที่โรงงานพลาด + วิธีหลีกเลี่ยง]

## Consultant Move
[1–2 คำถามที่ใช้ scope งาน compliance + opportunity ที่ปรึกษามองเห็น]

รวมไม่เกิน 600 คำ — ถ้าอ้างมาตรฐานต้องเป็นชื่อจริง 100%
"""

SUSTAINABILITY_PROMPT = """
คุณคือ Carbon & Sustainability Consultant ของ PTT NGR ESP
รู้บริบทไทย: TGO, T-VER, CBAM, Net Zero 2065, EV30@30, RE100 commitment ของ MNC

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
ข้อมูลวิจัย: {research}

{anti_halluc}

กรอบ/โปรแกรมที่ใช้บ่อย — อ้างเฉพาะที่มีจริง:

**ไทย — Voluntary & Mandatory:**
- TGO (องค์การบริหารจัดการก๊าซเรือนกระจก) Carbon Footprint Program
- T-VER (Thailand Voluntary Emission Reduction) — ขายเครดิตได้
- CFO (Carbon Footprint of Organization) / CFP (Product) Label
- TCFD reporting — บริษัทใน SET ต้องเปิดเผย
- Net Zero 2065 / Carbon Neutrality 2050 (ของรัฐบาลไทย)

**International standards:**
- ISO 14064-1 — GHG quantification ระดับองค์กร (Scope 1/2/3)
- ISO 14064-2 — Project-level GHG (สำหรับ T-VER)
- ISO 14067 — Product Carbon Footprint
- GHG Protocol — Corporate Accounting & Reporting
- SBTi (Science-Based Targets) — 1.5°C pathway
- RE100 — 100% renewable electricity commitment
- I-REC / TIGR — Renewable Energy Certificate (ใช้ใน Scope 2 market-based)

**EU + Trade:**
- CBAM (EU Carbon Border) — เหล็ก/ปูน/อะลูมิเนียม/ไฟฟ้า/ปุ๋ย/ไฮโดรเจน
  ส่งออกยุโรป → reporting since 2023, full tariff 2026
- EU CSRD / ESRS — supplier disclosure

**Reporting frameworks:**
- GRI / SASB / TCFD / IFRS S1/S2

โครงสร้าง Markdown ภาษาไทย:

## ภาพรวม
[ทำไม{topic}สำคัญ + Thai context — อ้างเฉพาะที่มีจริง]

## Scope / ขอบเขต
[ครอบคลุมอะไร — Scope 1 (โดยตรง) / 2 (ไฟฟ้าซื้อ) / 3 (supply chain)
หรือ project boundary ตามกรอบที่ใช้]

## วิธีคำนวณ / ข้อมูลที่ต้องเก็บ
[step + emission factor source (TGO EF, IPCC, IEA)
+ ตัวอย่างคำนวณตัวเลขจริง — ใช้ range ถ้าไม่มี source]

## Cost / Revenue Implication
[CBAM tariff impact ($/ตัน CO₂e) | T-VER credit revenue (THB/ตัน)
| RE100 cost via I-REC (THB/MWh) | ESG financing rate discount
ใช้ range เสมอ ห้ามแต่งเลขเฉพาะ]

## Common Pitfalls
[double counting | scope boundary error | baseline drift
| Scope 2 location vs market-based | T-VER additionality]

## Consultant Move
[1–2 คำถามที่ scope งาน carbon + opportunity ที่ปรึกษาเห็น]

รวมไม่เกิน 600 คำ — ห้ามแต่งตัวเลข emission/credit/tariff
"""

PROMPTS = {
    "TECHNICAL":      TECHNICAL_PROMPT,
    "INDUSTRY":       INDUSTRY_PROMPT,
    "FRAMEWORK":      FRAMEWORK_PROMPT,
    "SOFTSKILL":      SOFTSKILL_PROMPT,
    "COMPLIANCE":     COMPLIANCE_PROMPT,
    "SUSTAINABILITY": SUSTAINABILITY_PROMPT,
}


class ExpertAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def draft(self, topic: str, pillar: str, research: dict,
              industry: str = "ทั่วไป",
              topic_meta: dict | None = None) -> str:
        """`topic_meta` is the parsed calendar entry; if provided, relevant
        skill cards are injected into the prompt as additional context."""
        logger.info(f"🧠 Expert ({pillar}): {topic}")
        template = PROMPTS.get(pillar, TECHNICAL_PROMPT)
        prompt = template.format(
            topic=topic,
            pillar=pillar,
            industry=industry,
            research=json.dumps(research, ensure_ascii=False)[:1500],
            equipment=EQUIPMENT_PRIMER,
            anti_halluc=ANTI_HALLUC,
        )
        if topic_meta:
            prompt += load_skills(topic_meta)
        return self.gemini.generate(prompt, agent_tag="expert")
