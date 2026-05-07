import logging

from src.integrations.gemini_client import GeminiClient
from src.integrations.research_cache import ResearchCache

logger = logging.getLogger(__name__)

PROMPT = """
คุณคือ Research Agent ของ PTT NGR ESP
หน้าที่: รวบรวม benchmark + trend + กฎระเบียบ ของพลังงานอุตสาหกรรมไทย/ASEAN

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
Keywords: {keywords}

ข้อห้ามเด็ดขาด — ห้าม fabricate ข้อมูล:
- ห้ามแต่ง case study เฉพาะ ที่ไม่มาจากแหล่งที่เชื่อถือได้
- ห้ามแต่งตัวเลขเฉพาะ — ใช้ range เสมอ (เช่น 15–25% แทน 23%)
- ห้ามแต่งชื่อบริษัท/โรงงาน
- ห้ามอ้างกฎหมาย/มาตรฐานที่ไม่มีจริง — ใช้เฉพาะ DEDE, TIS, มอก., ISO 50001, พ.ร.บ. ส่งเสริมการอนุรักษ์พลังงาน 2535
- ถ้าไม่มี case study ที่เชื่อถือได้ → ตัด case_studies ออก ใส่ tools/tips แทน

ตอบเป็น JSON (ไม่มี markdown):
{{
  "case_studies": [
    {{"title": "ประเภทโครงการแบบทั่วไป (ไม่ระบุชื่อ)", "outcome": "ผลลัพธ์เป็น range เช่น ลด 15-25%", "savings_pct_range": "15-25", "payback_years_range": "2-4"}}
  ],
  "tools_tips": [
    "tool 1 ที่ใช้วัดผล + ราคา range",
    "tip 1 ที่ ที่ปรึกษาใช้ในไทย"
  ],
  "benchmarks": {{
    "energy_intensity_range": "2.0-3.5 kWh/หน่วย",
    "efficiency_std": "ชื่อมาตรฐานจริง (TIS, DEDE)",
    "tariff_thb_range": "3.5-4.8"
  }},
  "trends": ["trend 1", "trend 2", "trend 3"],
  "thai_regulations": ["DEDE", "TIS เลขที่จริง"]
}}

ถ้าไม่แน่ใจ case study ใดๆ — ส่ง array case_studies ว่าง [] แล้ว focus ที่ tools_tips แทน
"""


class ResearchAgent:
    def __init__(self, gemini: GeminiClient, cache: ResearchCache):
        self.gemini = gemini
        self.cache = cache

    def gather(self, topic: str, industry: str = None, keywords: list = None) -> dict:
        cached = self.cache.get(topic, industry)
        if cached:
            return cached

        logger.info(f"🔍 Researching: {topic} | {industry}")
        data = self.gemini.generate_json(
            PROMPT.format(
                topic=topic,
                industry=industry or "ทั่วไป",
                keywords=", ".join(keywords or [topic])
            ),
            agent_tag="research",
        )
        if not data:
            data = {
                "case_studies": [],
                "tools_tips": [],
                "benchmarks": {"tariff_thb_range": "3.5-4.8"},
                "trends": [],
                "thai_regulations": []
            }
        self.cache.set(topic, data, industry)
        return data
