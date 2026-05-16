# Recap → Knowledge-Capture Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework `RecapAgent` to feed Mon–Fri post bodies into the LLM, emit a 4-section knowledge-capture body (Takeaways / Knowledge Capture / Formulas & Heuristics / Apply), and send the result as an email after the existing Drive upload.

**Architecture:** All implementation lives in `src/agents/recap_agent.py`. The flow stays the same shape — collect Mon–Fri files, generate markdown via Gemini, render HTML via `DesignerAgent.create_recap_email`, upload to Drive — but the input expands from "titles only" to "full post bodies (HTML-stripped to text)", the prompt is rewritten for structured knowledge extraction, and a new `send_daily_email` call sits after the successful Drive upload. No site builder changes; the public KM site does not get recap pages.

**Tech Stack:** Python 3.11, Gemini 2.5 Flash via Vertex AI (`gemini_client.GeminiClient`), Google Drive via `drive_api.DriveAPI` (OAuth), Gmail SMTP via `email_sender.send_daily_email`, pytest + `unittest.mock.MagicMock` for tests.

---

## Spec reference

[docs/superpowers/specs/2026-05-16-recap-email-and-site-inclusion-design.md](../specs/2026-05-16-recap-email-and-site-inclusion-design.md) — see "Change 1" (email send) and "Change 2" (deep extraction) sections.

## File structure

**Created:**
- `tests/test_recap_agent.py` — first tests for `RecapAgent`. Uses `MagicMock` for `GeminiClient`, `DriveAPI`, and `send_daily_email`. Tests are self-contained (no Drive/SMTP/Vertex auth needed in CI).

**Modified:**
- `src/agents/recap_agent.py` — all production changes happen here:
  - Add `import html` (stdlib) and `from src.utils.email_sender import send_daily_email`.
  - Add two private module-level helpers: `_strip_html_to_text(html_str: str) -> str` and `_build_day_digest(file: dict, drive) -> str | None`.
  - Replace the title-only loop inside `generate_and_upload` with a body-based loop that calls `_build_day_digest`.
  - Replace the `PROMPT` constant with the new 4-section template that includes an anti-hallucination guard.
  - After the existing `drive.upload(...)` call (non-dry-run path), call `send_daily_email(subject, recap_html)`.

**Untouched:** `tools/build_site.py`, `src/utils/email_sender.py`, `src/agents/designer_agent.py`, `.github/workflows/`. The existing recap upload behavior, daily-routine flow, and site builder all stay as-is.

## Reference signatures (so the engineer doesn't have to dig)

```python
# src/integrations/drive_api.py
class DriveAPI:
    def list_files_by_prefix(self, name_prefix: str) -> list[dict]:
        # returns [{"id": "...", "name": "...", ...}, ...]
    def download_file(self, file_id: str) -> str:
        # returns the file's text content (HTML decoded as UTF-8)
    def upload(self, filename: str, content: str | bytes,
               folder_id: str, mime_type: str) -> str: ...
    def get_or_create_folder(self, path: str, root_id: str) -> str: ...

# src/integrations/gemini_client.py
class GeminiClient:
    def generate(self, prompt: str, max_tokens: int | None = None,
                 agent_tag: str = "unknown") -> str: ...

# src/utils/email_sender.py
def send_daily_email(subject: str, html_body: str,
                     attachments: list | None = None) -> bool: ...

# src/config/settings.py
def now_bangkok() -> datetime: ...     # timezone-aware Asia/Bangkok
```

## Test fixture conventions in this repo

- Tests live under `tests/`, run with `pytest`.
- For Drive, tests build a small `FakeDrive` class with the methods they touch (see `tests/test_build_site.py:test_collect_posts_skips_future_dates` for an example) **or** use `unittest.mock.MagicMock(spec=DriveAPI)`. Either is acceptable; this plan uses `MagicMock` because we mock more methods.
- No tests require real network / auth.

---

## Task 1: Add HTML-to-text helper with TDD

