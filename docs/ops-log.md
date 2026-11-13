# Ops log

Actions that change production behaviour but are not commits (secrets,
manual sends, one-off scripts). One line each: date · what · who is affected
· why · how to undo. Newest at the bottom.

| Date | What | Affects | Why | Undo |
|---|---|---|---|---|
| 2026-09-04 | Secret `EMAIL_RECIPIENTS` updated: 16 → 17 addresses (added `thakoon.c@pttplc.com`) | Daily + recap email recipients | Team request | Edit the secret; remove the address |
| 2026-09-11 | One test email sent from a local dry-run (Gemini 3.8 Flash, translator prompt v2) to `tanet.i@pttplc.com` only, via SMTP 465 (corporate network blocks 587) | 1 recipient (owner) | Review content before merging PR #5 | n/a (already delivered) |
| 2026-09-11 | PR #5 merged: all agents on `gemini-3.8-flash`, image on `gemini-3.1-flash-image`, Vertex location `global` | All recipients, from the 2026-09-11 run onward | Vertex retires Gemini 2.5 on 2026-10-16 | Revert merge commit `c97a5d6` |
| 2026-09-11 | Secret `VERTEX_AI_LOCATION` (`us-central1`) deleted by owner; no workflow read it after PR #5 | None | Location is now set in the workflow file | Re-create the secret with `us-central1` (it would still be unused) |
| 2026-09-11 | Secret `ALERT_EMAIL` created = `tanet.i@pttplc.com`; one `[TEST]` failure alert sent there from a local run | Owner only | Owner asked to be emailed when a run fails | Delete the secret (alerts become a no-op) |
| 2026-09-29 | Retention is NOT measured: mail is one-way by owner decision (no replies, no pixels, static site stores nothing). A per-run log line (shape/kit/recall/repairs) exists for operations only. Six-pillar dry run made with real Vertex calls (6 articles, no uploads, no email). | Measurement | A8/C2: record the limit instead of inventing a proxy | n/a |
| 2026-09-29 | Three sample emails (SOFTSKILL, TECHNICAL, SUSTAINABILITY — six-pillar dry-run output) sent to `tanet.i@pttplc.com` only, via SMTP 465 with a 300s timeout (the 30s default times out on ~5 MB of attachments). Corrects the row above, which recorded the dry run as "no email". | 1 recipient (owner) | Owner review of the new six-pillar format before merging `chuan` | n/a (already delivered) |
| 2026-11-13 | Hybrid routing enabled: upgraded `EXPERT` and `FACTCHECKER` to `gemini-4-hydrogen` ($1.50/$7.50); kept remaining agents on `gemini-3.8-flash` through 2026-12-31 ($0.75/$3.75 intro pricing). | Daily pipeline quality & cost | Higher engineering depth & anti-hallucination accuracy for ~20–30 THB/month extra | Revert `GEMINI_MODEL_EXPERT` & `GEMINI_MODEL_FACTCHECKER` to `gemini-3.8-flash` in `daily-routine.yml` |

## Reminders

- 2027-01-01: `gemini-3.8-flash` Vertex price rises from 0.75/3.75 to 1.50/7.50 USD per 1M tokens (same rate as `gemini-4-hydrogen`).
  - Switch remaining `GEMINI_MODEL*` (`RESEARCH`, `INDUSTRY`, `TRANSLATOR`, `EDITOR`, `PLANNER`, `RECAP`) in `.github/workflows/daily-routine.yml` (and default in `src/config/settings.py`) to `gemini-4-hydrogen`.
  - Update `PRICING` in `src/utils/cost_tracker.py` (`gemini-3.8-flash` → `(1.50, 7.50)`).
  - Review `MAX_TOKENS` in `src/config/settings.py` (raise `research`/`industry` budgets if thinking tokens hit cap) and evaluate `IMAGE_MODEL` (`gemini-nano-banana-2.1` replacement for deprecated `gemini-3.1-flash-image`).
