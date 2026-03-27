# CDISC Biomedical Concept Curation Application

## Context

The CDISC BC Curation Team manually creates and curates Biomedical Concepts (BCs) for the CDISC Library via ad hoc email and spreadsheets. Goal 1 of the SMART goals (Q1-Q2 2026) is to build a multi-format BC ingestion and AI parsing engine that replaces this process, achieving ≥90% AI field-mapping accuracy and <5 min ingest-to-queue time. This Flask/Jinja application provides the full curation workflow: ingest → AI-assist → internal review → governance approval → publish.

---

## Directory Structure

```
cdisc-concept-curation/
├── app.py                        # Flask app factory
├── config.py                     # Config (CDISC_API_KEY from env)
├── requirements.txt
├── models/
│   ├── __init__.py
│   ├── bc.py                     # BiomedicalConcept, DataElementConcept
│   ├── specialization.py         # DatasetSpecialization
│   ├── governance.py             # GovernanceRecord
│   └── audit.py                  # AuditLog
├── routes/
│   ├── __init__.py
│   ├── dashboard.py
│   ├── ingestion.py              # File upload + AI parse queue
│   ├── bc.py                     # BC detail CRUD
│   ├── ncit.py                   # NCIT mapping resolution
│   ├── specializations.py
│   ├── governance.py             # Kanban board
│   └── audit.py
├── services/
│   ├── cdisc_api.py              # CDISC Library API client
│   ├── ncit_api.py               # NCIt EVS REST API client
│   ├── ingestion.py              # XLSX/CSV/JSON parser + AI field mapper
│   └── export.py                 # XLSX, JSON, ODM-XML export
├── templates/
│   ├── base.html                 # Sidebar nav, Bootstrap 5
│   ├── dashboard.html
│   ├── ingestion.html
│   ├── bc_detail.html
│   ├── ncit_mapping.html
│   ├── specializations.html
│   ├── governance.html
│   └── audit.html
└── static/
    ├── css/custom.css
    └── js/main.js
```

---

## Data Models (SQLAlchemy + SQLite)

### BiomedicalConcept
- `bc_id` (PK, NCIt C-code), `short_name`, `definition`
- `ncit_code`, `parent_bc_id` (FK self-ref)
- `bc_categories` (semicolon-separated), `synonyms`
- `result_scales`, `system`, `system_name`, `code`
- `package_date`, `status` (provisional/sme_review/cdisc_approval/published)
- `submitter`, `created_at`, `updated_at`, `history_of_change`

### DataElementConcept
- `dec_id` (PK), `bc_id` (FK), `ncit_dec_code`
- `dec_label`, `data_type`, `example_set`
- `required`, `generic_dec`, `template_type`

### DatasetSpecialization
- `vlm_group_id` (PK), `bc_id` (FK)
- `domain` (SDTM/CDASH), `short_name`
- `variables` (JSON: list of variable mappings)

### GovernanceRecord
- `id` (PK), `bc_id` (FK)
- `stage` (0–4), `action`, `actor`, `comment`
- `created_at`

### AuditLog
- `id` (PK), `entity_type`, `entity_id`
- `action`, `actor`, `before_state` (JSON), `after_state` (JSON)
- `timestamp`

---

## Flask Blueprints

| Blueprint | Prefix | Key Routes |
|-----------|--------|------------|
| dashboard | `/` | `GET /` |
| ingestion | `/ingestion` | `GET /`, `POST /upload`, `GET /queue`, `POST /approve/<id>` |
| bc | `/bc` | `GET /`, `GET /<bc_id>`, `POST /`, `PUT /<bc_id>`, `DELETE /<bc_id>` |
| ncit | `/ncit` | `GET /mapping`, `POST /resolve`, `GET /search` |
| specializations | `/specializations` | `GET /`, `GET /<vlm_group_id>`, `POST /generate` |
| governance | `/governance` | `GET /board`, `POST /advance/<bc_id>`, `POST /reject/<bc_id>` |
| audit | `/audit` | `GET /` with filters |

---

## Services

### `services/cdisc_api.py`
- `CDISCApiClient(api_key)` — reads `CDISC_API_KEY` from env
- `get_biomedical_concepts(page, size)` — list existing BCs
- `get_bc(bc_id)` — fetch single BC
- `publish_bc(bc_data)` — POST new BC to library
- `check_duplicate(short_name)` — deduplication check

### `services/ncit_api.py`
- `NCItApiClient()` — uses EVS REST API (no key required)
- `search_concept(term)` → list of matches with codes + definitions
- `get_concept(ncit_code)` → full concept with synonyms
- `get_preferred_name(ncit_code)` → string

