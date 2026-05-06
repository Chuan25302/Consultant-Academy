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
3. Default model: `gemini-2.0-flash` (~$0.075/1M tokens)

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

| Item | Per day | Per month (~22 working days) |
|---|---|---|
| Gemini Flash (4 agents × ~1.5k tokens, real usage logged) | ~$0.0005 | ~$0.011 |
| Cache hits (after first occurrence within 7 days) | $0.00 | ~$0.00 |
| GitHub Actions | free (public) / 2000 min free (private) | — |
| **Total** | **<$0.001** | **<$1** |

Real token counts come from `response.usage_metadata.total_token_count` and are written to `data/cost_log.jsonl` (uploaded as a workflow artifact every run).

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