**Files:**
- Create: `tests/test_recap_agent.py`
- Modify: `src/agents/recap_agent.py` (add module-level helper + import)

The helper turns a daily email's HTML into plain text usable as LLM input. Block-level tags become newlines so the LLM sees section breaks; inline tags are dropped silently; `<style>` and `<script>` blocks are removed entirely so we don't feed CSS to Gemini.

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_recap_agent.py`:

```python
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

from src.agents.recap_agent import _strip_html_to_text


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
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `pytest tests/test_recap_agent.py -v`
Expected: ImportError / "cannot import name `_strip_html_to_text`" — function doesn't exist yet.

- [ ] **Step 1.3: Implement `_strip_html_to_text` in `src/agents/recap_agent.py`**

Add these to the top of `src/agents/recap_agent.py` (after the existing imports). Place the helper as a module-level function before the `RecapAgent` class:

```python
import html as html_module  # added — stdlib; aliased to avoid shadowing local vars

# ... existing imports stay ...

_STYLE_OR_SCRIPT_RE = re.compile(
    r"<(style|script)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_BLOCK_CLOSE_RE = re.compile(
    r"</(p|h1|h2|h3|h4|h5|h6|li|div)\s*>", re.IGNORECASE
)
_BR_OR_HR_RE = re.compile(r"<(br|hr)\s*/?>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_INLINE_WS_RE = re.compile(r"[ \t]+")


def _strip_html_to_text(html_str: str | None) -> str:
    """Convert an email-style HTML document to plain text suitable as
    LLM input.

    - Removes <style>/<script> blocks entirely (their content is not
      article content; feeding CSS to Gemini wastes tokens).
    - Replaces block-level closing tags with newlines so section
      structure (H2 headings, paragraphs, list items) survives the
      tag strip and the LLM can see where one section ends.
    - Decodes HTML entities so `&amp;` reads as `&`.
    - Collapses internal runs of spaces/tabs and drops blank lines.
    """
    if not html_str:
        return ""
    text = _STYLE_OR_SCRIPT_RE.sub("", html_str)
    text = _BLOCK_CLOSE_RE.sub("\n", text)
    text = _BR_OR_HR_RE.sub("\n", text)
    text = _ANY_TAG_RE.sub("", text)
    text = html_module.unescape(text)
    lines = [_INLINE_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)
```

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `pytest tests/test_recap_agent.py -v`
Expected: 5 passed.

Also run ruff to keep the codebase clean:
Run: `ruff check src/agents/recap_agent.py tests/test_recap_agent.py`
Expected: All checks passed (or warnings only — fix lint errors before continuing).

- [ ] **Step 1.5: Commit**

```bash
git add tests/test_recap_agent.py src/agents/recap_agent.py
git commit -m "feat(recap): add _strip_html_to_text helper

Prepares for deep extraction of Mon–Fri post bodies into the recap
LLM prompt. Stdlib-only (re + html.unescape), no new dependency.
Block-level closes become newlines so the LLM still sees section
boundaries after the tag strip."
```

---

## Task 2: Add `_build_day_digest` helper with TDD

**Files:**
- Modify: `tests/test_recap_agent.py`
- Modify: `src/agents/recap_agent.py`

This helper turns a Drive file dict (from `list_files_by_prefix`) into the per-day digest string we'll feed to Gemini. It downloads the file, runs the stripper, and returns the text — or `None` if the download fails or the file is empty. The main loop will filter `None`s so a single bad day doesn't break the whole recap.

- [ ] **Step 2.1: Append failing tests to `tests/test_recap_agent.py`**

Add after the existing tests:

