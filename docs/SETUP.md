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

## 2. Google Cloud / Drive API

1. Visit https://console.cloud.google.com → Create project
2. Enable **Google Drive API**
3. Create OAuth 2.0 Client ID (type: Desktop)
4. Download `credentials.json` to project root
5. Run `python src/main.py` once locally — browser opens for OAuth → creates `token.json`

---

## 3. Gemini API

1. Visit https://aistudio.google.com/apikey
2. Create API key → save as `GOOGLE_API_KEY` in `.env`
3. Default model: `gemini-2.0-flash` ($0.075/1M tokens)

---

## 4. Google Drive Folder Structure

Create three top-level folders in Drive and copy their IDs:

```
Email Archives/         → FOLDER_EMAIL_ARCHIVES
Knowledge Base/         → FOLDER_KNOWLEDGE_BASE
Program Management/     → FOLDER_PROGRAM_MGMT
```

Upload `docs/Content-Calendar-2024.md` to Drive — copy its file ID → `CALENDAR_FILE_ID`.

To find a folder ID: open folder in Drive, copy from URL `drive.google.com/drive/folders/<ID>`.

---

## 5. GitHub Actions Setup

Add these secrets at **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key |
| `ANTHROPIC_API_KEY` | (optional) Claude API key |
| `GOOGLE_CREDENTIALS_JSON` | full JSON content of `credentials.json` |
| `GOOGLE_TOKEN_JSON` | full JSON content of `token.json` (after local OAuth) |
| `CALENDAR_FILE_ID` | Drive file ID |
| `FOLDER_EMAIL_ARCHIVES` | Drive folder ID |
| `FOLDER_KNOWLEDGE_BASE` | Drive folder ID |
| `FOLDER_PROGRAM_MGMT` | Drive folder ID |

Schedule: Mon–Fri at 00:00 UTC (07:00 Bangkok). Can be triggered manually via **Actions → Daily Routine → Run workflow**.

---

## 6. Cost Expectations

| Item | Per day | Per month |
|---|---|---|
| Gemini Flash (4 agents × ~1.5k tokens) | ~$0.0005 | ~$0.01 |
| Cache hits (after week 1) | ~$0.00 | ~$0.00 |
| **Total** | **<$0.001** | **<$1** |

GitHub Actions: free for public repos, 2000 min/month free for private.

---

## 7. Adding New Topics

Edit `docs/Content-Calendar-2024.md` (locally **and** in Drive). Format:

```
- **YYYY-MM-DD**: PILLAR | หัวข้อ | Industry | keyword1,keyword2
```

Pillars: `TECHNICAL` | `INDUSTRY` | `FRAMEWORK` | `SOFTSKILL` | `RECAP`

---

## 8. Troubleshooting

- **`No topic found for YYYY-MM-DD`** — Calendar file in Drive doesn't have that date, or format is malformed
- **OAuth fails on GitHub Actions** — `token.json` expired; re-run `python src/main.py` locally to refresh, then update `GOOGLE_TOKEN_JSON` secret
- **Empty research output** — Gemini returned non-JSON; check API quota
- **Friday recap empty** — No `[Email] YYYY-MM-DD ...` files found in current week's folder
