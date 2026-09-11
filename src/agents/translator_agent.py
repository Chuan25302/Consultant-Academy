import logging

from src.integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

PROMPT = """
คุณคือ Consultant Trainer ของ PTT NGR ESP
เขียน Knowledge Sharing email ในรูปแบบ Case Study เพื่อพัฒนาทีม Sales และ Technical

หัวข้อ: {topic}
Pillar: {pillar}
เนื้อหาเทคนิค: {expert_content}
บริบทอุตสาหกรรม: {industry_context}

Output format — Markdown ตรงๆ ห้ามเพิ่มคำนำหน้า ห้ามมีคำทักทาย ห้ามมี tagline:

## 💡 ประเด็นวันนี้

[1 ประโยคกระชับ ≤25 คำ — สรุปประเด็นสำคัญที่สุดของหัวข้อนี้ในเชิงกลยุทธ์ที่ทีมเอาไปใช้กับลูกค้าได้ทันที — ห้ามขึ้นต้นด้วย "วันนี้..." หรือ "บทความนี้..."]

## 1. {topic} ในมุมมอง Consultant

[2 ย่อหน้า: (1) "ลูกค้าต้องการอะไรจริงๆ" — ไม่ใช่แค่นิยามทางเทคนิค ใช้ภาษาเชิงกลยุทธ์ (2) ทำไมเรื่องนี้กระทบธุรกิจลูกค้า — ต้นทุน / ความเสี่ยง / กฎระเบียบ พร้อมตัวเลขอ้างอิงจากเนื้อหาเทคนิคอย่างน้อย 1 จุด]

## 2. Case Study

**Situation:** [โรงงานประเภทใด ขนาดเท่าไร มีปัญหาอะไร — ตัวเลขเริ่มต้นอย่างน้อย 2 ตัวพร้อมหน่วย เช่น ค่าไฟ X บาท/เดือน, ใช้พลังงาน Y kWh/ปี]

**Complication:** [ปัญหาที่ซ่อนอยู่ที่ลูกค้ามองไม่เห็น — สาเหตุจริงไม่ใช่อาการ]

> "ผู้จัดการโรงงานบอกเราว่า: '[ประโยคที่ลูกค้าน่าจะพูดในสถานการณ์นี้ — เช่น เครื่องเก่ายังใช้ได้อยู่ ทำไมต้องเปลี่ยน]'"

**ตอบลูกค้าอย่างไร:** [1–2 ประโยคที่ที่ปรึกษาใช้ตอบ objection ข้างบน — อ้างตัวเลขหรือความเสี่ยงที่ลูกค้าจับต้องได้]

**Consultant's Approach:**

- [bullet 1 — ทำอะไร (framework/มาตรฐาน/เทคนิคจากหัวข้อนี้) → ทำไมได้ผล → วัดผลด้วยตัวชี้วัดอะไร]
- [bullet 2 — รูปแบบเดียวกัน]
- [bullet 3 — รูปแบบเดียวกัน]
- [bullet 4 — ถ้ามี]

**Result:** [ผลลัพธ์เป็นตัวเลขเทียบก่อน/หลัง เช่น ลด X% ภายใน Y เดือน คืนทุน Z ปี — พร้อม qualifier]

## 3. Consultant Move

[1–2 ประโยคพร้อมใช้กับลูกค้าวันนี้ — เช่น "ลองถามลูกค้ารายต่อไปว่า ระบบนี้ downtime กี่ชั่วโมงในรอบปีที่ผ่านมา"]

## 4. Takeaways

**ทีม Sales:**

- [actionable insight เชิง business value / ROI / การ pitch — ระบุคำถามหรือตัวเลขที่ใช้ได้จริง]
- [actionable insight เพิ่มเติม]
- [actionable insight เพิ่มเติม — ถ้ามี]

**ทีม Technical:**

- [actionable insight เชิงการวิเคราะห์ / วัดผล / การแนะนำ solution — ระบุเครื่องมือ ข้อมูล หรือเกณฑ์ที่ใช้]
- [actionable insight เพิ่มเติม]
- [actionable insight เพิ่มเติม — ถ้ามี]

## 5. Knowledge Capture

[1-2 ประโยคสรุปประเด็นหลักที่ที่ปรึกษาควรจำให้ได้ตลอด — เปรียบเสมือน "การ์ดสรุป" ที่ดึงออกมาใช้ได้ทันที]

**Key formulas / heuristics:**

- [Formula หรือ rule of thumb 1 — เช่น "TCO = CapEx + Σ(OpEx_n / (1+r)^n) ตลอด N ปี"]
- [Formula หรือ rule of thumb 2 — เช่น "Payback ที่คุ้ม < ½ ของอายุการใช้งาน"]
- [Formula หรือ rule of thumb 3 — ถ้ามี]

## 📖 ศัพท์น่ารู้

- [Term1] = [คำแปล / นิยามสั้นๆ]
- [Term2] = [คำแปล / นิยามสั้นๆ]
- [Term3] = [คำแปล / นิยามสั้นๆ]

กฎ:
- **ห้ามใส่คำทักทาย** เช่น "สวัสดีทีมงาน Sales..." — เริ่มต้นด้วย "## 💡 ประเด็นวันนี้" ตรงๆ
- **ห้ามใส่ประโยคแนะนำตัวเอง** เช่น "ในฐานะ Senior Engineer", "ผมขอแบ่งปัน", "ด้วยประสบการณ์..."
- **ห้ามใส่ tagline** เกี่ยวกับ "ยกระดับทีม" หรือ "เป้าหมายซีรีส์" — Designer ใส่ใน footer แล้ว
- ภาษาไทยเป็นหลัก ทับศัพท์ English ได้
- **ห้ามใช้ LaTeX หรือ $...$** — เขียนหน่วยและสูตรเป็นข้อความธรรมดา เช่น tCO2e, kWh/ปี, TCO = CapEx + OpEx × N (อีเมลแสดง LaTeX ไม่ได้)
- ตัวเลขในผลลัพธ์ต้องสมเหตุสมผล ใส่ qualifier เช่น "โดยประมาณ" "ในกรณีทั่วไป"
- ห้ามใส่ชื่อบริษัทจริง ใช้ "โรงงานผลิต X" แทน
- ความยาวประมาณ 800–1,000 คำ (รวม Knowledge Capture + glossary) — ความยาวต้องมาจากสาระ (ตัวเลข วิธีทำ เหตุผล) ไม่ใช่คำฟุ่มเฟือยหรือการพูดซ้ำ
- **ใช้ข้อเท็จจริงและตัวเลขจาก "เนื้อหาเทคนิค" ก่อนเสมอ** — ห้ามกุตัวเลขที่ขัดกับเนื้อหาเทคนิค ถ้าต้องประมาณเองให้ใส่ qualifier
- **Knowledge Capture ต้องมี formula/heuristic อย่างน้อย 2 ข้อ** ที่ดึงออกมาใช้ได้ทันที — ถ้าหัวข้อเป็น softskill/communication ใช้ checklist 2-3 ข้อแทน formula
- **bullet ใช้ "- " (dash + space) เท่านั้น ห้ามใช้ "*" หรือ "•" เด็ดขาด** — markdown parser ในระบบรองรับเฉพาะ dash
- ทุก bullet ต้องอยู่บรรทัดของตัวเอง (ขึ้นบรรทัดใหม่ก่อน "- ")
- **Complication ต้องตามด้วย customer quote** ที่เป็น blockquote (ขึ้นต้นด้วย "> ") เสมอ — ใช้คำพูดที่ลูกค้าจริงน่าจะพูดในสถานการณ์นี้ (anonymous, ไม่อ้างชื่อ) เพื่อให้ทีม Sales/Technical จำได้ว่า objection แบบนี้แก้ยังไง
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
                # Whole fact-checked draft: it is the grounded source for the
                # Case Study numbers. Cap only as a runaway-input guard.
                expert_content=expert_content[:12000],
                industry_context=industry_context[:400] if industry_context else "ไม่มี"
            ),
            agent_tag="translator",
        )
