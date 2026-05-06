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
Calendar → Research → Expert(by-pillar) → Industry → FactChecker → Translator → Editor → Connector → Designer → Drive → Index
                          ↓                   ↓            ↓                       ↓         ↓                              ↓
                  4 templates per pillar  6 sectors  no-halluc gate          regen if      "อ่านเพิ่ม"                  master index
                                                                              quality fails  links
```

7 LLM agents (Research, Expert, Industry, FactChecker, Translator, Editor, Recap) + 2 local helpers (Designer, IndexBuilder/Connector). Research is cached locally for 7 days; expired entries auto-pruned. Knowledge Base is organized by pillar → cluster → level with an auto-regenerated master index so new hires can follow a single file to catch up.

### Anti-hallucination guardrails

- **Research / Expert / Translator** prompts forbid fabricating company names, specific numbers without source, or invented standards. Range values (`15–25%`) and qualifiers (`ประมาณ`) are required when source is missing.
- **FactChecker** (Pro 2.5 by default) runs heuristic regex checks for company names, ungrounded percentages, person names. If any flag triggers, sends content + research data to Pro to soften unverifiable claims.
- **Editor** does a final regex spot-check for leftover company names and structural quality (Consultant Move, glossary, ≥3 numbers with units, length ≤600 words).
- **Pillar-aware Expert prompts** (5 templates): TECHNICAL (equipment + ROI), INDUSTRY (sector profile), FRAMEWORK (named methodology), SOFTSKILL (**must use** a named framework: BANT/MEDDIC/SPIN/Sandler/Challenger/RACI/...), COMPLIANCE (real Thai/international standards: พ.ร.บ. 2535, ISO 50001/14001, GMP, HACCP, มอก./TIS, LEED/TREES).

### Industry coverage (6 families)

Food & Pharma + Cold Storage | General Manufacturing | Petrochem & Chemical | Heavy (Steel/Cement/**Glass**) | **Large Commercial Buildings** | Waste Management.

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
pytest         # 112 tests
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
