# Setup Guide — PTT NGR ESP Consultant Academy

## Prerequisites
- Python 3.11+
- Google Cloud project with Drive API enabled
- Gemini API key (Google AI Studio)
- GitHub repository with Actions enabled

---

## 1. Local Development Setup

```bash
git clone <this-repo>
cd consultant-academy
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with your keys and IDs.

---

## 2. Google Cloud — Service Account

We use a **service account** (not OAuth Desktop) so the workflow runs headless on GitHub Actions without expiring tokens.

1. Visit https://console.cloud.google.com → Create or pick a project
2. Enable **Google Drive API**
3. **IAM & Admin → Service Accounts → Create Service Account**
   - Name: `consultant-academy-bot`
   - Skip role grants (Drive permission is per-folder, see step 4)
4. Open the new service account → **Keys → Add Key → Create new key → JSON**
   - Download the JSON, save as `service-account.json` in repo root
5. Note the service account email — looks like `consultant-academy-bot@<project>.iam.gserviceaccount.com`

> **Service accounts have NO Drive of their own.** They can only access folders/files that have been explicitly **shared** with their email.

---

## 3. Share Drive folders with the service account

In Google Drive, for each of the 3 root folders **and** the calendar file:

```
Email Archives/         → share with SA email, role: Editor
Knowledge Base/         → share with SA email, role: Editor
Program Management/     → share with SA email, role: Editor
Content-Calendar-2024.md → share with SA email, role: Viewer (or Editor)
```

Then copy each folder's ID from URL `drive.google.com/drive/folders/<ID>` into `.env`.

---

## 4. Gemini API

1. Visit https://aistudio.google.com/apikey
2. Create API key → save as `GOOGLE_API_KEY` in `.env`
3. Default model: `gemini-2.0-flash` (~$0.075/$0.30 per 1M in/out tokens)

### Per-agent model selection

Each agent can use a different model. Set in `.env` (or GitHub secrets):

```
GEMINI_MODEL=gemini-2.0-flash         # global default
GEMINI_MODEL_EXPERT=gemini-2.5-pro    # use Pro for the core content
GEMINI_MODEL_RECAP=gemini-2.5-flash-lite
```

Available models (price = USD per 1M tokens, input/output):

| Model | In | Out | Use case |
|---|---|---|---|
| `gemini-2.0-flash` | 0.075 | 0.30 | **Default** — fast & cheap |
| `gemini-2.0-flash-lite` | 0.075 | 0.30 | Cheapest, smaller context window |
| `gemini-2.5-flash-lite` | 0.10 | 0.40 | Good middle ground |
| `gemini-2.5-flash` | 0.30 | 2.50 | Much better reasoning |
| `gemini-2.5-pro` | 1.25 | 10.00 | Best quality (use sparingly) |
| `gemini-1.5-pro` | 1.25 | 5.00 | Older flagship |

**Recommended setup** for cost-vs-quality balance:
- `EXPERT` → `gemini-2.5-pro` (core content quality matters most)
- everything else → `gemini-2.0-flash`

Per-month cost in this configuration is still under $1 for daily Mon–Fri runs (1 Pro call/day × ~3k tokens × $0.01 ≈ $0.20/month, plus negligible Flash calls).

---

## 5. Local smoke test

```bash
python src/main.py --dry-run
```

`--dry-run` runs the full Gemini pipeline but skips Drive uploads — good for verifying agents + calendar parsing without polluting Drive.

---

## 6. GitHub Actions Setup

Add these secrets at **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON content of `service-account.json` |
| `CALENDAR_FILE_ID` | Drive file ID of content calendar |
| `FOLDER_EMAIL_ARCHIVES` | Drive folder ID |
| `FOLDER_KNOWLEDGE_BASE` | Drive folder ID |
| `FOLDER_PROGRAM_MGMT` | Drive folder ID |
| `SLACK_WEBHOOK_URL` | *(optional)* Slack incoming webhook for failure alerts |

Schedule: Mon–Fri at 00:00 UTC (07:00 Bangkok). Manual trigger via **Actions → Daily Routine → Run workflow** (with optional `dry_run`).

---

## 7. Cost Expectations

Real token counts (`prompt_token_count` + `candidates_token_count`) are written
to `data/cost_log.jsonl` — uploaded as a workflow artifact every run.

| Configuration | Per day | Per month (~22 days) |
|---|---|---|
| All Flash 2.0 | ~$0.001 | ~$0.02 |
| Expert=Pro 2.5, rest Flash 2.0 | ~$0.02 | ~$0.40 |
| All Pro 2.5 | ~$0.10 | ~$2.20 |
| GitHub Actions | free (public) / 2000 min free (private) | — |

---

## 8. Adding New Topics

Edit the calendar file in Drive (and optionally `docs/Content-Calendar-2024.md` to keep them in sync). Format:

```
- **YYYY-MM-DD**: PILLAR | หัวข้อ | Industry | keyword1,keyword2
```

Pillars: `TECHNICAL` | `INDUSTRY` | `FRAMEWORK` | `SOFTSKILL` | `RECAP`

`RECAP` rows skip the full pipeline and run the weekly recap agent instead (which summarizes the week's `[Email] ...` files).

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `No topic found for YYYY-MM-DD` | Calendar in Drive doesn't contain that date | Add row in calendar (Bangkok timezone) |
| `Calendar file empty or unreadable` | SA doesn't have access to the calendar file | Share file with SA email |
| `Upload failed: 403 insufficient permissions` | SA doesn't have Editor on the target folder | Share folder with SA email as **Editor** |
| Friday recap empty | No `[Email] YYYY-MM-DD ...` files for Mon–Thu of current week | Re-run earlier days, or check folder structure |
| Workflow fails silently | No Slack secret configured | Add `SLACK_WEBHOOK_URL` and check workflow run page directly |
| Same file uploaded twice | Re-running workflow same day | `upload()` defaults to `skip_if_exists=True` so this should be a no-op now |
