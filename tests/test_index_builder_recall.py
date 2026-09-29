import json
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


def test_malformed_article_skipped_good_articles_kept():
    """Multiple malformed articles should be skipped, leaving good articles
    intact (blast radius: bad row, not whole block). Multiple skips are logged."""
    articles = [
        {"id": "good1", "title": "Good article 1", "date": "2026-10-08", "cluster": "Test", "level": 1},
        {"id": "bad1", "title": "Bad article 1", "date": "2026-10-07", "cluster": "Test", "level": 1},
        {"id": "good2", "title": "Good article 2", "date": "2026-10-06", "cluster": "Test", "level": 1},
        {"id": "bad2", "date": "2026-10-05", "cluster": "Test", "level": 1},  # Missing title → KeyError
        {"id": "good3", "title": "Good article 3", "date": "2026-10-04", "cluster": "Test", "level": 1},
    ]
    summaries = {
        "good1": {"tldr": "First good article"},
        "bad1": {"tldr": None},  # None tldr will raise AttributeError on .strip()
        "good2": {"tldr": "Second good article"},
        # bad2 has no entry → summaries.get returns {}, which is fine
        "good3": {"tldr": "Third good article"},
    }
    picked = _builder(articles=articles, summaries=summaries).recall_candidates(TODAY, cluster="Test", limit=5)
    # Both bad articles are skipped; three good articles should be returned (newest first)
    assert [p["title"] for p in picked] == ["Good article 1", "Good article 2", "Good article 3"]


# --- scene history (Task 5) -------------------------------------------------

def _scene_builder(summaries):
    b = IndexBuilder(MagicMock(), MagicMock())
    b._load_summaries = MagicMock(return_value=summaries)
    return b


SCENES = {
    "a": {"scene": "S-old", "date": "2026-05-01"},
    "b": {"scene": "S-mid", "date": "2026-05-02"},
    "c": {"scene": "S-today", "date": "2026-05-04"},
    "d": {"tldr": "no scene", "date": "2026-05-03"},
}


def test_recent_scenes_newest_first_limited_and_skips_sceneless():
    rows = _scene_builder(SCENES).recent_scenes(limit=2)
    assert [r["scene"] for r in rows] == ["S-today", "S-mid"]


def test_recent_scenes_excludes_the_date_being_generated():
    rows = _scene_builder(SCENES).recent_scenes(limit=2, exclude_date="2026-05-04")
    assert [r["scene"] for r in rows] == ["S-mid", "S-old"]


def test_update_summary_stores_scene_and_date():
    b = IndexBuilder(MagicMock(), MagicMock())
    b._load_summaries = MagicMock(return_value={})
    b.update_summary("doc1", "tl", "h1", scene="S", date="2026-05-04")
    assert b._summaries_cache["doc1"] == {
        "tldr": "tl", "html_id": "h1", "scene": "S", "date": "2026-05-04"}


def test_update_summary_without_scene_keeps_old_record_shape():
    b = IndexBuilder(MagicMock(), MagicMock())
    b._load_summaries = MagicMock(return_value={})
    b.update_summary("doc1", "tl", "h1")
    assert b._summaries_cache["doc1"] == {"tldr": "tl", "html_id": "h1"}


def test_recent_scenes_ignores_records_dated_after_the_generated_date():
    summaries = dict(SCENES, e={"scene": "S-future", "date": "2026-05-06"})
    rows = _scene_builder(summaries).recent_scenes(limit=5, exclude_date="2026-05-03")
    assert [r["scene"] for r in rows] == ["S-mid", "S-old"]


# --- failed loads must never wipe stored summaries --------------------------

def _drive_builder(download):
    drive = MagicMock()
    drive._list.return_value = {"files": [{"id": "sum1"}]}
    drive.download_file.side_effect = download
    return IndexBuilder(drive, MagicMock()), drive


def test_failed_load_is_not_cached_and_is_retried():
    b, drive = _drive_builder([RuntimeError("drive down"),
                               '{"x": {"tldr": "kept"}}'])
    assert b._load_summaries() == {}
    assert b._summaries_cache is None
    assert b._load_summaries() == {"x": {"tldr": "kept"}}
    assert drive.download_file.call_count == 2


def test_update_summary_after_failed_load_does_not_write():
    b, drive = _drive_builder([RuntimeError("drive down")])
    assert b.update_summary("doc1", "tl", "h1", scene="S", date="2026-05-04") is None
    drive.update_or_create.assert_not_called()


def test_update_summary_after_failed_file_lookup_does_not_write():
    b, drive = _drive_builder([])
    drive._list.side_effect = RuntimeError("list down")
    assert b.update_summary("doc1", "tl", "h1") is None
    drive.update_or_create.assert_not_called()


def test_update_summary_with_absent_file_still_writes_first_record():
    drive = MagicMock()
    drive._list.return_value = {"files": []}
    b = IndexBuilder(drive, MagicMock())
    b.update_summary("doc1", "tl", "h1")
    drive.update_or_create.assert_called_once()


def test_a_listing_miss_does_not_wipe_stored_summaries_at_write_time():
    """`drive._list` succeeding with zero matches is not proof the file is
    absent (eventual consistency / permission blip / renamed parent). The
    branch widened the window: recent_scenes() loads summaries ~8 minutes
    before update_summary writes. The 'absent' verdict must therefore not be
    cached — the write re-queries and merges."""
    drive = MagicMock()
    drive._list.side_effect = [{"files": []}, {"files": [{"id": "sum1"}]}]
    drive.download_file.return_value = '{"old": {"tldr": "kept", "date": "2026-05-01"}}'
    b = IndexBuilder(drive, MagicMock())

    assert b.recent_scenes() == []          # first listing missed
    b.update_summary("doc1", "tl", "h1", scene="S", date="2026-05-04")

    written = json.loads(drive.update_or_create.call_args.kwargs["content"])
    assert written["old"] == {"tldr": "kept", "date": "2026-05-01"}
    assert written["doc1"]["tldr"] == "tl"


def test_a_truly_absent_summaries_file_is_still_created():
    """The genuine first-ever write must keep working."""
    drive = MagicMock()
    drive._list.return_value = {"files": []}
    b = IndexBuilder(drive, MagicMock())

    b.update_summary("doc1", "tl", "h1")

    written = json.loads(drive.update_or_create.call_args.kwargs["content"])
    assert written == {"doc1": {"tldr": "tl", "html_id": "h1"}}
    drive.download_file.assert_not_called()
