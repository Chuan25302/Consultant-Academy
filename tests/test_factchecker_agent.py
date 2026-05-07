"""Tests for FactCheckerAgent — heuristic flags + LLM-skip-when-clean."""
from unittest.mock import MagicMock

from src.agents.factchecker_agent import FactCheckerAgent

CLEAN_CONTENT = """## สถานการณ์
โรงงานขนาดกลางในนิคมอุตสาหกรรมแห่งหนึ่ง ใช้พลังงานประมาณ 200,000 บาท/เดือน

## ตัวเลือกแก้ไข
- ลดการใช้พลังงานได้ประมาณ 15–25% ROI 2–4 ปี

## Consultant Move
ตรวจสอบ COP ปัจจุบัน

📖 ศัพท์น่ารู้: COP = ค่าประสิทธิภาพ
"""

DIRTY_CONTENT_COMPANY = """## สถานการณ์
บริษัท XYZ จำกัด ลด 23.5% หลังติดตั้ง chiller ใหม่ payback 2.7 ปี
"""

DIRTY_CONTENT_PERSON = """## สถานการณ์
คุณสมชาย ผู้จัดการโรงงาน บอกว่าประหยัดได้
"""

RESEARCH_DATA = {
    "case_studies": [],
    "tools_tips": ["data logger ราคา 5,000–15,000 บาท"],
    "benchmarks": {"tariff_thb_range": "3.5-4.8"},
}


def test_clean_content_skips_llm():
    gemini = MagicMock()
    fc = FactCheckerAgent(gemini)
    out = fc.review(CLEAN_CONTENT, RESEARCH_DATA)
    assert out == CLEAN_CONTENT
    gemini.generate.assert_not_called()


def test_company_mention_triggers_llm():
    gemini = MagicMock()
    gemini.generate.return_value = "FIXED CONTENT"
    fc = FactCheckerAgent(gemini)
    out = fc.review(DIRTY_CONTENT_COMPANY, RESEARCH_DATA)
    gemini.generate.assert_called_once()
    _, kwargs = gemini.generate.call_args
    assert kwargs["agent_tag"] == "factchecker"
    assert out == "FIXED CONTENT"


def test_person_name_triggers_llm():
    gemini = MagicMock()
    gemini.generate.return_value = "CLEANED"
    fc = FactCheckerAgent(gemini)
    fc.review(DIRTY_CONTENT_PERSON, RESEARCH_DATA)
    gemini.generate.assert_called_once()


def test_precise_numbers_without_qualifier_trigger_llm():
    gemini = MagicMock()
    gemini.generate.return_value = "CLEANED"
    fc = FactCheckerAgent(gemini)
    md = "ลด 27.3% หลังจาก 18 เดือน payback 1.4 ปี"
    fc.review(md, RESEARCH_DATA)
    gemini.generate.assert_called_once()


def test_qualifier_softens_precise_numbers():
    """If the precise number has 'ประมาณ' before it, no flag."""
    gemini = MagicMock()
    md = ("เนื้อหา ประมาณ 23% และเครื่องจักร "
          "## Consultant Move\nถาม\n📖 ศัพท์น่ารู้: x=y")
    fc = FactCheckerAgent(gemini)
    flags = fc._heuristic_flags(md, RESEARCH_DATA)
    assert not any(f.startswith("precise-percent") for f in flags)


def test_falls_back_to_original_on_llm_error():
    gemini = MagicMock()
    gemini.generate.return_value = "[Error: rate limit]"
    fc = FactCheckerAgent(gemini)
    out = fc.review(DIRTY_CONTENT_COMPANY, RESEARCH_DATA)
    assert out == DIRTY_CONTENT_COMPANY  # safer to keep original than crash


def test_numbers_in_research_are_not_flagged():
    """If the precise number was provided in research data, it's grounded."""
    gemini = MagicMock()
    research = {"benchmarks": {"x": "23.5%"}, "case_studies": []}
    md = ("ลด 23.5% เป็นค่าจริง "
          "## Consultant Move\nถาม\n📖 ศัพท์น่ารู้: x=y")
    fc = FactCheckerAgent(gemini)
    flags = fc._heuristic_flags(md, research)
    assert not any("23.5" in f for f in flags)


def test_flag_count_is_capped():
    """Don't flood logs with hundreds of flags."""
    gemini = MagicMock()
    md = "ลด " + " ".join(f"{n}%" for n in range(20, 50)) + " ครับ"
    fc = FactCheckerAgent(gemini)
    flags = fc._heuristic_flags(md, RESEARCH_DATA)
    assert len(flags) <= 10
