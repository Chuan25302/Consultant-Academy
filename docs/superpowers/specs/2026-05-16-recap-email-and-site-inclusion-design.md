# Recap → Knowledge-Capture Email — Design

**Date:** 2026-05-16
**Branch:** `chuan`
**Status:** Approved — ready for implementation plan

> **Revision history**
> - **v1** — proposed two changes: send recap email + include recap files
>   in the static site. User feedback redirected this: the recap doesn't
>   belong on the public site (duplicates content already published as
>   daily posts → confusing). And the recap content itself should pivot
>   from a high-level summary to a real knowledge-capture artifact
>   (formulas, heuristics, takeaways) that consultants will actually
>   look back at.
> - **v2 (this version)** — drops the site-inclusion change entirely;
>   instead reworks `RecapAgent` to do deep extraction of the week's
>   content and emit a structured "knowledge capture" body, then sends
>   that as an email.

## Problem

Weekly RECAP runs every Saturday and uploads `[Recap] YYYY-MM-DD ...html`
to Drive. Two issues with that artifact today:

1. **No email is sent.** The team has to remember to open Drive to read
   the weekly summary. (Confirmed: `src/main.py:147-153` returns before
   reaching `send_daily_email`.)
2. **The content is high-level "summary of what we covered."** The
   prompt only sees the *titles* of Mon–Fri posts (see
   `recap_agent.py:64-67` — only `f["name"]` is appended to summaries),
   so the LLM has nothing concrete to extract. The result reads like a
   recap of a recap. There's no formula, no rule of thumb, no specific
   data point that a consultant would bookmark and reuse.

## Goals

- Saturday recap → arrives in the team's inbox as a structured
  **knowledge-capture digest**: takeaways, captured knowledge, formulas
  and heuristics, and concrete consultant moves to try next week.
- Recap stays in Drive as the archived copy (already happens — no change).
- Quality lift: the LLM gets the *bodies* of Mon–Fri posts as input, so
  the formulas / heuristics it surfaces are pulled from the actual week's
  content rather than guessed from titles.

## Non-goals (YAGNI)

- **Do not put recap on the public KM site.** The site already has each
  Mon–Fri post as its own page; the recap would duplicate that and
  confuse readers (`build_site.py` regex stays unchanged).
- **No image/infographic for recap.** Email template already has a
  Mon–Fri timeline strip as the visual anchor.
- **No new email template.** `DesignerAgent.create_recap_email()` is
  flexible — the body is rendered from whatever markdown the LLM
  produces. Changing sections = changing the prompt only.
- **No model change.** Keep `GEMINI_MODEL_RECAP=gemini-2.5-flash`. The
  deeper input is still well within Flash's capability for structured
  extraction. Revisit if output quality is weak after a few real runs.
- **No workflow / CI / env-var changes.**

## Design

### Change 1: Send email from `RecapAgent`

**File:** `src/agents/recap_agent.py`

After the successful Drive upload, call `send_daily_email()` with the
same `recap_html` already in memory.

```python
from src.utils.email_sender import send_daily_email

# ... after self.drive.upload(...) and the "✅ Weekly recap uploaded" log:
subject = f"[Consultant Academy] สรุปสัปดาห์ที่ {week_num} — {date_str}"
send_daily_email(subject, recap_html, attachments=None)
```

**Behavior**

- Recipients: `EMAIL_RECIPIENTS` env (same list as daily).
- Attachments: `None`.
- Failure mode: `send_daily_email` already logs warning + returns `False`
  on failure. Don't raise. The Drive copy is the source of truth.
- `dry_run=True`: skip the email send (mirrors the existing Drive-upload
  skip).

### Change 2: Deep extraction — feed Mon–Fri bodies to the LLM

**File:** `src/agents/recap_agent.py`

Replace the title-only loop with a loop that downloads each Mon–Fri
post and extracts a compact "key sections" digest per day. Feed all
five days as structured input to the LLM under a new prompt.

#### Per-day extraction

For each `[Email] YYYY-MM-DD ...html` file found in Drive:

1. `drive.download_file(file_id)` → full HTML.
2. Strip HTML to plain text. Daily emails are already structured with
   `<h2>` sections like "Key Takeaway" / "Why this matters" /
   "Apply to clients" — keep those headings as section markers so the
   recap LLM knows what kind of content each chunk is.
3. Send the full per-day text to the LLM — no truncation. Flash's
   1M-token context easily handles a week of full posts (~20K tokens
   typical). Budget truncation was considered and rejected because
   formulas/heuristics typically appear in deep-dive sections, not
   in the TLDR — truncating short would cut off exactly the content
   we want to extract. Cost impact of going full-body vs. truncated
   is ≤$0.002/run, negligible.
4. Skip a day cleanly if download or strip fails — the recap should
   still produce a useful output from the remaining days.

A small helper in `recap_agent.py` (private function — not a public
module API) is fine. No need to refactor `drive_api.py` or add a
shared HTML utility — this is the one place that needs it.

#### New prompt

The Gemini prompt receives the structured per-day digests and is told
to produce four named sections in markdown. The sections map to what
gets rendered as the email body via `DesignerAgent._md_to_html`.

