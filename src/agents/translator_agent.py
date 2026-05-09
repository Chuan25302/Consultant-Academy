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

[อธิบายว่า "ลูกค้าต้องการอะไรจริงๆ" — ไม่ใช่แค่นิยามทางเทคนิค ใช้ภาษาเชิงกลยุทธ์]

## 2. Case Study

**Situation:** [โรงงานประเภทใด มีปัญหาอะไร ตัวเลขเริ่มต้น เช่น ค่าไฟ X บาท/เดือน]

**Complication:** [ปัญหาที่ซ่อนอยู่ที่ลูกค้ามองไม่เห็น — สาเหตุจริงไม่ใช่อาการ]

> "ผู้จัดการโรงงานบอกเราว่า: '[ประโยคที่ลูกค้าน่าจะพูดในสถานการณ์นี้ — เช่น เครื่องเก่ายังใช้ได้อยู่ ทำไมต้องเปลี่ยน]'"

**Consultant's Approach:**

- [bullet 1 — วิธีแก้ด้วย framework/มาตรฐาน/เทคนิคจากหัวข้อนี้]
- [bullet 2]
- [bullet 3]

**Result:** [ผลลัพธ์เป็นตัวเลข เช่น ลด X% ภายใน Y เดือน คืนทุน Z ปี]

## 3. Consultant Move

[1–2 ประโยคพร้อมใช้กับลูกค้าวันนี้ — เช่น "ลองถามลูกค้ารายต่อไปว่า ระบบนี้ downtime กี่ชั่วโมงในรอบปีที่ผ่านมา"]

## 4. Takeaways

**ทีม Sales:**

- [actionable insight เชิง business value / ROI / การ pitch]
- [actionable insight เพิ่มเติม]

**ทีม Technical:**

- [actionable insight เชิงการวิเคราะห์ / วัดผล / การแนะนำ solution]
- [actionable insight เพิ่มเติม]

## 📖 ศัพท์น่ารู้

- [Term1] = [คำแปล / นิยามสั้นๆ]
- [Term2] = [คำแปล / นิยามสั้นๆ]
- [Term3] = [คำแปล / นิยามสั้นๆ]

กฎ:
- **ห้ามใส่คำทักทาย** เช่น "สวัสดีทีมงาน Sales..." — เริ่มต้นด้วย "## 💡 ประเด็นวันนี้" ตรงๆ
- **ห้ามใส่ประโยคแนะนำตัวเอง** เช่น "ในฐานะ Senior Engineer", "ผมขอแบ่งปัน", "ด้วยประสบการณ์..."
- **ห้ามใส่ tagline** เกี่ยวกับ "ยกระดับทีม" หรือ "เป้าหมายซีรีส์" — Designer ใส่ใน footer แล้ว
- ภาษาไทยเป็นหลัก ทับศัพท์ English ได้
- ตัวเลขในผลลัพธ์ต้องสมเหตุสมผล ใส่ qualifier เช่น "โดยประมาณ" "ในกรณีทั่วไป"
- ห้ามใส่ชื่อบริษัทจริง ใช้ "โรงงานผลิต X" แทน
- ไม่เกิน 600 คำ
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
                expert_content=expert_content[:1500],
                industry_context=industry_context[:400] if industry_context else "ไม่มี"
            ),
            agent_tag="translator",
        )