```python
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
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `pytest tests/test_recap_agent.py -v -k "build_day_digest"`
Expected: ImportError on `_build_day_digest`.

- [ ] **Step 2.3: Implement `_build_day_digest` in `src/agents/recap_agent.py`**

Add this immediately after `_strip_html_to_text`:

```python
def _build_day_digest(file: dict, drive) -> str | None:
    """Download a Mon–Fri email archive and return its body as plain
    text. Returns None when the download fails or the file is empty,
    so the caller can simply skip that day rather than crashing the
    whole recap run."""
    try:
        raw = drive.download_file(file["id"])
    except Exception as e:
        logger.warning(
            f"Could not download {file.get('name', file.get('id'))} for recap: {e}"
        )
        return None
    if not raw:
        return None
    text = _strip_html_to_text(raw)
    return text or None
```

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `pytest tests/test_recap_agent.py -v`
Expected: 8 passed (5 prior + 3 new).

Run: `ruff check src/agents/recap_agent.py tests/test_recap_agent.py`
Expected: All checks passed.

- [ ] **Step 2.5: Commit**

```bash
git add src/agents/recap_agent.py tests/test_recap_agent.py
git commit -m "feat(recap): add _build_day_digest for per-day extraction

Downloads a single Mon–Fri archive HTML and returns its stripped
text. Returns None on failure so the main recap loop can skip a
bad day instead of failing the whole weekly run."
```

---

## Task 3: Rewrite the prompt + main loop to use deep extraction

**Files:**
- Modify: `tests/test_recap_agent.py`
- Modify: `src/agents/recap_agent.py`

Currently `generate_and_upload` builds `summaries` from filenames only and feeds those titles to a generic summary prompt. We replace both: the loop builds full per-day digests via `_build_day_digest`, and `PROMPT` becomes the 4-section structured prompt with an anti-hallucination guard for the Formulas section. `daily_topics` (the timeline strip data) is unchanged — the recap email template still expects it.

- [ ] **Step 3.1: Append failing tests to `tests/test_recap_agent.py`**

Add at the bottom of the file. These tests exercise `RecapAgent.generate_and_upload` end-to-end with everything mocked.

```python
# ---------- RecapAgent.generate_and_upload ---------------------------------

from datetime import datetime
from zoneinfo import ZoneInfo

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
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `pytest tests/test_recap_agent.py -v -k "feeds_full_bodies or four_sections"`
Expected: Both fail. The prompt still only contains filenames, not body snippets, so the body assertions fail; the section markers also aren't present yet.

- [ ] **Step 3.3: Replace `PROMPT` constant in `src/agents/recap_agent.py`**

Replace the existing `PROMPT = """..."""` block with:

```python
PROMPT = """คุณคือผู้สรุปและจับใจความเชิงลึกของ PTT NGR ESP Consultant Academy

นี่คือเนื้อหาบทความ Mon–Fri สัปดาห์ที่ {week}:

{day_digests}

---

จงเขียน Markdown ภาษาไทย แบ่งเป็น 4 หัวข้อตามนี้ ไม่เกิน 500 คำรวมทั้งหมด:

## สรุปประจำสัปดาห์ที่ {week}

### 🎯 Key Takeaways
3–5 bullets — บทเรียนใหญ่ที่เปลี่ยน mental model ของที่ปรึกษาสัปดาห์นี้
แต่ละ bullet ต้องอ้างเนื้อหาได้จริง (ระบุวันสั้น ๆ หากใช่)

### 📚 Knowledge Capture
สิ่งที่ควรจำและอ้างถึงได้:
- คำศัพท์ / นิยามใหม่ที่สำคัญ
- ตัวเลข / data point ที่ใช้อ้างกับลูกค้าได้
- framework / model ที่ใช้บ่อย

### 📐 Formulas & Heuristics
ดึง **เฉพาะที่ปรากฏจริง** ในเนื้อหาสัปดาห์นี้
**สำคัญ:** ห้ามแต่ง formula หรือ heuristic ที่ไม่มีในเนื้อจริง
ถ้าสัปดาห์นี้ไม่มี formula ให้พิมพ์ว่า "สัปดาห์นี้ไม่มี formula หลัก — เน้น soft-skill / framework"
**Formulas:** สูตรพร้อมตัวแปรและ "ใช้เมื่อไร"
**Heuristics:** กฎหัวแม่มือ / rules of thumb

### 🛠️ ใช้กับลูกค้าได้เลย
3 consultant moves — action เฉพาะที่ทำได้สัปดาห์หน้า ดึงจากเนื้อหาที่อ่าน
"""
```

