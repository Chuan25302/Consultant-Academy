"""Tests for RecapAgent — covers the deep-extraction rework that feeds
Mon–Fri post bodies into Gemini and emails the result.

No real Drive/SMTP/Vertex calls — everything is mocked."""
from __future__ import annotations

import re
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


def test_strip_html_removes_email_chrome():
    """Email archive HTML wraps boilerplate (preheader, banner, footer)
    in known classes — those should not bleed into the LLM prompt."""
    html = '''
    <div class="preheader">hidden inbox preview text</div>
    <div class="km-banner">📖 อ่านบทความก่อนหน้า</div>
    <p>Real article body</p>
    <div class="ftr">PTT NGR ESP · footer</div>
    <div class="meta">Tue 12/5 · อ่าน 3 นาที</div>
    '''
    out = _strip_html_to_text(html)
    assert "Real article body" in out
    assert "preview text" not in out
    assert "อ่านบทความก่อนหน้า" not in out
    assert "footer" not in out
    assert "Tue 12/5" not in out


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


def test_multiple_emails_per_day_collapse_to_one_header():
    """If a single Mon–Fri date has two [Email] files (re-run / backfill
    case), the prompt should still have ONE day header for that date
    with both bodies under it — not two repeated date headers."""
    drive = MagicMock()

    def list_by_prefix(prefix: str):
        if prefix == "[Email] 2026-05-11":
            return [
                {"id": "id-mon-a", "name": f"{prefix} First.html"},
                {"id": "id-mon-b", "name": f"{prefix} Second.html"},
            ]
        return []

    drive.list_files_by_prefix.side_effect = list_by_prefix
    drive.download_file.side_effect = lambda fid: {
        "id-mon-a": "<p>First body</p>",
        "id-mon-b": "<p>Second body</p>",
    }.get(fid, "")
    drive.get_or_create_folder.return_value = "folder"

    gemini = MagicMock()
    gemini.generate.return_value = "## stub"

    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>r</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=True):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )

    sent_prompt = gemini.generate.call_args.args[0]
    # Both bodies present:
    assert "First body" in sent_prompt
    assert "Second body" in sent_prompt
    # But only ONE "11/5" date header (count occurrences of the day-header substring):
    assert sent_prompt.count("11/5") == 1, (
        f"expected one date header for Monday, got {sent_prompt.count('11/5')}"
    )


# ---------- email send -----------------------------------------------------

def test_sends_email_with_recap_subject_after_upload():
    bodies = {"2026-05-11": "<p>x</p>"}
    drive = _make_drive_with_week(bodies)
    gemini = MagicMock()
    gemini.generate.return_value = "## stub markdown"

    sent_email = MagicMock(return_value=True)
    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>recap-body</html>"), \
         patch("src.agents.recap_agent.send_daily_email", sent_email):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )

    # Upload happened first…
    drive.upload.assert_called_once()
    # …then the email went out:
    sent_email.assert_called_once()
    subject, html_body = sent_email.call_args.args[:2]
    assert subject.startswith("[Consultant Academy] สรุปสัปดาห์ที่")
    assert "2026-05-16" in subject
    # The email body is the same HTML we uploaded:
    assert html_body == "<html>recap-body</html>"


def test_dry_run_skips_upload_and_email():
    bodies = {"2026-05-11": "<p>x</p>"}
    drive = _make_drive_with_week(bodies)
    gemini = MagicMock()
    gemini.generate.return_value = "## stub markdown"

    sent_email = MagicMock(return_value=True)
    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>recap-body</html>"), \
         patch("src.agents.recap_agent.send_daily_email", sent_email):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=True,
        )

    drive.upload.assert_not_called()
    sent_email.assert_not_called()


def test_partial_download_failure_still_generates_recap():
    """If one Mon-Fri download fails, the recap should still generate
    from the other four - the team's weekly digest is more useful with
    4 days than zero days."""
    bodies = {
        "2026-05-11": "<p>Monday OK</p>",
        "2026-05-12": "<p>Tuesday OK</p>",
        "2026-05-13": None,                # this day will raise on download
        "2026-05-14": "<p>Thursday OK</p>",
        "2026-05-15": "<p>Friday OK</p>",
    }
    drive = MagicMock()

    def list_by_prefix(prefix: str):
        date = prefix.split(" ", 1)[1]
        if date in bodies:
            return [{"id": f"id-{date}", "name": f"{prefix} T.html"}]
        return []

    def download(file_id: str):
        date = file_id.replace("id-", "")
        if bodies[date] is None:
            raise RuntimeError("Drive 503 simulated")
        return bodies[date]

    drive.list_files_by_prefix.side_effect = list_by_prefix
    drive.download_file.side_effect = download
    drive.get_or_create_folder.return_value = "folder_id"

    gemini = MagicMock()
    gemini.generate.return_value = "## stub"

    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>r</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=True):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )

    # The recap still went out:
    drive.upload.assert_called_once()
    # And the prompt had four days of body content (not five, not zero):
    sent_prompt = gemini.generate.call_args.args[0]
    assert "Monday OK" in sent_prompt
    assert "Tuesday OK" in sent_prompt
    assert "Thursday OK" in sent_prompt
    assert "Friday OK" in sent_prompt
    assert "503" not in sent_prompt  # error wasn't accidentally fed to LLM


