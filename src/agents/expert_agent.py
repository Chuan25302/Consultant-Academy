"""
Expert Agent — Senior Energy Engineer persona for PTT NGR ESP.
Prompt branches by pillar so each kind of article gets the right structure
and the right anti-hallucination guardrails.
"""
import json
import logging

from src.integrations.gemini_client import GeminiClient

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

PROMPTS = {
    "TECHNICAL": TECHNICAL_PROMPT,
    "INDUSTRY":  INDUSTRY_PROMPT,
    "FRAMEWORK": FRAMEWORK_PROMPT,
    "SOFTSKILL": SOFTSKILL_PROMPT,
}


class ExpertAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def draft(self, topic: str, pillar: str, research: dict,
              industry: str = "ทั่วไป") -> str:
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
        return self.gemini.generate(
            prompt, max_tokens=2000, agent_tag="expert"
        )
