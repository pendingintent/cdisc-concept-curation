---
name: Project Foundation
description: Core structure of the CDISC Biomedical Concept Curation Flask app — entry points, blueprints, models, and database setup
type: project
---

The app uses a Flask application factory pattern in `app.py`. `db` and `migrate` are module-level singletons; blueprints are imported and registered inside `create_app()`.

**Blueprints registered (name → url_prefix):**
- `dashboard` → `/`
- `ingestion` → `/ingestion`
- `bc` → `/bc`
- `ncit` → `/ncit`
- `loinc` → `/loinc`
- `specializations` → `/specializations`
- `governance` → `/governance`
- `audit` → `/audit`

Route files live in `routes/<name>.py`. Each exports `bp = Blueprint('<name>', __name__)`.

**Models** (`models/`):
- `bc.py` — `BiomedicalConcept`, `DataElementConcept`
- `specialization.py` — `DatasetSpecialization`
- `governance.py` — `GovernanceRecord`
- `audit.py` — `AuditLog`
- `ingestion.py` — `IngestionRecord` (staging rows for the upload queue)

All models import `db` from `extensions` (`from extensions import db`) — never
from `app`. `extensions.py` holds the shared `db`/`migrate` singletons.

Database: SQLite at `sqlite:///cdisc_curation.db` by default. Tables are auto-created via `db.create_all()` inside `create_app()`.

Virtual environment: `.venv/` — use `.venv/bin/pip` and `.venv/bin/python` for all commands.

**Flask-SQLAlchemy version:** 3.1.1. `.query.get_or_404(pk)` is available on the Flask-SQLAlchemy `Query` class and works fine. `.query.get(pk)` also still works (not yet removed in this version). Avoid `db.session.get()` unless needed for clarity.

**Services** (`services/`):
- `ingestion.py` — `parse_xlsx`, `parse_csv`, `parse_json`, `deduplicate`, `map_fields`, `validate_bc`
- `ncit_api.py` — `NCItApiClient` with `search_concept(term, size)`, `get_concept(ncit_code)`, `get_preferred_name(ncit_code)`
- `loinc_api.py` — `LoincApiClient.search(term)` against NLM Clinical Tables (optional Basic Auth)
- `export.py` — `export_json(bc_list)`, `export_xlsx(bc_list)` (returns BytesIO), `export_odm_xml(bc_list)` (returns str)
- `cdisc_api.py` — `CDISCApiClient`, a full CDISC Library REST client with a stale-tolerant in-memory cache (not a stub)

**Route implementations are complete** (as of 2026-03-27). All 24 URL rules register successfully. Key route decisions:
- `bc.export` is a static path `/bc/export` — must be defined before `bc.detail` (`/bc/<bc_id>`) to avoid Flask treating "export" as a bc_id.
- `governance` blueprint has no `/` route — board is at `/governance/board`.
- `ncit.index` at `/ncit/` redirects to `ncit.mapping`.
- Ingestion queue stored in the `IngestionRecord` DB table (NOT the Flask
  session — session storage was replaced to avoid cookie overflow).
- `_save_decs()` in `bc.py` does a full delete-then-reinsert of DECs on every save.

**Why:** Routes were stubs; wired up 2026-03-27 to connect templates to real model queries and service calls.

**How to apply:** When adding new routes, follow the existing blueprint pattern. When adding models, import `db` from `app` and register any new relationships carefully to avoid circular imports.
