from datetime import date
from unittest.mock import MagicMock

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


def _builder(articles=None, summaries=None):
    b = IndexBuilder(MagicMock(), MagicMock())
    b.collect_articles = MagicMock(return_value=articles or ARTICLES)
    b._load_summaries = MagicMock(return_value=summaries or SUMMARIES)
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
    b = _builder(summaries={"c": {"tldr": ""}})
    assert b.recall_candidates(TODAY, cluster="HVAC") == []


def test_drive_failure_returns_empty_instead_of_raising():
    b = _builder()
    b.collect_articles = MagicMock(side_effect=RuntimeError("drive down"))
    assert b.recall_candidates(TODAY, cluster="HVAC") == []


def test_age_boundary_3_days_included():
    """Age 3 (2026-10-12) should be included."""
    articles = [
        {"id": "x", "title": "Age 3", "date": "2026-10-12", "cluster": "Test", "level": 1},
    ]
    summaries = {"x": {"tldr": "Exactly 3 days old"}}
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="Test")
    assert [p["title"] for p in picked] == ["Age 3"]


def test_age_boundary_2_days_excluded():
    """Age 2 (2026-10-13) should be excluded."""
    articles = [
        {"id": "x", "title": "Age 2", "date": "2026-10-13", "cluster": "Test", "level": 1},
    ]
    summaries = {"x": {"tldr": "Only 2 days old"}}
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="Test")
    assert picked == []


def test_age_boundary_14_days_included():
    """Age 14 (2026-10-01) should be included."""
    articles = [
        {"id": "x", "title": "Age 14", "date": "2026-10-01", "cluster": "Test", "level": 1},
    ]
    summaries = {"x": {"tldr": "Exactly 14 days old"}}
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="Test")
    assert [p["title"] for p in picked] == ["Age 14"]


def test_age_boundary_15_days_excluded():
    """Age 15 (2026-09-30) should be excluded."""
    articles = [
        {"id": "x", "title": "Age 15", "date": "2026-09-30", "cluster": "Test", "level": 1},
    ]
    summaries = {"x": {"tldr": "15 days old"}}
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="Test")
    assert picked == []


def test_same_cluster_first_and_newest_first():
    """With two same-cluster in-window articles and one out-of-cluster newer,
    ensure same-cluster comes first, and within cluster, newest first."""
    articles = [
        {"id": "a", "title": "HVAC old", "date": "2026-10-06", "cluster": "HVAC", "level": 1},
        {"id": "b", "title": "HVAC new", "date": "2026-10-09", "cluster": "HVAC", "level": 1},
        {"id": "c", "title": "Other newer", "date": "2026-10-07", "cluster": "Other", "level": 1},
    ]
    summaries = {
        "a": {"tldr": "HVAC older"},
        "b": {"tldr": "HVAC newer"},
        "c": {"tldr": "Other also in window"},
    }
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="HVAC", limit=3)
    # Same cluster first (HVAC), then newest first within cluster, then fill from others (by recency)
    assert [p["title"] for p in picked] == ["HVAC new", "HVAC old", "Other newer"]


def test_summaries_failure_returns_empty():
    """When _load_summaries raises, return [] instead of raising."""
    b = _builder()
    b._load_summaries = MagicMock(side_effect=RuntimeError("summaries down"))
    assert b.recall_candidates(TODAY, cluster="HVAC") == []


def test_invalid_date_string_skipped():
    """Articles with invalid date strings should be skipped, not raise."""
    articles = [
        {"id": "x", "title": "Bad date", "date": "not-a-date", "cluster": "Test", "level": 1},
        {"id": "y", "title": "Good date", "date": "2026-10-08", "cluster": "Test", "level": 1},
    ]
    summaries = {
        "x": {"tldr": "Bad date article"},
        "y": {"tldr": "Good date article"},
    }
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="Test")
    assert [p["title"] for p in picked] == ["Good date"]
