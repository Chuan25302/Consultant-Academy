"""Tests for RecapAgent — covers the deep-extraction rework that feeds
Mon–Fri post bodies into Gemini and emails the result.

No real Drive/SMTP/Vertex calls — everything is mocked."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

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


# ---------- RecapAgent.generate_and_upload ---------------------------------

from src.agents.recap_agent import RecapAgent  # noqa: E402


def _fake_settings():
    s = MagicMock()
    s.FOLDER_EMAIL_ARCHIVES = "archive_root_id"
    return s


def _saturday_2026_05_16():
    return datetime(2026, 5, 16, 9, 0, tzinfo=ZoneInfo("Asia/Bangkok"))


def _make_drive_with_week(bodies_by_date: dict[str, str]):
    """Build a MagicMock DriveAPI that returns one [Email] file for
    each Mon–Fri date that has a body in `bodies_by_date`."""
    drive = MagicMock()

    def list_by_prefix(prefix: str):
        # prefix is "[Email] YYYY-MM-DD"
        date = prefix.split(" ", 1)[1]
        if date in bodies_by_date:
            return [{"id": f"id-{date}", "name": f"{prefix} Topic.html"}]
        return []

    def download(file_id: str):
        date = file_id.replace("id-", "")
        return bodies_by_date.get(date, "")

    drive.list_files_by_prefix.side_effect = list_by_prefix
    drive.download_file.side_effect = download
    drive.get_or_create_folder.return_value = "month_folder_id"
    return drive


def test_generate_feeds_full_bodies_into_prompt():
    """The prompt sent to Gemini must contain Mon–Fri body text
    (not just titles). This is the core of the 'deep extraction'
    pivot — without body content the LLM can only hallucinate."""
    bodies = {
        "2026-05-11": "<p>Monday body — pump efficiency rule</p>",
        "2026-05-12": "<p>Tuesday body — compressor surge formula</p>",
        "2026-05-13": "<p>Wednesday body — heat exchanger NTU</p>",
        "2026-05-14": "<p>Thursday body — soft skill: discovery questions</p>",
        "2026-05-15": "<p>Friday body — case study takeaway</p>",
    }
    drive = _make_drive_with_week(bodies)
    gemini = MagicMock()
    gemini.generate.return_value = "## stub recap markdown"

    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>recap</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=True):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )

    assert gemini.generate.call_count == 1
    sent_prompt = gemini.generate.call_args.args[0]
    # Every day's body text must appear in the prompt:
    for body_snippet in [
        "pump efficiency rule", "compressor surge formula",
        "heat exchanger NTU", "discovery questions", "case study takeaway",
    ]:
        assert body_snippet in sent_prompt, f"missing in prompt: {body_snippet}"


def test_prompt_has_four_sections_and_anti_hallucination_guard():
    """The new prompt must define all four output sections AND tell the
    LLM not to invent formulas — that guard is the only thing keeping
    'Formulas & Heuristics' honest."""
    bodies = {"2026-05-11": "<p>x</p>"}  # minimal — just need one day
    drive = _make_drive_with_week(bodies)
    gemini = MagicMock()
    gemini.generate.return_value = "## stub"

    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>recap</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=True):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )

    sent_prompt = gemini.generate.call_args.args[0]
    assert "Key Takeaways" in sent_prompt
    assert "Knowledge Capture" in sent_prompt
    assert "Formulas & Heuristics" in sent_prompt
    assert "ใช้กับลูกค้าได้เลย" in sent_prompt
    # Anti-hallucination guard (free-form match — exact wording may vary):
    assert "ห้ามแต่ง" in sent_prompt or "อย่าแต่ง" in sent_prompt
