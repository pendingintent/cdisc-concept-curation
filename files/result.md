# What was built

**All 8 routes return HTTP 200** — run with `.venv/bin/python app.py`

### Structure
```
├── app.py                    # Flask factory
├── extensions.py             # db + migrate (avoids circular imports)
├── config.py                 # CDISC_API_KEY from env
├── requirements.txt
├── models/                   # BiomedicalConcept, DataElementConcept,
│                             #   DatasetSpecialization, GovernanceRecord, AuditLog
├── routes/                   # 7 blueprints (dashboard, ingestion, bc,
│                             #   ncit, specializations, governance, audit)
├── services/                 # cdisc_api, ncit_api, ingestion parser, export
├── templates/                # base.html + 8 screen templates (Bootstrap 5)
└── static/                   # custom.css + main.js
```

### Key capabilities
- **Ingestion**: Upload XLSX/CSV/JSON → fuzzy AI field mapping → review queue → approve to DB
- **BC CRUD**: Full create/edit/delete with all CDISC fields + DEC sub-table
- **NCIT Mapping**: Search NCI Thesaurus, resolve low-confidence mappings
- **Governance Kanban**: 4-stage pipeline (Provisional → SME Review → CDISC Approval → Published) with advance/reject
- **Audit Trail**: Immutable log of every create/update/status change with before/after state
- **Export**: JSON, XLSX, ODM-XML
- **Auth**: `CDISC_API_KEY` env var only — `export CDISC_API_KEY=your_key` before running
