# CDISC Biomedical Concept Curation Platform

A Flask web application for curating CDISC Biomedical Concepts (BCs). It replaces ad hoc spreadsheet and email workflows with a structured pipeline: ingest files, AI-assist field mapping, review, govern, and publish. The platform targets >=90% AI field-mapping accuracy and <5 min ingest-to-queue time (SMART goal Q1-Q2 2026).

---

## Prerequisites

- Python 3.11 or 3.12
- pip

---

## Quick Start (no git required)

If you're not a developer and just want to run the app locally: download the latest
release archive from the [Releases page](https://github.com/pendingintent/cdisc-concept-curation/releases)
(`.zip` for Windows, `.tar.gz` for Mac/Linux), extract it, and double-click the
installer for your platform:

- **Windows**: `Install (Windows).bat`
- **Mac**: `Install (Mac).command`
- **Linux**: `install.sh`

The installer creates a virtual environment, installs dependencies, asks for your
CDISC API key, sets up the database, and leaves behind a `Start` launcher
(`Start.bat` / `Start.command` / `start.sh`) — double-click that any time to run the
app. No git, and no command line beyond double-clicking, required.

Maintainers cutting a release: see [RELEASING.md](RELEASING.md).

## Installation (for developers)

```bash
# 1. Clone the repository
git clone https://github.com/pendingintent/cdisc-concept-curation.git
cd cdisc-concept-curation

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install git hooks for code quality (for developers only)
pre-commit install
```

Pre-commit hooks will now run automatically before each `git commit`, enforcing code formatting (black) and linting (flake8).

## Submodules

`cdisc-bc-ncit-alignment/` is a git submodule ([pendingintent/cdisc-bc-ncit-alignment](https://github.com/pendingintent/cdisc-bc-ncit-alignment)) containing standalone tools for aligning CDISC Biomedical Concepts with NCI Thesaurus codes. It is not part of the Flask app's import path — see its own README for setup and usage.

```bash
# If you haven't cloned yet, pull submodules along with the main repo:
git clone --recurse-submodules https://github.com/pendingintent/cdisc-concept-curation.git

# If you already cloned without --recurse-submodules:
git submodule update --init

# To pull the latest changes from the submodule's remote main branch:
git submodule update --remote cdisc-bc-ncit-alignment
```

The last command updates your working copy and stages the new submodule commit in the parent repo; commit that change (`git add cdisc-bc-ncit-alignment && git commit`) to record which submodule commit this repo depends on.

## Configuration

### Environment Variables

The application is configured entirely through environment variables, loaded
automatically from a `.env` file in the repo root if one exists (via
`python-dotenv`) — copy `.env.example` to `.env` and fill in your values, or set
real environment variables instead.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CDISC_API_KEY` | Yes | _(empty)_ | API key for the CDISC Library. All CDISC API calls will fail without it. |
| `CDISC_SUBSCRIPTION_KEY` | No | _(empty)_ | When set, used instead of `CDISC_API_KEY` (sent as the `Ocp-Apim-Subscription-Key` header). |
| `SECRET_KEY` | No | `dev-secret-key-change-in-prod` | Flask session secret. Set a strong value in production. |
| `DATABASE_URL` | No | `sqlite:///cdisc_curation.db` | SQLAlchemy database URI. Defaults to a local SQLite file. |
| `PORT` | No | `8081` | Dev server port. |
| `FLASK_DEBUG` | No | `1` | Set to `0` to disable Flask's debugger/auto-reloader (recommended outside active development). |
| `LOINC_USER` | No | _(empty)_ | Optional Basic Auth username for the NLM Clinical Tables API. If set, `LOINC_PASSWORD` must also be set. |
| `LOINC_PASSWORD` | No | _(empty)_ | Optional Basic Auth password for the NLM Clinical Tables API. If set, `LOINC_USER` must also be set. |
| `ALIGNMENT_SUBMODULE_DIR` | No | `<app_dir>/cdisc-bc-ncit-alignment` | Path to the alignment submodule checkout. |

Set environment variables before running the app (or put them in `.env`):

```bash
export CDISC_API_KEY=your_cdisc_api_key_here
export SECRET_KEY=a-strong-random-secret           # recommended for non-dev use
```
## Running the App

```bash
python app.py
```

The Flask development server starts on `http://localhost:8081` (override with the `PORT` env var). On startup the app brings the SQLite database (`instance/cdisc_curation.db`) to the current Alembic migration head automatically: fresh databases are built with `flask db upgrade`, and databases created before the migration baseline was squashed (2026-07-08) are stamped in place. If startup reports a schema that cannot be auto-migrated, recreate the database or run `flask db stamp head` after bringing it up to date manually.

Schema changes are managed exclusively through Flask-Migrate/Alembic — edit the model, then run `flask db migrate -m "describe change"` and commit the generated revision.

> **Note:** `python app.py` uses Flask's built-in development server. Do not use this in production. Use a WSGI server such as gunicorn instead.

---

## Code Quality

Code style and linting are enforced automatically via [pre-commit](https://pre-commit.com) hooks (configured in [`.pre-commit-config.yaml`](.pre-commit-config.yaml)):

- **black** (26.3.1) — enforces consistent Python formatting with a line length of 200 characters (configured in `pyproject.toml`)
- **flake8** (7.3.0) — enforces PEP8 linting rules (configured in [`.flake8`](.flake8))

These hooks run automatically before each `git commit`. If black reformats any files, the commit is blocked and you must `git add` the reformatted files and retry the commit.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Tests use an in-memory SQLite database and the Flask test client. No environment variables are required to run tests.

To run a single test file:

```bash
python -m pytest tests/test_ingestion_service.py -v
```

To run a single test:

```bash
python -m pytest tests/test_bc_routes.py::TestCreateBc::test_creates_bc_and_redirects -v
```

---

## Key Screens

The sidebar navigation exposes seven screens, accessible at these URL prefixes:

| Screen | URL | What it does |
|--------|-----|-------------|
| Dashboard | `/` | KPI cards (total BCs, pending review, published), governance pipeline chart with concurrent CDISC API fetches (ThreadPoolExecutor), recent submissions table |
| Ingestion | `/ingestion` | Upload XLSX, CSV, or JSON files; AI field mapper assigns confidence scores; approve or reject rows to the database |
| BCs | `/bc` | Browse, create, edit, and delete Biomedical Concepts; LOINC code entry with asynchronous metadata fetch — fetch triggers automatically on page load if a LOINC code is set and no cached metadata exists, stores result in database for fast future loads; click "Search LOINC" button to manually trigger fresh fetch; click "Clear" button to remove LOINC code, metadata, and spinner; NCIt concept selection with live search and one-click integration — click "Use this concept" to fetch full metadata asynchronously (preferred name, synonyms, description, parent concepts, child concepts, semantic type, and NCIt Browser link); click "Clear" button to remove NCIt code, metadata, and parent BC ID; all available definitions displayed with source attribution as `[SOURCE] definition text` in the References section; query parameters `/bc/new?ncit_code=...&ncit_name=...&ncit_definition=...` pre-populate BC fields on page load; `parent_bc_id` auto-filled from first parent concept's code; form inputs use Jinja2 `or ''` pattern to prevent rendering Python `None` as literal string `"None"` in HTML attributes; Data Element Concept sub-records |
| NCIT Mapping | `/ncit` | Search the NCI Thesaurus, resolve low-confidence mappings, and confirm NCIt codes for each BC |
| Specializations | `/specializations` | View and generate SDTM/CDASH dataset specializations and CRF variable mappings |
| Governance | `/governance` | 4-stage Kanban board (Provisional > SME Review > CDISC Approval > Published) with advance and reject actions; export published BCs as XLSX (BC_LB worksheet format with 18 columns) via "Export Published BCs" button |
| Audit Trail | `/audit` | Immutable log of every create, update, and status change with before/after state, filterable by entity, action, actor, and date |

---

## Project Structure

```
cdisc-concept-curation/
├── app.py                        # Flask app factory
├── config.py                     # Config (reads env vars)
├── extensions.py                 # db + migrate instances (avoids circular imports)
├── requirements.txt
├── models/
│   ├── bc.py                     # BiomedicalConcept (loinc_metadata and ncit_metadata store API responses as JSON), DataElementConcept
│   ├── specialization.py         # DatasetSpecialization
│   ├── governance.py             # GovernanceRecord
│   └── audit.py                  # AuditLog
├── routes/                       # 8 Flask blueprints
│   ├── dashboard.py              # Concurrent CDISC API fetches (ThreadPoolExecutor), KPI cards
│   ├── ingestion.py              # File upload and AI field mapper
│   ├── bc.py                     # Create, edit, detail views; `/bc/new` accepts query parameters (`ncit_code`, `ncit_name`, `ncit_definition`) to pre-populate BC fields on page load; `/bc/<bc_id>/clear-ncit` and `/bc/<bc_id>/clear-loinc` endpoints to remove codes and metadata; NCIt metadata fetch on demand; auto-fills `parent_bc_id` from first parent concept code; LOINC metadata auto-fetched and saved on detail page load
│   ├── ncit.py                   # GET /ncit/search and GET /ncit/concept/<code> JSON endpoints with full metadata, children, and NCIt Browser links
│   ├── loinc.py                  # GET /loinc/search JSON API endpoint
│   ├── specializations.py        # Dataset specializations and CRF mappings
│   ├── governance.py             # Kanban board and status workflows; `/governance/export` route for exporting published BCs as XLSX
│   └── audit.py                  # Immutable change log with filters
├── services/
│   ├── cdisc_api.py              # CDISC Library API client with stale-while-refresh caching (5-min fresh TTL, 1-hour stale fallback)
│   ├── ncit_api.py               # NCI EVS REST API client with in-memory caching (5-min fresh TTL, 1-hour stale fallback); search uses include="summary" for richer metadata; full concept detail with all definitions prioritized by source via `_pick_definition()` helper (CDISC > NCI > first available), parent and child concepts with codes, semantic type, and NCIt Browser reference links
│   ├── loinc_api.py              # NLM Clinical Tables API client (optional Basic Auth, metadata caching)
│   ├── ingestion.py              # File parser and AI field mapper
│   └── export.py                 # XLSX, JSON, ODM-XML export; `export_governance_xlsx()` exports stage-3 BCs in BC_LB worksheet format (BC fields, DEC fields, History of Change)
├── templates/
│   ├── base.html                 # Bootstrap 5 sidebar layout
│   └── *.html                    # One template per screen
├── static/
│   ├── css/custom.css
│   └── js/main.js
├── files/                        # Reference documents (read-only)
│   ├── implementation.md         # Architecture specification
│   └── result.md                 # Build summary
└── cdisc-bc-ncit-alignment/      # Git submodule — NCIt <-> CDISC BC alignment tools (see its own README)
```

---

## External APIs

The platform integrates with three external APIs to provide rich concept metadata:

- **CDISC Library** (`https://api.library.cdisc.org/api/cosmos/v2`) — Requires `CDISC_API_KEY`. Used in Dashboard and BC Library detail views. Implements stale-while-refresh caching (5-min fresh TTL, 1-hour stale fallback) to gracefully handle transient failures.
- **NCI EVS REST API** (`https://api-evsrest.nci.nih.gov/api/v1`) — No authentication required. Returns NCIt concept definitions with source attribution, parent and child concepts, semantic types, and browser links. Search requests use `include=summary` for richer metadata. Integrated into BC detail views via `/bc/fetch_metadata` endpoint with on-demand asynchronous full-concept fetch (no LOINC concurrent fetches). Prioritizes definitions by source using `_pick_definition()` helper: CDISC > NCI > first available. Displays all available definitions with source attribution as `[SOURCE] definition text` in the References section. Displays parent and child concepts with codes. Includes direct links to the NCIt Browser (via `https://ncithesaurus.nci.nih.gov/ncitbrowser/ConceptReport.jsp?dictionary=NCI_Thesaurus&code=<code>`) for each concept. Auto-fills `parent_bc_id` from first parent concept code. Implements in-memory caching (5-min fresh TTL, 1-hour stale fallback) to serve cached data rapidly and degrade gracefully when the service is unavailable.
- **NLM Clinical Tables API (LOINC)** (`https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search`) — Optional Basic Auth via `LOINC_USER` / `LOINC_PASSWORD`. Returns LOINC metadata including LONG_COMMON_NAME, SHORTNAME, COMPONENT, METHOD_TYP, units, datatype, and copyright notices. Integrated into BC detail views via `/bc/fetch_metadata` endpoint with on-demand asynchronous metadata fetch — when a LOINC code is set and no cached metadata exists, the fetch triggers automatically on page load; metadata is cached in the database and formatted in a grid display (Long Common Name, Short Name, Component, Property, Method Type, Units, Data Type, Consumer Name, Related Names, Answer Lists, copyright status, and links).
