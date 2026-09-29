from datetime import date
from unittest.mock import MagicMock, patch

from src.utils.index_builder import IndexBuilder

TODAY = date(2026, 10, 15)
ARTICLES = [
    {"id": "a", "title": "Chiller COP", "date": "2026-10-14", "cluster": "HVAC", "level": 1},
    {"id": "b", "title": "Pump curves", "date": "2026-10-10", "cluster": "Pump", "level": 2},
    {"id": "c", "title": "Cooling tower", "date": "2026-10-08", "cluster": "HVAC", "level": 2},
    {"id": "d", "title": "Ancient post", "date": "2026-08-01", "cluster": "HVAC", "level": 1},
]
SUMMARIES = {
    "a": {"tldr": "COP บอกประสิทธิภาพ chiller"},
    "b": {"tldr": "เลือกปั๊มต้องดูจุดทำงานจริง"},
    "c": {"tldr": "คูลลิ่งทาวเวอร์ทิ้งความร้อน"},
    "d": {"tldr": "ของเก่ามาก"},
}


def _builder():
    b = IndexBuilder(MagicMock(), MagicMock())
    b.collect_articles = MagicMock(return_value=ARTICLES)
    b._load_summaries = MagicMock(return_value=SUMMARIES)
    return b


def test_skips_material_younger_than_three_days():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC")
    assert "Chiller COP" not in [p["title"] for p in picked]


def test_skips_material_older_than_fourteen_days():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC")
    assert "Ancient post" not in [p["title"] for p in picked]


def test_prefers_the_same_cluster_then_fills_from_others():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC", limit=2)
    assert [p["title"] for p in picked] == ["Cooling tower", "Pump curves"]


def test_entries_carry_their_tldr():
    picked = _builder().recall_candidates(TODAY, cluster="HVAC", limit=1)
    assert picked[0]["tldr"] == "คูลลิ่งทาวเวอร์ทิ้งความร้อน"


def test_articles_without_a_tldr_are_not_offered():
    b = _builder()
    b._load_summaries = MagicMock(return_value={"c": {"tldr": ""}})
    assert b.recall_candidates(TODAY, cluster="HVAC") == []


def test_drive_failure_returns_empty_instead_of_raising():
    b = _builder()
    b.collect_articles = MagicMock(side_effect=RuntimeError("drive down"))
    assert b.recall_candidates(TODAY, cluster="HVAC") == []
