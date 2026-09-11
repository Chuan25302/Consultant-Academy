# Ops log

Actions that change production behaviour but are not commits (secrets,
manual sends, one-off scripts). One line each: date · what · who is affected
· why · how to undo. Newest at the bottom.

| Date | What | Affects | Why | Undo |
|---|---|---|---|---|
| 2026-09-04 | Secret `EMAIL_RECIPIENTS` updated: 16 → 17 addresses (added `thakoon.c@pttplc.com`) | Daily + recap email recipients | Team request | Edit the secret; remove the address |
| 2026-09-11 | One test email sent from a local dry-run (Gemini 3.8 Flash, translator prompt v2) to `tanet.i@pttplc.com` only, via SMTP 465 (corporate network blocks 587) | 1 recipient (owner) | Review content before merging PR #5 | n/a (already delivered) |
| 2026-09-11 | PR #5 merged: all agents on `gemini-3.8-flash`, image on `gemini-3.1-flash-image`, Vertex location `global` | All recipients, from the 2026-09-11 run onward | Vertex retires Gemini 2.5 on 2026-10-16 | Revert merge commit `c97a5d6` |
| 2026-09-11 | Secret `VERTEX_AI_LOCATION` (`us-central1`) no longer read by any workflow; owner to delete | None | Location is now set in the workflow file | Re-create the secret with `us-central1` (it would still be unused) |

## Reminders

- 2027-01-01: `gemini-3.8-flash` Vertex price rises from 0.75/3.75 to 1.50/7.50 USD per 1M tokens. Update `src/utils/cost_tracker.py` `PRICING` the same day.
