# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Does

Flask web app for curating CDISC Biomedical Concepts (BCs). Replaces spreadsheet/email workflows with a structured pipeline: ingest files → AI-assisted field mapping → SME review → governance approval → publish to CDISC Library.

## Running the App

```bash
# Install dependencies (once)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Required env var
export CDISC_API_KEY=your_key_here

# Start dev server
python app.py  # runs on http://localhost:5000
```

Database (`instance/cdisc_curation.db`) is auto-created on first run via `db.create_all()`.

## Linting

```bash
flake8 .
black --check .
```

Line length is set to 200 (black) / 999 (flake8). Flake8 ignores F401, F841, E711 — see `.flake8` for full ignore list.

There is no test suite.

## Architecture

**Route → Service → Model pattern:**
- `routes/` — Flask blueprints (one per feature area), handle HTTP and render templates
- `services/` — Business logic, API clients, parsers
- `models/` — SQLAlchemy ORM models
- `templates/` — Jinja2 + Bootstrap 5
- `extensions.py` — Shared `db` and `migrate` instances (avoids circular imports — always import from here)

**7 blueprints** registered in `app.py`:

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `dashboard` | `/` | KPI stats, live CDISC API data |
| `ingestion` | `/ingestion` | File upload → parse → queue → approve |
| `bc` | `/bc` | BC CRUD, export (XLSX/JSON/ODM-XML) |
| `ncit` | `/ncit` | NCI Thesaurus search & mapping |
| `specializations` | `/specializations` | Dataset specialization management |
| `governance` | `/governance` | 4-stage Kanban board |
| `audit` | `/audit` | Immutable change log |

**Key services:**
- `services/cdisc_api.py` — CDISC Library REST client with 5-min in-memory cache
- `services/ncit_api.py` — NCI EVS client (no auth required)
- `services/ingestion.py` — XLSX/CSV/JSON parser + fuzzy field mapper (`SequenceMatcher` similarity scoring)
- `services/export.py` — XLSX/JSON/ODM-XML exporter

**Ingestion pipeline flow:**
1. Upload file → parser extracts rows, groups by BC ID (handles multi-row DECs per BC)
2. Field mapper assigns canonical names + confidence scores
3. Rows stored in `IngestionRecord` DB table (not session cookies — avoids cookie overflow)
4. User approves/rejects → rows committed to `BiomedicalConcept` + `DataElementConcept`
5. `AuditLog` captures before/after state as JSON for every change

**Governance stages:** Provisional → SME Review → CDISC Approval → Published (tracked in `GovernanceRecord`)

## Config

All configuration is in `config.py` via environment variables:

| Var | Default | Purpose |
|-----|---------|---------|
| `CDISC_API_KEY` | `''` | CDISC Library API authentication |
| `SECRET_KEY` | `'dev-secret-key-change-in-prod'` | Flask session secret |
| `DATABASE_URL` | `sqlite:///cdisc_curation.db` | Database connection string |

CDISC API base: `https://api.library.cdisc.org/api/cosmos/v2`
NCIt API base: `https://api-evsrest.nci.nih.gov/api/v1`