- [ ] **Step 3.4: Rework the main loop in `RecapAgent.generate_and_upload`**

Inside `generate_and_upload`, replace the existing Mon–Fri loop (the block that builds `summaries`) with a body-based loop that produces `day_digests`. Keep the `daily_topics` accumulation — the email template still needs it.

Locate the block that currently looks like:

```python
summaries = []
daily_topics = []  # for the timeline strip in the recap layout

for offset in range(5):  # Mon–Fri (recap runs Saturday)
    d = week_start + timedelta(days=offset)
    day = d.strftime("%Y-%m-%d")
    prefix = f"[Email] {day}"
    files = self.drive.list_files_by_prefix(prefix)
    day_topic = "—"
    for f in files:
        title = re.sub(r"\[Email\] \d{4}-\d{2}-\d{2} (.+)\.html",
                       r"\1", f["name"])
        summaries.append(f"- {title}")
        day_topic = title  # last one wins if a day has multiple
    daily_topics.append({
        "date_th": f"{d.day}/{d.month}",
        "day_th":  WEEKDAY_TH_SHORT[d.weekday()],
        "topic":   day_topic,
    })

if not summaries:
    logger.warning("⚠️ No emails found for recap")
    return
```

Replace it with:

```python
day_digests: list[str] = []
daily_topics = []  # for the timeline strip in the recap layout

for offset in range(5):  # Mon–Fri (recap runs Saturday)
    d = week_start + timedelta(days=offset)
    day = d.strftime("%Y-%m-%d")
    prefix = f"[Email] {day}"
    files = self.drive.list_files_by_prefix(prefix)
    day_topic = "—"
    for f in files:
        title = re.sub(r"\[Email\] \d{4}-\d{2}-\d{2} (.+)\.html",
                       r"\1", f["name"])
        day_topic = title  # last one wins if a day has multiple
        body_text = _build_day_digest(f, self.drive)
        if body_text:
            day_digests.append(
                f"## {WEEKDAY_TH_SHORT[d.weekday()]} {d.day}/{d.month} — {title}\n\n{body_text}"
            )
    daily_topics.append({
        "date_th": f"{d.day}/{d.month}",
        "day_th":  WEEKDAY_TH_SHORT[d.weekday()],
        "topic":   day_topic,
    })

if not day_digests:
    logger.warning("⚠️ No content extracted for recap")
    return
```

Then update the `self.gemini.generate(...)` call below it. The current call is:

```python
recap_md = self.gemini.generate(
    PROMPT.format(
        week=week_num,
        summaries="\n".join(summaries),
    ),
    agent_tag="recap",
)
```

Replace it with:

```python
recap_md = self.gemini.generate(
    PROMPT.format(
        week=week_num,
        day_digests="\n\n---\n\n".join(day_digests),
    ),
    agent_tag="recap",
)
```

- [ ] **Step 3.5: Run all recap tests + ruff**

Run: `pytest tests/test_recap_agent.py -v`
Expected: 10 passed (8 prior + 2 new).

Run: `ruff check src/agents/recap_agent.py tests/test_recap_agent.py`
Expected: All checks passed.

- [ ] **Step 3.6: Commit**

```bash
git add src/agents/recap_agent.py tests/test_recap_agent.py
git commit -m "feat(recap): deep extraction from Mon–Fri bodies + 4-section prompt

Recap LLM now receives the actual body text of each Mon–Fri post
(via _build_day_digest), so the Takeaways / Knowledge Capture /
Formulas & Heuristics / Apply sections are grounded in real content
rather than guessed from titles. Anti-hallucination guard explicitly
tells the model not to invent formulas that aren't in the source.

No model / max-tokens change; Flash handles a full week of bodies
well under its context window."
```

