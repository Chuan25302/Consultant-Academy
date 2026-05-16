"""Tests for RecapAgent — covers the deep-extraction rework that feeds
Mon–Fri post bodies into Gemini and emails the result.

No real Drive/SMTP/Vertex calls — everything is mocked."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.recap_agent import _strip_html_to_text  # noqa: E402

# ---------- _strip_html_to_text --------------------------------------------

def test_strip_html_removes_tags_keeps_text():
    html = "<p>Hello <strong>world</strong></p>"
    assert _strip_html_to_text(html) == "Hello world"


def test_strip_html_drops_style_and_script_blocks():
    html = """
    <html><head><style>body{color:red}</style></head>
    <body><script>alert('x')</script><p>Real content</p></body></html>
    """
    out = _strip_html_to_text(html)
    assert "color:red" not in out
    assert "alert" not in out
    assert "Real content" in out


def test_strip_html_preserves_section_breaks():
    """Block-level tags should become newlines so the LLM sees that
    'Key Takeaway' is on its own line, not glued to the prior paragraph."""
    html = "<h2>Key Takeaway</h2><p>Pumps lose 2% per year</p><h2>Apply</h2>"
    out = _strip_html_to_text(html)
    lines = [ln for ln in out.splitlines() if ln]
    assert "Key Takeaway" in lines
    assert "Pumps lose 2% per year" in lines
    assert "Apply" in lines


def test_strip_html_decodes_entities():
    assert _strip_html_to_text("<p>A &amp; B</p>") == "A & B"


def test_strip_html_handles_empty_and_none():
    assert _strip_html_to_text("") == ""
    assert _strip_html_to_text(None) == ""


# ---------- _build_day_digest ----------------------------------------------

from src.agents.recap_agent import _build_day_digest  # noqa: E402


def test_build_day_digest_returns_stripped_body():
    drive = MagicMock()
    drive.download_file.return_value = "<p>Pump efficiency = head × flow / power</p>"
    file_dict = {"id": "abc123", "name": "[Email] 2026-05-11 Pump basics.html"}

    digest = _build_day_digest(file_dict, drive)

    drive.download_file.assert_called_once_with("abc123")
    assert digest == "Pump efficiency = head × flow / power"


def test_build_day_digest_returns_none_on_download_failure():
    drive = MagicMock()
    drive.download_file.side_effect = RuntimeError("Drive 503")
    file_dict = {"id": "x", "name": "[Email] 2026-05-12 Y.html"}

    assert _build_day_digest(file_dict, drive) is None


def test_build_day_digest_returns_none_on_empty_file():
    drive = MagicMock()
    drive.download_file.return_value = ""
    file_dict = {"id": "x", "name": "[Email] 2026-05-12 Y.html"}

    assert _build_day_digest(file_dict, drive) is None
