# CDISC Biomedical Concept Curation Platform

A Flask web application for curating CDISC Biomedical Concepts (BCs). It replaces ad hoc spreadsheet and email workflows with a structured pipeline: ingest files, AI-assist field mapping, review, govern, and publish. The platform targets >=90% AI field-mapping accuracy and <5 min ingest-to-queue time (SMART goal Q1-Q2 2026).

---

## Prerequisites

- Python 3.10 or later
- pip

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/cdisc-concept-curation.git
cd cdisc-concept-curation

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Dependencies installed

| Package | Version | Purpose |
|---------|---------|---------|
| flask | 3.0.3 | Web framework |
| flask-sqlalchemy | 3.1.1 | ORM |
| flask-migrate | 4.0.7 | DB schema migrations |
| pandas | 2.2.2 | XLSX/CSV parsing |
| openpyxl | 3.1.2 | Excel file I/O |
| requests | 2.32.3 | HTTP client for CDISC and NCIt APIs |
| lxml | 5.2.2 | ODM-XML export |

---

## Configuration

The application is configured entirely through environment variables.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CDISC_API_KEY` | Yes | _(empty)_ | API key for the CDISC Library. All CDISC API calls will fail without it. |
| `SECRET_KEY` | No | `dev-secret-key-change-in-prod` | Flask session secret. Set a strong value in production. |
| `DATABASE_URL` | No | `sqlite:///cdisc_curation.db` | SQLAlchemy database URI. Defaults to a local SQLite file. |

Set environment variables before running the app:

```bash
export CDISC_API_KEY=your_cdisc_api_key_here
export SECRET_KEY=a-strong-random-secret           # recommended for non-dev use
```

---

## Running the App

```bash
python app.py
```

The Flask development server starts on `http://localhost:5000`. The SQLite database file (`cdisc_curation.db`) is created automatically on first run.

> **Note:** `python app.py` uses Flask's built-in development server. Do not use this in production. Use a WSGI server such as gunicorn instead.

---

## Key Screens

The sidebar navigation exposes seven screens, accessible at these URL prefixes:

| Screen | URL | What it does |
|--------|-----|-------------|
| Dashboard | `/` | KPI cards (total BCs, pending review, published), governance pipeline chart, recent submissions table |
| Ingestion | `/ingestion` | Upload XLSX, CSV, or JSON files; AI field mapper assigns confidence scores; approve or reject rows to the database |
| BCs | `/bc` | Browse, create, edit, and delete Biomedical Concepts including all CDISC fields and Data Element Concept sub-records |
| NCIT Mapping | `/ncit` | Search the NCI Thesaurus, resolve low-confidence mappings, and confirm NCIt codes for each BC |
| Specializations | `/specializations` | View and generate SDTM/CDASH dataset specializations and CRF variable mappings |
| Governance | `/governance` | 4-stage Kanban board (Provisional > SME Review > CDISC Approval > Published) with advance and reject actions |
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
│   ├── bc.py                     # BiomedicalConcept, DataElementConcept
│   ├── specialization.py         # DatasetSpecialization
│   ├── governance.py             # GovernanceRecord
│   └── audit.py                  # AuditLog
├── routes/                       # 7 Flask blueprints
│   ├── dashboard.py
│   ├── ingestion.py
│   ├── bc.py
│   ├── ncit.py
│   ├── specializations.py
│   ├── governance.py
│   └── audit.py
├── services/
│   ├── cdisc_api.py              # CDISC Library API client
│   ├── ncit_api.py               # NCI EVS REST API client (no key required)
│   ├── ingestion.py              # File parser and AI field mapper
│   └── export.py                 # XLSX, JSON, ODM-XML export
├── templates/
│   ├── base.html                 # Bootstrap 5 sidebar layout
│   └── *.html                    # One template per screen
├── static/
│   ├── css/custom.css
│   └── js/main.js
└── files/                        # Reference documents (read-only)
    ├── implementation.md         # Architecture specification
    └── result.md                 # Build summary
```

---

## External APIs

- **CDISC Library** — `https://api.library.cdisc.org/api/cosmos/v2` — requires `CDISC_API_KEY`
- **NCI EVS REST API** — `https://api-evsrest.nci.nih.gov/api/v1` — no key required