### `services/ingestion.py`
- `parse_xlsx(file)` → list of BC dicts (using openpyxl/pandas)
- `parse_csv(file)` → list of BC dicts
- `parse_json(file)` → list of BC dicts
- `map_fields(raw_dict)` → normalized BC dict with confidence scores
- `validate_bc(bc_dict)` → list of validation errors per curation rules
- `deduplicate(bc_list)` → flag duplicates against existing BCs

### `services/export.py`
- `export_xlsx(bc_list)` → BytesIO
- `export_json(bc_list)` → str
- `export_odm_xml(bc_list)` → str

---

## Templates

### `base.html`
Bootstrap 5 layout with collapsible sidebar nav (matching `cdisc_bc_ai_platform.html`):
- Links: Dashboard, Ingestion, BCs, NCIT Mapping, Specializations, Governance, Audit Trail
- Flash messages, active nav highlighting

### Per-screen templates
- **dashboard.html**: KPI cards (total BCs, pending review, published), governance pipeline chart, recent submissions table
- **ingestion.html**: File upload form (XLSX/CSV/JSON), parsed entries table with AI confidence scores, batch approve/reject
- **bc_detail.html**: Full BC form (all fields), DEC sub-table, NCIT lookup inline, save/submit-for-review actions
- **ncit_mapping.html**: Conflict cards with AI recommendations, manual resolution UI, confidence scores
- **specializations.html**: SDTM/CDASH variable table, CRF preview
- **governance.html**: 4-column Kanban (Provisional → SME Review → CDISC Approval → Published), drag-to-advance via JS
- **audit.html**: Filterable table (entity, action, actor, date range)

---

## Implementation Phases

### Phase 1 — Core Foundation (MVP)
1. `requirements.txt` + `config.py` + `app.py` (Flask factory, SQLAlchemy, SQLite)
2. All SQLAlchemy models + `flask db init/migrate/upgrade`
3. `base.html` with sidebar nav (Bootstrap 5, matching mockup styling)
4. Dashboard screen (static KPI cards, empty tables)
5. BC list + detail screens (CRUD via CDISC API + local DB)
6. `CDISCApiClient` service

### Phase 2 — Ingestion + NCIt
7. File ingestion service (XLSX/CSV/JSON parsing with pandas)
8. AI field mapper (`map_fields` using column name heuristics + NCIt lookup)
9. Ingestion queue screen (upload → parse → review → approve)
10. `NCItApiClient` service
11. NCIT Mapping screen (conflict resolution UI)

### Phase 3 — Governance + Specializations
12. Governance Kanban board + stage transitions
13. Audit log middleware (auto-log all BC state changes)
14. Audit trail screen
15. Specializations (SDTM/CDASH template generation)
16. DEC template application (Default, Vital Signs, etc.)

### Phase 4 — Export + Polish
17. Export service (XLSX, JSON, ODM-XML)
18. Deduplication check on ingest
19. Curation validation rules engine (from `BC Curation Principles`)
20. Notifications/alerts screen
21. Final styling pass to match `cdisc_bc_ai_platform.html`

---

## Critical Files to Create/Modify

- `app.py` — Flask app factory
- `config.py` — env var config (`CDISC_API_KEY`)
- `requirements.txt` — flask, flask-sqlalchemy, flask-migrate, pandas, openpyxl, requests, lxml
- `models/bc.py`, `models/governance.py`, `models/audit.py`
- `services/cdisc_api.py`, `services/ncit_api.py`, `services/ingestion.py`
- `templates/base.html` + all 7 screen templates

## Reference Files (read-only)
- `files/cdisc_bc_ai_platform.html` — UI mockup to match
- `files/BC Examples.xlsx` — BC field structure
- `files/BC DEC Templates.xlsx` — DEC template definitions
- `files/BC Curation Principles and Completion GLs.xlsx` — validation rules
- `files/BC Governance.docx` — workflow stages and roles

---

## Verification

1. `python app.py` starts Flask dev server without errors
2. Navigate to `http://localhost:5000` — dashboard loads with sidebar
3. Upload a sample `BC Examples.xlsx` via Ingestion → rows appear in queue
4. Open a BC detail page → all fields editable, NCIT lookup returns results
5. Advance a BC through governance stages → Kanban updates, audit log records action
6. Export a BC as JSON → valid CDISC BC schema output
7. `CDISC_API_KEY` env var used for all CDISC API calls (no hard-coded keys)
