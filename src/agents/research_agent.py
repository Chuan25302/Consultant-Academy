import logging

from src.integrations.gemini_client import GeminiClient
from src.integrations.research_cache import ResearchCache

logger = logging.getLogger(__name__)

PROMPT = """
คุณคือ Research Agent ของ PTT NGR ESP
หน้าที่: รวบรวม case study + benchmark พลังงานอุตสาหกรรมในไทย/ASEAN

หัวข้อ: {topic}
อุตสาหกรรม: {industry}
Keywords: {keywords}

ตอบเป็น JSON (ไม่มี markdown):
{{
  "case_studies": [
    {{"title": "ชื่อโครงการ/โรงงาน", "outcome": "ผลลัพธ์", "savings_pct": 20, "payback_years": 2.5}},
    {{"title": "...", "outcome": "...", "savings_pct": 15, "payback_years": 3.0}}
  ],
  "benchmarks": {{
    "energy_intensity": "2.5 kWh/หน่วย",
    "efficiency_std": "TIS 2677 / DEDE มาตรฐาน IE3",
    "avg_tariff_thb": 4.5
  }},
  "trends": ["trend 1", "trend 2", "trend 3"],
  "thai_regulations": ["DEDE", "TIS ที่เกี่ยวข้อง"]
}}
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
                "benchmarks": {"avg_tariff_thb": 4.5},
                "trends": [],
                "thai_regulations": []
            }
        self.cache.set(topic, data, industry)
        return data
