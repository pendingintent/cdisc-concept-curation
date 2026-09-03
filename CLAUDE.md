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
python app.py  # runs on http://localhost:8081 (override with PORT env var)
```

Database (`instance/cdisc_curation.db`) is brought to the Alembic migration
head automatically on startup by `db_bootstrap.ensure_db()` (fresh DBs are
built via `flask db upgrade`; pre-baseline DBs are stamped in place).
**Schema changes require an Alembic revision**: edit the model, then
`flask db migrate -m "..."` — `db.create_all()` is used only by tests.

## Linting

```bash
isort .
black .
flake8 .
```

Line length is 200 (black, isort, flake8). Flake8 ignores only E203/W503
(black conflicts) and E711 (SQLAlchemy `== None` filters); unused imports
(F401) and unused locals (F841) are errors. Dev tools are pinned in
`requirements-dev.txt`; CI runs the same lint + test steps.

## Testing

```bash
pytest --tb=short              # full suite (same command CI runs)
pytest tests/test_bc_routes.py -v   # single file
```

- Tests use an in-memory SQLite database via `TestConfig` in
  `tests/conftest.py`; an autouse `clean_db` fixture drops/creates all tables
  around every test. No env vars required; external API clients are mocked.
- Pre-commit (`.pre-commit-config.yaml`) runs black, flake8, and pytest on
  every commit.
- CI (`.github/workflows/ci.yml`) runs `pytest --tb=short` on Python 3.12.

## Architecture

**Route → Service → Model pattern:**
- `routes/` — Flask blueprints (one per feature area), handle HTTP and render templates
- `services/` — Business logic, API clients, parsers
- `models/` — SQLAlchemy ORM models
- `templates/` — Jinja2 + Bootstrap 5
- `extensions.py` — Shared `db` and `migrate` instances (avoids circular imports — always import from here)
- `tests/` - Unit tests

**10 blueprints** registered in `app.py`:

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `dashboard` | `/` | KPI stats, live CDISC API data |
| `ingestion` | `/ingestion` | File upload → parse → queue → approve |
| `bc` | `/bc` | BC CRUD, export (XLSX/JSON/ODM-XML) |
| `ncit` | `/ncit` | NCI Thesaurus search & mapping |
| `ncit_alignment` | `/ncit-alignment` | Background NCIt↔CDISC BC alignment run (`cdisc-bc-ncit-alignment` submodule), progress tracking, XLSX/JSON download |
| `loinc` | `/loinc` | LOINC code search (NLM Clinical Tables) |
| `specializations` | `/specializations` | Dataset specialization management |
| `governance` | `/governance` | 4-stage Kanban board |
| `audit` | `/audit` | Immutable change log |
| `notes` | `/notes` | Free-text notes on BCs/specializations |

**Key services:**
- `services/cdisc_api.py` — CDISC Library REST client with 5-min in-memory cache
- `services/ncit_api.py` — NCI EVS client (no auth required)
- `services/loinc_api.py` — NLM Clinical Tables LOINC search (optional Basic Auth via `LOINC_USER`/`LOINC_PASSWORD`)
- `services/ingestion.py` — XLSX/CSV/JSON parser + fuzzy field mapper (`SequenceMatcher` similarity scoring)
- `services/export.py` — XLSX/JSON/ODM-XML exporter
- `services/alignment_runner.py` — runs the `cdisc-bc-ncit-alignment` submodule's two-stage CLI pipeline as subprocesses from a background thread, tracking progress on an `AlignmentJob` row (see `models/alignment.py`)

**Ingestion pipeline flow:**
1. Upload file → parser extracts rows, groups by BC ID (handles multi-row DECs per BC)
2. Field mapper assigns canonical names + confidence scores
3. Rows stored in `IngestionRecord` DB table (not session cookies — avoids cookie overflow)
4. User approves/rejects → rows committed to `BiomedicalConcept` + `DataElementConcept`
5. `AuditLog` captures before/after state as JSON for every change

**Governance stages:** Provisional → SME Review → CDISC Approval → Published (tracked in `GovernanceRecord`)

**MCP server:** `mcp_server/` (run with `python -m mcp_server`; registered in
`.mcp.json`). Eight read tools (`list_bcs`, `get_bc`, `search_ncit`,
`get_ncit_concept`, `search_loinc`, `search_cdisc_library`, `get_library_bc`,
`list_review_queue`) and six write tools (`create_bc`, `update_bc`,
`map_ncit_to_bc`, `submit_bc_for_review`, `advance_governance`, `reject_bc`).
Handlers run inside a Flask app context via the shared app factory, so the
MCP process and the web app use the same `instance/cdisc_curation.db` and the
same service clients. Writes go through `services/bc_service.py` and
`services/governance_service.py` — the exact code path the routes use — with
`actor` defaulting to `"mcp"` in the audit trail. SQLite runs in WAL mode
with a 15s busy timeout (`extensions.py`) so the two writer processes
coexist. Tests call `mcp_server.server._dispatch` directly
(`tests/test_mcp_server.py`).

## Config

All configuration is in `config.py` via environment variables:

| Var | Default | Purpose |
|-----|---------|---------|
| `CDISC_API_KEY` | `''` | CDISC Library API authentication |
| `SECRET_KEY` | `'dev-secret-key-change-in-prod'` | Flask session secret |
| `DATABASE_URL` | `sqlite:///cdisc_curation.db` | Database connection string (resolves to `instance/cdisc_curation.db`) |
| `PORT` | `8081` | Dev server port |
| `LOINC_USER` / `LOINC_PASSWORD` | unset | Optional Basic Auth for the NLM LOINC API |
| `ALIGNMENT_SUBMODULE_DIR` | `cdisc-bc-ncit-alignment/` (repo root) | Path to the alignment submodule, used as `cwd` when its CLI stages are run as subprocesses |

CDISC API base: `https://api.library.cdisc.org/api/cosmos/v2`
NCIt API base: `https://api-evsrest.nci.nih.gov/api/v1`


## Conventions
- Always follow test driven development principles.
- When updating Python code, ensure the associated unit tests are updated accordingly.
- Execute the appropriate unit tests after updating Python code.
- Any front-end/UI work — the `frontend-design` skill, the `cdisc-frontend-dev` agent, or hand-written templates/CSS — MUST apply the `cdisc-brand-guidelines` skill (CDISC Blue `#134678`, Purple `#553278`, Orange `#D57E00`, Green `#286040`; Arial). Invoke it before creating or updating any UI, not just when the user says "on-brand." 