---

## Task 4: Send email after Drive upload

**Files:**
- Modify: `tests/test_recap_agent.py`
- Modify: `src/agents/recap_agent.py`

After the existing `self.drive.upload(...)` succeeds, send the recap HTML to the team as an email using the existing `send_daily_email` helper. Subject pattern is fixed so the team can filter on it. Dry-run continues to skip everything below the early-return.

- [ ] **Step 4.1: Append failing tests to `tests/test_recap_agent.py`**

```python
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
```

- [ ] **Step 4.2: Run tests to verify they fail**

Run: `pytest tests/test_recap_agent.py -v -k "sends_email or dry_run_skips"`
Expected: `test_sends_email_with_recap_subject_after_upload` fails (`send_daily_email` not called). `test_dry_run_skips_upload_and_email` should already pass because the existing `dry_run` block returns before upload, but **keep the test** — it locks behavior we don't want to regress.

- [ ] **Step 4.3: Add import + call in `src/agents/recap_agent.py`**

Add to the top-of-file imports (next to the existing `from src.integrations...` lines):

```python
from src.utils.email_sender import send_daily_email
```

Then at the **end** of `generate_and_upload`, immediately after this existing block:

```python
self.drive.upload(
    filename=filename,
    content=recap_html,
    folder_id=folder_id,
    mime_type="text/html",
)
logger.info("✅ Weekly recap uploaded")
```

Add:

```python
subject = (
    f"[Consultant Academy] สรุปสัปดาห์ที่ {week_num} — {date_str}"
)
send_daily_email(subject, recap_html, attachments=None)
```

Note: `date_str` and `week_num` are already in local scope at this point in the function — no recomputation needed.

- [ ] **Step 4.4: Run all recap tests + ruff**

Run: `pytest tests/test_recap_agent.py -v`
Expected: 12 passed.

Run: `ruff check src/agents/recap_agent.py tests/test_recap_agent.py`
Expected: All checks passed.

- [ ] **Step 4.5: Commit**

```bash
git add src/agents/recap_agent.py tests/test_recap_agent.py
git commit -m "feat(recap): email weekly recap to the team after Drive upload

Reuses send_daily_email (same SMTP path as daily emails) with the
exact same HTML that's archived to Drive. Subject is distinct
('สรุปสัปดาห์ที่ N') so recipients can filter or thread weekly
recaps separately from daily emails.

SMTP failure does not abort the recap run — Drive copy remains the
source of truth, mirroring daily-email behavior. Dry-run skips both
sides as expected."
```

---

## Task 5: Partial-failure tolerance (1 of 5 download fails)

**Files:**
- Modify: `tests/test_recap_agent.py`

**No production-code change needed** — `_build_day_digest` already returns `None` on exceptions, and the new main loop only appends digests that are truthy. This task locks in that behavior with a test so a future refactor can't silently break it.

- [ ] **Step 5.1: Append the test**

```python
def test_partial_download_failure_still_generates_recap():
    """If one Mon–Fri download fails, the recap should still generate
    from the other four — the team's weekly digest is more useful with
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
```

- [ ] **Step 5.2: Run tests**

Run: `pytest tests/test_recap_agent.py -v -k "partial_download"`
Expected: PASS — behavior already works thanks to `_build_day_digest`'s try/except.

- [ ] **Step 5.3: Commit**

```bash
git add tests/test_recap_agent.py
git commit -m "test(recap): lock partial-day-failure behavior

If one of five Mon–Fri downloads raises, the recap still produces
from the remaining days. This is implicit in _build_day_digest
returning None on failure, but a future refactor could easily
regress it — this test holds the line."
```

---

## Task 6: End-to-end verification

**Files:** none changed.

- [ ] **Step 6.1: Run the full test suite**

Run: `pytest -v`
Expected: All tests pass, including the existing `tests/test_build_site.py` (we did not touch the site builder — sanity check).

