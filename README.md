# PTT NGR ESP — Consultant Academy

Daily Thai-language content automation for the energy consulting team. Runs Mon–Fri via GitHub Actions, generates an HTML email + DOCX article from a Google Drive content calendar, uploads results back to Drive. Friday produces a weekly recap.

## Stack
- **Python 3.11+**
- **Gemini Flash** (`gemini-2.0-flash`) via the new `google-genai` SDK — ~$0.075/1M tokens
- **Google Drive API v3** with **service account** auth (headless-friendly)
- **GitHub Actions** for scheduling (no GCP, no DB, no email sending)
- **tenacity** for retry on transient errors; **premailer** to inline CSS for email clients

## Pipeline
```
Calendar → Research → Expert → Industry → Translator → Designer → Drive → Index
                                              ↓
                              (RECAP pillar)  Recap Agent
```

5 LLM agents (Research, Expert, Industry, Translator, Recap) + 1 local renderer (Designer) + 1 local index builder. Research is cached locally for 7 days; expired entries are auto-pruned. Knowledge Base is organized by pillar → cluster → level with an auto-regenerated master index so new hires can follow a single file to catch up.

## Cost
< $1/month for daily content, even with no cache hits. Real token usage logged via `response.usage_metadata`. See `docs/SETUP.md`.

## CLI
```bash
python src/main.py                    # today's topic
python src/main.py --date 2024-05-06  # backfill specific day
python src/main.py --recap-only       # force weekly recap now
python src/main.py --dry-run          # skip Drive uploads
python src/main.py --skip-validation  # bypass startup pre-flight check
```

## Quick Start
1. `pip install -r requirements.txt`
2. Copy `.env.example` → `.env`, fill in keys & Drive IDs
3. Drop `service-account.json` (service account JSON key) in repo root
4. Share your Drive folders with the SA email (Editor)
5. `python src/main.py --dry-run` — verify pipeline locally
6. Add GitHub secrets, push — Actions takes over

Full setup in [`docs/SETUP.md`](docs/SETUP.md). Content schedule in [`docs/Content-Calendar-2024.md`](docs/Content-Calendar-2024.md).

## Development
```bash
pip install -r requirements-dev.txt
pytest         # 74 tests
ruff check .   # lint
```

CI runs ruff + pytest on every push/PR via `.github/workflows/tests.yml`.

## Project Layout
```
consultant-academy/
├── .github/workflows/
│   ├── daily-routine.yml       # Mon–Fri cron
│   └── tests.yml               # ruff + pytest on push/PR
├── src/
│   ├── main.py                 # orchestrator + CLI
│   ├── agents/                 # 6 agents (5 LLM + Designer)
│   ├── integrations/           # Gemini, Drive (SA auth), 7d cache
│   ├── utils/                  # logger, cost, calendar parser, retry, docx_writer, cli
│   └── config/settings.py
├── tests/                      # 53 pytest tests
├── data/                       # cost log + research cache (auto-created, gitignored)
├── docs/                       # SETUP + Content Calendar
├── pyproject.toml              # ruff + pytest config
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```
