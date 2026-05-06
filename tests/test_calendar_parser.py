from datetime import datetime

from src.utils.calendar_parser import CalendarParser

SAMPLE = """
# Calendar
- **2024-05-06**: TECHNICAL | Chiller 101 | Hospitality | chiller,COP
- **2024-05-07**: INDUSTRY | Hotel Energy Profile | Hospitality | hotel,cooling
- **2024-05-08**: FRAMEWORK | 5W1H | General | audit
- **2024-05-09**: SOFTSKILL | Budget Objection | General |
- **2024-05-10**: RECAP | สรุป | General | recap
- **2024-05-13**: TECHNICAL | Topic with no industry
"""


def _date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def test_parse_full_row():
    t = CalendarParser(SAMPLE).get_topic(_date("2024-05-06"))
    assert t["pillar"] == "TECHNICAL"
    assert t["topic"] == "Chiller 101"
    assert t["industry"] == "Hospitality"
    assert t["keywords"] == ["chiller", "COP"]


def test_pillar_uppercased():
    md = "- **2024-05-06**: technical | x | y | z"
    t = CalendarParser(md).get_topic(_date("2024-05-06"))
    assert t["pillar"] == "TECHNICAL"


def test_missing_date_returns_none():
    assert CalendarParser(SAMPLE).get_topic(_date("2024-12-31")) is None


def test_partial_row_no_industry_no_keywords():
    t = CalendarParser(SAMPLE).get_topic(_date("2024-05-13"))
    assert t["pillar"] == "TECHNICAL"
    assert t["topic"] == "Topic with no industry"
    assert t["industry"] == "General"
    assert t["keywords"] == []


def test_empty_keywords_field():
    t = CalendarParser(SAMPLE).get_topic(_date("2024-05-09"))
    # Trailing pipe with empty keyword section → split produces [""]
    assert t["pillar"] == "SOFTSKILL"
    assert t["industry"] == "General"


def test_recap_pillar():
    t = CalendarParser(SAMPLE).get_topic(_date("2024-05-10"))
    assert t["pillar"] == "RECAP"


def test_date_carries_through():
    d = _date("2024-05-06")
    t = CalendarParser(SAMPLE).get_topic(d)
    assert t["date"] == d