def test_gemini_error_aborts_before_upload_and_email():
    from src.integrations.gemini_client import LLMStageError

    drive = _make_drive_with_week({"2026-05-11": "<p>x</p>"})
    gemini = MagicMock()
    gemini.generate.return_value = "[Error: 503 UNAVAILABLE. model overloaded]"

    sent_email = MagicMock(return_value=True)
    with patch("src.agents.recap_agent.send_daily_email", sent_email), \
         pytest.raises(LLMStageError, match="recap"):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )

    drive.upload.assert_not_called()
    sent_email.assert_not_called()


def test_recap_email_send_failure_raises():
    from src.utils.email_sender import EmailNotSentError

    drive = _make_drive_with_week({"2026-05-11": "<p>x</p>"})
    gemini = MagicMock()
    gemini.generate.return_value = "## stub markdown"
    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>r</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=False), \
         patch("src.agents.recap_agent.email_configured", return_value=True), \
         pytest.raises(EmailNotSentError):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False,
        )


def _recap_prompt() -> str:
    drive = _make_drive_with_week({"2026-05-11": "<p>x</p>"})
    gemini = MagicMock()
    gemini.generate.return_value = "## stub"
    with patch("src.agents.recap_agent.DesignerAgent.create_recap_email",
               return_value="<html>r</html>"), \
         patch("src.agents.recap_agent.send_daily_email", return_value=True):
        RecapAgent(gemini, drive, _fake_settings()).generate_and_upload(
            today=_saturday_2026_05_16(), dry_run=False)
    return gemini.generate.call_args.args[0]


def test_recap_prompt_asks_for_retrieval_not_a_summary():
    prompt = _recap_prompt()
    assert "🔁 ทวนสัปดาห์นี้" in prompt and "🔑 เฉลย" in prompt
    assert "5 คำถาม" in prompt
    assert "Knowledge Capture" in prompt, "anchor must survive (renderer + site)"
    assert "Key Takeaways" not in prompt
    # answers live in their own section, after the questions
    assert prompt.index("🔁 ทวนสัปดาห์นี้") < prompt.index("🔑 เฉลย")


def test_recap_prompt_is_one_way_and_keeps_word_budget():
    prompt = _recap_prompt()
    # a reply/form request may appear only inside the prohibition sentences
    stripped = (prompt.replace("ห้ามขอให้ผู้อ่านตอบกลับอีเมล", "")
                      .replace("ห้ามขอให้กรอกฟอร์ม", ""))
    for term in ("ตอบกลับ", "ฟอร์ม", "reply", "Reply", "ส่งกลับ", "แจ้งกลับ",
                 "ส่งคำตอบ", "กรอก"):
        assert term not in stripped, f"one-way mail must not ask: {term}"
    assert "ห้ามขอให้ผู้อ่านตอบกลับอีเมล" in prompt
    assert "ไม่เกิน 500 คำ" in prompt
    assert "ทวนของเก่า" not in prompt, "daily wording must stay distinct"


def test_recap_prompt_keeps_anti_fabrication_rule():
    assert "ห้ามแต่ง" in _recap_prompt()


def _skeleton_from_prompt() -> str:
    """Headings exactly as the prompt tells the LLM to emit them."""
    from src.agents.recap_agent import PROMPT
    lines = []
    for line in PROMPT.splitlines():
        if re.match(r"^#{2,3} ", line):
            lines += [line.replace("{week}", "20"), "", "- x", ""]
    return "\n".join(lines)


def test_recap_markdown_renders_recall_kcapture_answers_as_sibling_boxes():
    from src.agents.designer_agent import DesignerAgent
    html = DesignerAgent.create_recap_email(
        _skeleton_from_prompt(), 20,
        [{"day_th": "จ", "topic": "t", "date_th": "11 พ.ค."}],
        _saturday_2026_05_16())
    assert 'class="recall"' in html and 'class="answers"' in html
    assert 'class="kcapture"' in html, "Knowledge Capture must render as its own box"
    recall, kc, ans = (html.index(f'class="{c}"')
                       for c in ("recall", "kcapture", "answers"))
    assert recall < kc < ans
    # siblings, not nested: each box closes before the next opens
    assert html.index("</div>", recall) < kc
    assert html.index("</div>", kc) < ans
    # premailer inlined the recall/answers rules
    assert "#FFF8E1" in html and "dashed" in html
