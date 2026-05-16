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
