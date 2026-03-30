# Project Progress

## Overview

CDISC Biomedical Concept Curation — a Flask/Jinja web application for curating, governing, and exporting CDISC Biomedical Concepts (BCs) and Data Element Concepts (DECs). Current phase: **MVP Complete / Initial Build**.

## Feature Status

| Module | Status | Details |
|--------|--------|---------|
| Flask App Foundation | ✅ Complete | `app.py`, `extensions.py`, `config.py` |
| Database Models | ✅ Complete | BC, DEC, Governance, Audit, Ingestion, Specialization |
| Dashboard | ✅ Complete | KPI stats, live CDISC Library API counts + BC/Spec panels, route `/` |
| Ingestion (Upload + Parse) | ✅ Complete | XLSX/CSV/JSON upload, AI field mapping, BC/DEC grouping |
| BC CRUD + Export | ✅ Complete | JSON/XLSX/ODM-XML export |
| NCIt Mapping | ✅ Complete | EVS REST API search + mapping resolution |
| Dataset Specializations | ✅ Complete | Full CRUD management |
| Governance Workflow | ✅ Complete | 4-stage Kanban board |
| Audit Trail | ✅ Complete | Filterable audit log |
| CDISC Library API Client | ✅ Complete | `services/cdisc_api.py` |
| NCIt EVS API Client | ✅ Complete | `services/ncit_api.py` |
| Export Service | ✅ Complete | XLSX, JSON, ODM-XML |
| UI (Bootstrap 5) | ✅ Complete | Sidebar layout, custom CDISC design tokens |

## Daily Changelog

### 2026-03-30

#### Dashboard: API Integration + BC/Specialization Display

- Fixed variable name mismatches in `routes/dashboard.py` (`recent_bcs` -> `recent_submissions`, `pipeline` -> `governance_items`) that were causing empty dashboard tables
- Added `DatasetSpecialization` query to `routes/dashboard.py` so the dashboard reflects locally stored specializations
- `routes/dashboard.py` now calls the CDISC Library API for live BC and specialization counts and lists on every dashboard load (with cache)
- Fixed `services/cdisc_api.py` `get_biomedical_concepts()` to correctly parse the `_links.biomedicalConcepts` array from the API response (~1127 BCs returned)
- Added `get_dataset_specializations()` to `services/cdisc_api.py` using the correct endpoint `/mdr/specializations/datasetspecializations` (~1123 specs returned)
- Added 5-minute in-memory cache to `services/cdisc_api.py` to avoid redundant API calls on rapid page refreshes
- Fixed `check_duplicate()` in `services/cdisc_api.py` to use the `title` field from link objects (was using wrong key)
- Added two new panels to `templates/dashboard.html`: "CDISC Library - Biomedical Concepts" (first 50 of ~1127) and "CDISC Library - Dataset Specializations" (first 50 of ~1123)
- Updated KPI cards in `templates/dashboard.html`: "BCs in CDISC Library" and "Dataset Specializations" now display live counts from the API rather than static zeros

### 2026-03-27
- ✅ Built complete Flask/Jinja web application from scratch for CDISC BC curation
- ✅ Created `app.py` — Flask application factory with blueprint registration
- ✅ Created `extensions.py` — SQLAlchemy + Flask-Migrate instances (avoids circular imports)
- ✅ Created `config.py` — Config class using `CDISC_API_KEY` env var
- ✅ Created `requirements.txt` — All dependencies pinned
- ✅ Created `models/bc.py` — `BiomedicalConcept` + `DataElementConcept` SQLAlchemy models
- ✅ Created `models/specialization.py` — `DatasetSpecialization` model
- ✅ Created `models/governance.py` — `GovernanceRecord` model (4-stage Kanban)
- ✅ Created `models/audit.py` — `AuditLog` model
- ✅ Created `models/ingestion.py` — `IngestionRecord` model (DB-backed session storage)
- ✅ Created `routes/dashboard.py` — Dashboard with KPI stats
- ✅ Created `routes/ingestion.py` — File upload + parse queue + approve/reject flow
- ✅ Created `routes/bc.py` — BC CRUD + JSON/XLSX/ODM-XML export
- ✅ Created `routes/ncit.py` — NCIt concept search and mapping resolution
- ✅ Created `routes/specializations.py` — Dataset specialization management
- ✅ Created `routes/governance.py` — 4-stage Kanban governance workflow
- ✅ Created `routes/audit.py` — Filterable audit trail
- ✅ Created `services/cdisc_api.py` — CDISC Library REST API client
- ✅ Created `services/ncit_api.py` — NCIt EVS REST API client
- ✅ Created `services/ingestion.py` — XLSX/CSV/JSON parser with AI field mapping + BC/DEC grouping
- ✅ Created `services/export.py` — XLSX, JSON, ODM-XML export
- ✅ Created `templates/base.html` — Bootstrap 5 sidebar layout
- ✅ Created all 8 feature templates (dashboard, ingestion, bc_list, bc_detail, ncit_mapping, specializations, governance, audit)
- ✅ Created `static/css/custom.css` — Custom design tokens matching CDISC mockup
- ✅ Created `static/js/main.js` — Interactive JS (NCIt lookup, Kanban drag/drop, DEC table, file upload)
- 🐛 Fixed circular import — moved `db`/`migrate` instances to `extensions.py`
- 🐛 Fixed ingestion form 405 error — corrected form `action` to `/ingestion/upload`
- 🐛 Fixed session cookie size overflow (287 records exceeding 4KB limit) — replaced cookie session with DB-backed `IngestionRecord` model
- 🐛 Fixed XLSX DEC sub-rows being parsed as separate BCs — added `_group_by_bc()` grouping logic in `services/ingestion.py`
- ✅ Initial commit pushed to GitHub — all 50 files, 5,828 insertions
- 📝 Created `files/implementation.md` — implementation plan
- 📝 Created `files/result.md` — build summary
