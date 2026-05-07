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

> 📋 **For a step-by-step Drive setup checklist with diagrams, see [Drive-Setup.md](Drive-Setup.md)**

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

| Configuration | Mon–Fri (each) | Sat (recap only) | Per month |
|---|---|---|---|
| All Flash 2.0 | ~$0.002 (~0.07 ฿) | ~$0.001 | ~$0.05 (~1.7 ฿) |
| **Recommended**: Pro 2.5 on Expert + FactChecker + Editor + Sustainability, Flash 2.5 on Research/Industry/Translator, Flash 2.0 on Recap | ~$0.07 (~2.5 ฿) | ~$0.001 (~0.04 ฿) | ~$1.50 (~50 ฿) |
| All Pro 2.5 | ~$0.18 | ~$0.01 | ~$4.00 |
| GitHub Actions | free (public) / 2000 min free (private) | — | — |

Schedule: Mon–Fri = full pipeline (5 content days), Sat = RECAP only.
Recommended config keeps Mon–Fri inside the 3 บาท ceiling while running Pro 2.5 on the four quality-critical agents (Expert for core content, FactChecker for anti-hallucination, Editor for final QA, Sustainability for carbon math accuracy).

---

## 8. Adding New Topics

Edit the calendar file in Drive (and optionally `docs/Content-Calendar-2024.md` to keep them in sync). Format:

```
- **YYYY-MM-DD**: PILLAR | หัวข้อ | Industry | k1,k2 | cluster=X | level=N
```

| Field | Required | Notes |
|---|---|---|
| `PILLAR` | yes | `TECHNICAL` \| `INDUSTRY` \| `FRAMEWORK` \| `SOFTSKILL` \| `COMPLIANCE` \| `SUSTAINABILITY` \| `RECAP` |
| Topic | yes | Used as the email/article title |
| Industry | yes | Used by Industry agent (`General` skips it) |
| Keywords | yes | Used by Research agent |
| `cluster=X` | no | Subfolder under the pillar in Knowledge Base (e.g. `HVAC-Chillers`). Defaults to `General` |
| `level=N` | no | 1=basics, 2=intermediate, 3=advanced. Defaults to `1` |

`RECAP` rows skip the full pipeline and run the weekly recap agent instead.

### Auto-extending the calendar

After every successful run, the **Planner agent** checks if the calendar has fewer than 14 days of entries ahead. If so, it generates the next 4 weeks (Mon–Fri content + Sat RECAP) using Pro 2.5 and writes them back to the calendar in Drive. Manual trigger: `python src/main.py --plan-next`.

The planner avoids repeating recent topics, progresses through Levels 1→2→3 within each cluster, rotates through the 10 industry families (incl. niche: pulp/paper, rubber/glove, ceramics, data center, battery), and uses a variety of named SOFTSKILL frameworks. Generated entries can be reviewed in Drive and edited if needed — the system reads the latest version on every run.

## 9. Knowledge Base structure (for new hires)

The pipeline organizes the Knowledge Base hierarchy by pillar → cluster → level so a new hire can read through it sequentially without prior knowledge of where things are:

```
Knowledge Base/
├── 00-Master-Index.md  ← auto-generated every day, single starting point
├── 01-Technical-Depth/
│   ├── HVAC-Chillers/
│   │   ├── [L1] 2024-05-06 Chiller Efficiency 101.docx
│   │   └── [L2] 2024-09-12 Cooling Tower Optimization.docx
│   ├── Motors-VFD/
│   ├── Steam/
│   └── Compressed-Air/
├── 02-Industry-Business-Logic/
│   ├── Hospitality/
│   ├── Steel/
│   └── Pharma/
├── 03-Diagnostic-Frameworks/
│   ├── Energy-Audit/
│   ├── Measurement-Verification/
│   └── Financial-Analysis/
└── 04-Soft-Skills-Positioning/
    ├── Discovery/
    ├── Objection-Handling/
    └── Proposal-Writing/
```

`00-Master-Index.md` lists every article grouped by pillar → cluster, and includes a "🆕 สำหรับคนใหม่ — เริ่มอ่านที่นี่" section with all Level 1 articles in chronological order. New hires open this single file and follow the suggested reading order.

Filename convention: `[L<level>] YYYY-MM-DD <topic>.docx` so Drive's alphabetical sort puts L1 articles first within each cluster.

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