```
สรุปประจำสัปดาห์ที่ {week}

### 🎯 Key Takeaways
3–5 bullets — บทเรียนใหญ่ที่เปลี่ยน mental model ของที่ปรึกษาในสัปดาห์นี้
แต่ละ bullet ต้องอ้างได้ว่ามาจากเนื้อหาวันไหน

### 📚 Knowledge Capture
สิ่งที่ควรจำและอ้างถึงได้:
- คำศัพท์/นิยามใหม่ที่สำคัญ
- ตัวเลข / data point ที่ใช้อ้างกับลูกค้าได้
- framework / model ที่ใช้บ่อย

### 📐 Formulas & Heuristics
ดึง **เฉพาะที่ปรากฏจริง** ในเนื้อหาสัปดาห์นี้ ห้ามแต่งเอง:
**Formulas:** สูตรพร้อมตัวแปรและ "ใช้เมื่อไร"
**Heuristics:** กฎหัวแม่มือ / rules of thumb

### 🛠️ ใช้กับลูกค้าได้เลย
3 consultant moves — action เฉพาะที่ทำได้สัปดาห์หน้า
```

Total length target: ~400-500 คำ (กว่า recap เดิม เพราะมีเนื้อมากขึ้น —
แต่ยังคงเป็น "ของอ่านเร็ว").

**Anti-hallucination guard in the prompt:** explicitly tell the LLM
*do not invent formulas*. If the week's content had no formulas, that
section should say so (e.g. "สัปดาห์นี้ไม่มี formula หลัก — เน้น
soft-skill / framework"). This is a real risk with knowledge-capture
prompts and worth one explicit line of prompt language.

### What stays the same

- `daily_topics` timeline strip (Mon–Fri) — still passed to
  `create_recap_email()`. Useful chronological anchor next to the
  knowledge-capture body.
- Filename pattern `[Recap] YYYY-MM-DD สัปดาห์ที่ N.html` — unchanged.
- Drive folder `Email Archives/{year}/{month_lowercase}/` — unchanged.
- `tools/build_site.py` regex — **unchanged**. Recap files stay off
  the public site by design.

### Data flow

```
Saturday RECAP run (recap_agent.generate_and_upload)
  │
  ├── For each Mon–Fri:
  │     │  drive.list_files_by_prefix("[Email] YYYY-MM-DD")
  │     │
  │     └── For each file found:
  │           ├── drive.download_file(file_id) → HTML
  │           ├── strip HTML → text, keep H2 section markers
  │           ├── truncate to per-day budget
  │           └── append to structured prompt input
  │
  ├── Gemini Flash → markdown with 4 named sections
  ├── DesignerAgent.create_recap_email(content=md, daily_topics=..., ...)
  │        └── renders email-ready HTML (existing template, unchanged)
  ├── drive.upload(filename="[Recap] ...html")        ← existing
  └── send_daily_email(subject, recap_html)           ← NEW
        └── reuses EMAIL_RECIPIENTS / SMTP from daily emails
```

### Error handling

| Failure | Behavior |
|---|---|
| One Mon–Fri post fails to download | Log warning, skip that day, keep going. |
| All five days have no content | Existing `if not summaries: return` path stays — early-exit with warning. |
| Gemini call fails | Existing retry layer (`@retry` decorator in gemini_client) applies. Final failure propagates. |
| `drive.upload` fails | Existing behavior — exception bubbles. Email is *not* sent (we only send after a successful upload). |
| `send_daily_email` SMTP fail | Logs warning, returns `False`. Run continues. Drive copy already saved. |
| `EMAIL_RECIPIENTS` unset | `send_daily_email` logs `📧 Email skipped`, returns `False`. No crash. |
| `--dry-run` | Skip both Drive upload and email send (current dry-run path simply returns early). |

### Cost

Rough order-of-magnitude (Gemini Flash):

| Phase | Input | Output | Cost est. |
|---|---|---|---|
| **v2 (deep extraction, full body)** | ~5 days × full post ≈ 20K tokens | ~1500 tokens (longer body) | ~$0.002 |
| Current (titles only) | ~100 tokens | ~600 tokens | ~$0.001 |

Cost lift is well under $0.01/run, roughly $0.05/year. No image gen →
no hidden cost. Daily-pipeline cost (Mon–Fri) is untouched.

## Files touched

1. `src/agents/recap_agent.py` — main change:
   - import `send_daily_email`
   - add private helper to download + strip a single Mon–Fri post
   - replace the title-only loop with per-day deep extraction
   - replace `PROMPT` with the new 4-section prompt
   - call `send_daily_email` after `drive.upload`
2. **No** change to `tools/build_site.py`.
3. **No** change to workflows, env, dependencies.
4. Test files (see below).

## Testing

- **`tests/test_recap_agent.py` — create new.** No existing test for
  `RecapAgent`. Mock Gemini + Drive + SMTP. Cover:
  - Happy path: 5 Mon–Fri files → asserts (a) Drive upload called once,
    (b) `send_daily_email` called with subject matching
    `f"[Consultant Academy] สรุปสัปดาห์ที่ {week}"`, (c) prompt sent to
    Gemini contains the downloaded body text (not just titles).
  - Partial failure: 1 of 5 downloads fails → recap still generates from
    the other 4, no exception.
  - All days empty: returns early with warning, no upload, no email.
  - `dry_run=True`: no upload, no email; Gemini still called (so cost is
    logged correctly).
- **`tests/test_build_site.py` — no changes.** The site builder behavior
  is untouched in v2.

## Rollout / rollback

- Single PR off `chuan`, single commit (or two if test scaffolding is
  separated for review clarity).
- Rollback = revert commit. Drive recaps will go back to title-only
  summaries with no email; no data needs unwinding.

## Open questions

None.
