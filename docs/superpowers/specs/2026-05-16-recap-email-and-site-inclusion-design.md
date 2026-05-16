# Recap Email + Site Inclusion — Design

**Date:** 2026-05-16
**Branch:** `chuan`
**Status:** Approved — ready for implementation plan

## Problem

Weekly RECAP runs every Saturday and uploads `[Recap] YYYY-MM-DD ...html` to
Drive, but two pieces of value are missing:

1. **No email is sent.** Daily Mon–Fri emails go to the team; Saturday's
   weekly summary is silently uploaded to Drive only. The team has to remember
   to look it up. (Confirmed: `src/main.py:147-153` returns before reaching
   `send_daily_email`.)
2. **The recap doesn't appear on the public KM site.** `tools/build_site.py`
   regex matches only `^\[Email\]\s+...`, so `[Recap]` files in Drive are
   skipped during site builds. The weekly summary never becomes part of the
   browsable knowledge archive.

## Goals

- Saturday recap → arrives in the team's inbox like the daily emails do.
- Saturday recap → indexed on the static site under pillar=RECAP, archive
  pages, and homepage "latest" list.
- Zero additional LLM cost — reuse the recap HTML that's already generated.
- Backward-compatible: daily-email flow, daily-post site rendering, all
  existing recap behavior (upload-to-Drive) are unchanged.

## Non-goals (YAGNI)

- **No image/infographic for recap.** Template already has a visual
  Mon–Fri timeline strip. Adding image gen would multiply recap cost ~50×
  and add a brittle step for a "summary" piece. Revisit if user feedback
  asks for it.
- **No dedicated `/recaps/` site section.** `PILLAR_META["RECAP"]` already
  exists; pillar page + archive pages handle this for free.
- **No new email template.** `DesignerAgent.create_recap_email()` already
  returns email-ready HTML (inlined styles).
- **No workflow / CI changes.** Existing `daily-routine.yml` job order
  (`run` → `deploy-site`) already rebuilds the site after the recap upload.
- **No backfill script.** When the regex change ships, the next site build
  will automatically pick up any historic `[Recap]` files in Drive.

## Design

### Change 1: Send email from `RecapAgent`

**File:** `src/agents/recap_agent.py`

After the successful upload-to-Drive log line, call `send_daily_email()`
with the same `recap_html` already in memory.

```python
from src.utils.email_sender import send_daily_email

# ... after self.drive.upload(...) and the "✅ Weekly recap uploaded" log:
subject = f"[Consultant Academy] สรุปสัปดาห์ที่ {week_num} — {date_str}"
send_daily_email(subject, recap_html, attachments=None)
```

**Behavior**

- Recipients: read from `EMAIL_RECIPIENTS` env (same as daily email — no
  separate distribution list).
- Attachments: `None`. Recap has no infographic.
- Failure mode: `send_daily_email` already logs warning + returns `False`
  on failure. Don't raise. The Drive copy is the source of truth, and
  failing the whole RECAP run because SMTP hiccupped would be a regression.
- `dry_run=True` path: skip email send (mirrors the existing skip of the
  Drive upload).

### Change 2: Include `[Recap]` files in site builder

**File:** `tools/build_site.py` (line ~48-50)

Extend the archive filename regex to match both `[Email]` and `[Recap]`:

```python
# Before:
ARCHIVE_FILENAME_RE = re.compile(
    r"^\[Email\]\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\.html$"
)

# After:
ARCHIVE_FILENAME_RE = re.compile(
    r"^\[(?:Email|Recap)\]\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\.html$"
)
```

The capture-group order stays the same (date, then title), so downstream
code in `collect_posts()` works without further changes.

### Data flow

```
Saturday RECAP run
  │
  ├── RecapAgent.generate_and_upload()
  │     │
  │     ├── Gemini Flash → markdown summary
  │     ├── DesignerAgent.create_recap_email() → recap_html
  │     ├── drive.upload(filename="[Recap] ...html")     ← already exists
  │     └── send_daily_email(subject, recap_html)        ← NEW
  │
  └── deploy-site job (already in workflow)
        │
        └── tools/build_site.py
              │
              └── ARCHIVE_FILENAME_RE matches [Recap] too ← NEW
                    │
                    ├── Post(pillar="RECAP", ...)
                    │    pillar/cluster/industry from calendar entry
                    │    (Saturday is marked pillar=RECAP in the calendar)
                    │
                    ├── Listed in homepage "latest 20"
                    ├── Indexed under /pillars/recap/
                    ├── Indexed under /archive/YYYY/MM/
                    └── Rendered at /posts/YYYY/MM/DD/
```

### Site rendering details

- **Title on post page / cards:** comes from the filename's title group, e.g.
  `สัปดาห์ที่ 20`. Readable.
- **Pillar chip:** `PILLAR_META["RECAP"]` → 📋 "สรุปสัปดาห์".
- **Cluster chip:** Saturday's calendar entry has cluster=`General`, which
  `is_meaningful_cluster()` already filters out — so no junk chip appears.
- **TLDR snippet on listing cards:** falls back to the first paragraph of
  the recap body (key-takeaway intro).
- **`<body>` extraction:** `BODY_RE` (existing) pulls `<body>...</body>`
  out of the recap HTML — same path as daily email archives. Inline styles
  from `premailer` come along.

## Error handling

| Failure | Behavior |
|---|---|
| SMTP send fails | `send_daily_email` logs `📧 Email failed: ...`, returns `False`. Run continues. Drive upload succeeded → recap is recoverable. |
| `EMAIL_RECIPIENTS` unset | `send_daily_email` logs `📧 Email skipped` and returns `False`. Same as daily. |
| `--dry-run` | Skip the email call along with the Drive upload. |
| Site builder hits non-matching filename (e.g. `[Notes] ...`) | Falls through `if not m: continue` — unchanged. |

## Testing

- **`tests/test_recap_agent.py` — create new.** No existing test for
  `RecapAgent`. Add a test that mocks Gemini + Drive + SMTP, runs
  `generate_and_upload()`, and asserts (a) Drive upload was called and
  (b) `send_daily_email` was called with the recap subject pattern.
  Also a test for `dry_run=True` that asserts neither side-effect runs.
- **`tests/test_build_site.py` — extend.** Add a fixture file named
  `[Recap] 2026-05-16 สัปดาห์ที่ 20.html` and assert `collect_posts()`
  yields a `Post` with `pillar="RECAP"`. Existing `[Email]` tests must
  keep passing.

## Files touched

1. `src/agents/recap_agent.py` — +3 lines (import + 2-line call)
2. `tools/build_site.py` — 1 character change in regex pattern
3. Test files as identified above

No new dependencies. No env-var changes. No workflow changes.

## Rollout / rollback

- Single commit, single PR.
- Rollback = revert that commit. Reverting restores the silent-Drive-upload
  behavior; no data needs to be undone (recap files already in Drive stay
  there; site is rebuilt from Drive every run).

## Open questions

None.
