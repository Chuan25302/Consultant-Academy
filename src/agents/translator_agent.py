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

Output format — Markdown ตรงๆ ห้ามเพิ่มคำนำหน้า:

สวัสดีทีมงาน Sales และ Technical ทุกท่าน

เป้าหมายของซีรีส์นี้คือการยกระดับทีมจากผู้เชี่ยวชาญเฉพาะด้าน สู่ Energy Consultant ที่ลูกค้าไว้วางใจในการให้คำปรึกษาแบบครบวงจร

## 1. {topic} ในมุมมอง Consultant

[อธิบายว่า "ลูกค้าต้องการอะไรจริงๆ" — ไม่ใช่แค่นิยามทางเทคนิค ใช้ภาษาเชิงกลยุทธ์]

## 2. Case Study

**Situation:** [โรงงานประเภทใด มีปัญหาอะไร ตัวเลขเริ่มต้น เช่น ค่าไฟ X บาท/เดือน]

**Complication:** [ปัญหาที่ซ่อนอยู่ที่ลูกค้ามองไม่เห็น — สาเหตุจริงไม่ใช่อาการ]

**Consultant's Approach:** [วิธีแก้ด้วย framework/มาตรฐาน/เทคนิคจากหัวข้อนี้ — bullet points]

**Result:** [ผลลัพธ์เป็นตัวเลข เช่น ลด X% ภายใน Y เดือน คืนทุน Z ปี]

## 3. Takeaways

**ทีม Sales:**
- [actionable insight เชิง business value / ROI / การ pitch]
- [actionable insight เพิ่มเติม]

**ทีม Technical:**
- [actionable insight เชิงการวิเคราะห์ / วัดผล / การแนะนำ solution]
- [actionable insight เพิ่มเติม]

📖 ศัพท์น่ารู้: [Term1 = คำแปล] | [Term2 = คำแปล] | [Term3 = คำแปล]

กฎ:
- ภาษาไทยเป็นหลัก ทับศัพท์ English ได้
- ตัวเลขในผลลัพธ์ต้องสมเหตุสมผล ใส่ qualifier เช่น "โดยประมาณ" "ในกรณีทั่วไป"
- ห้ามใส่ชื่อบริษัทจริง ใช้ "โรงงานผลิต X" แทน
- ไม่เกิน 600 คำ
- **ห้ามใส่ประโยคแนะนำตัวเอง** เช่น "ในฐานะ Senior Engineer", "ในฐานะนักสื่อสาร", "ผมขอแบ่งปัน", "ด้วยประสบการณ์..." — เริ่มต้นด้วย "สวัสดีทีมงาน..." แล้วเข้าเนื้อหาทันที
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