- [ ] **Step 6.2: Run ruff over the touched files**

Run: `ruff check src/agents/recap_agent.py tests/test_recap_agent.py`
Expected: All checks passed.

- [ ] **Step 6.3: Smoke-test the prompt locally (optional but recommended)**

This step needs real Drive + Vertex auth, so it only works on the maintainer's local machine — **skip in CI**.

Run: `python -m src.main --recap-only --dry-run`
Expected: Logs `📋 RECAP-ONLY mode`, downloads the current week's Mon–Fri archives, and prints (in dry-run) "would upload" with the new prompt feeding bodies. Read the generated `recap_md` log line to confirm the LLM produced all four sections with real formulas/heuristics from the week.

If the output reads as expected, you're done. If the model hallucinates formulas anyway, tighten the anti-hallucination clause in `PROMPT` and re-run.

- [ ] **Step 6.4: Open the PR**

```bash
git push -u origin chuan
gh pr create --title "feat(recap): knowledge-capture email + deep extraction" --body "$(cat <<'EOF'
## Summary

- RecapAgent now feeds full Mon–Fri post bodies to Gemini (not just titles), so the weekly digest extracts real formulas, heuristics, and takeaways from the week's content instead of guessing from filenames.
- New 4-section prompt: 🎯 Key Takeaways / 📚 Knowledge Capture / 📐 Formulas & Heuristics / 🛠️ Apply, with an explicit anti-hallucination guard for the Formulas section.
- After the existing Drive upload, the recap HTML is also emailed to the team via the same SMTP path as the daily emails. Subject: `[Consultant Academy] สรุปสัปดาห์ที่ N — YYYY-MM-DD`.
- Recap is **not** added to the public KM site — duplicating content already published as daily posts would confuse readers (this was the original v1 plan; reversed after design review).

Spec: [docs/superpowers/specs/2026-05-16-recap-email-and-site-inclusion-design.md](docs/superpowers/specs/2026-05-16-recap-email-and-site-inclusion-design.md)

## Test plan

- [ ] `pytest tests/test_recap_agent.py -v` — 13 passing (new file)
- [ ] `pytest tests/test_build_site.py -v` — still green (site builder untouched)
- [ ] Local `python -m src.main --recap-only --dry-run` against current week — confirm prompt feeds bodies, recap markdown contains all four sections, no hallucinated formulas
- [ ] After merge, watch Saturday's scheduled run → confirm email arrives + Drive archive matches

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Covered by |
|---|---|
| Change 1: Send email from RecapAgent | Task 4 |
| Change 2: Deep extraction (download + strip per day) | Tasks 1, 2, 3 |
| New 4-section prompt with anti-hallucination guard | Task 3 |
| daily_topics timeline strip stays intact | Task 3 (loop edit preserves it) |
| Site builder unchanged | None needed — explicitly not touched |
| Error: SMTP fail → log + continue | Inherent in `send_daily_email`; no extra handling |
| Error: one day's download fails → skip that day | Task 2 (None return) + Task 5 (lock test) |
| Error: all days empty → early return | Task 3 (`if not day_digests: return`) |
| Error: dry-run → no upload, no email | Task 4 lock test (existing dry-run early-return) |
| Cost analysis | Already documented in spec; nothing to implement |

No gaps.

**Placeholder scan:** none ("TBD", "TODO", "implement later", "similar to Task N" — none of these appear in the plan).

**Type / signature consistency:**
- `_strip_html_to_text(html_str: str | None) -> str` — used in Task 1, called by `_build_day_digest` in Task 2. ✓
- `_build_day_digest(file: dict, drive) -> str | None` — defined Task 2, called from `generate_and_upload` in Task 3. ✓
- `send_daily_email(subject, html_body, attachments=None) -> bool` — signature from `src/utils/email_sender.py`, used in Task 4. ✓
- `PROMPT.format(week=..., day_digests=...)` — the new placeholder is `day_digests`, matching what's joined into the prompt in Task 3. ✓

All consistent.
