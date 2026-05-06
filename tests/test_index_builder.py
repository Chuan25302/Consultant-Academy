"""Tests for the Knowledge Base IndexBuilder."""
from unittest.mock import MagicMock

from src.utils.index_builder import (
    MASTER_INDEX_FILENAME,
    IndexBuilder,
    _parse_filename,
)


def test_parse_filename_new_format():
    p = _parse_filename("[L2] 2024-05-06 Chiller Efficiency 101.docx")
    assert p == {"level": 2, "date": "2024-05-06", "title": "Chiller Efficiency 101"}


def test_parse_filename_legacy_format():
    p = _parse_filename("2024-05-06 — TECHNICAL — Chiller 101.docx")
    assert p == {"level": 1, "date": "2024-05-06", "title": "Chiller 101"}


def test_parse_filename_html_extension():
    p = _parse_filename("[L1] 2024-05-06 Topic.html")
    assert p is not None and p["level"] == 1


def test_parse_filename_unknown_format_returns_none():
    assert _parse_filename("random-file.docx") is None
    assert _parse_filename("MASTER.md") is None


def _mock_settings():
    s = MagicMock()
    s.FOLDER_KNOWLEDGE_BASE = "kb-root"
    return s


def test_collect_articles_skips_master_index_and_unknown():
    drive = MagicMock()
    drive.walk.return_value = [
        {"name": MASTER_INDEX_FILENAME, "id": "x", "parent_path": "", "mime": "text/markdown"},
        {"name": "[L1] 2024-05-06 Chiller 101.docx", "id": "1",
         "parent_path": "01-Technical-Depth/HVAC-Chillers", "mime": "x"},
        {"name": "random.txt", "id": "2", "parent_path": "01-Technical-Depth", "mime": "x"},
    ]
    ib = IndexBuilder(drive, _mock_settings())
    articles = ib.collect_articles()
    assert len(articles) == 1
    assert articles[0]["pillar"] == "01-Technical-Depth"
    assert articles[0]["cluster"] == "HVAC-Chillers"
    assert articles[0]["level"] == 1


def test_render_empty_returns_placeholder():
    ib = IndexBuilder(MagicMock(), _mock_settings())
    md = ib.render([])
    assert "ยังไม่มีบทความ" in md


def test_render_groups_by_pillar_and_cluster():
    ib = IndexBuilder(MagicMock(), _mock_settings())
    articles = [
        {"level": 1, "date": "2024-05-06", "title": "Chiller 101", "id": "a",
         "pillar": "01-Technical-Depth", "cluster": "HVAC-Chillers", "filename": "x"},
        {"level": 2, "date": "2024-05-13", "title": "Cooling Tower", "id": "b",
         "pillar": "01-Technical-Depth", "cluster": "HVAC-Chillers", "filename": "x"},
        {"level": 1, "date": "2024-05-20", "title": "Motor 101", "id": "c",
         "pillar": "01-Technical-Depth", "cluster": "Motors-VFD", "filename": "x"},
        {"level": 1, "date": "2024-05-07", "title": "Hotel Profile", "id": "d",
         "pillar": "02-Industry-Business-Logic", "cluster": "Hospitality", "filename": "x"},
    ]
    md = ib.render(articles)

    # New-hire section lists all level-1 articles in date order
    nh = md.split("## 📂")[0]
    assert nh.index("Chiller 101") < nh.index("Hotel Profile") < nh.index("Motor 101")

    # Pillars and clusters are grouped
    assert "TECHNICAL — เนื้อหาเทคนิค (3)" in md
    assert "INDUSTRY — ตามอุตสาหกรรม (1)" in md
    assert "HVAC-Chillers (2)" in md
    assert "Motors-VFD (1)" in md
    assert "Hospitality (1)" in md

    # Each link points to a Drive viewer URL
    assert "drive.google.com/file/d/a/view" in md


def test_render_sorts_within_cluster_by_level_then_date():
    ib = IndexBuilder(MagicMock(), _mock_settings())
    articles = [
        {"level": 2, "date": "2024-05-06", "title": "B-L2-early", "id": "a",
         "pillar": "p", "cluster": "c", "filename": "x"},
        {"level": 1, "date": "2024-05-13", "title": "A-L1-late", "id": "b",
         "pillar": "p", "cluster": "c", "filename": "x"},
        {"level": 1, "date": "2024-05-06", "title": "C-L1-early", "id": "c",
         "pillar": "p", "cluster": "c", "filename": "x"},
    ]
    md = ib.render(articles)
    # Within the cluster table, L1 entries come before L2; within L1, earlier date first
    cluster_section = md.split("## 📂")[-1]
    assert cluster_section.index("C-L1-early") < cluster_section.index("A-L1-late") \
        < cluster_section.index("B-L2-early")


def test_rebuild_calls_update_or_create():
    drive = MagicMock()
    drive.walk.return_value = []
    drive.update_or_create.return_value = "fake-id"
    ib = IndexBuilder(drive, _mock_settings())
    result = ib.rebuild()
    drive.update_or_create.assert_called_once()
    args, kwargs = drive.update_or_create.call_args
    assert kwargs["filename"] == MASTER_INDEX_FILENAME
    assert kwargs["folder_id"] == "kb-root"
    assert kwargs["mime_type"] == "text/markdown"
    assert result == "fake-id"
