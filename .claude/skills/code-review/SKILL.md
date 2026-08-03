---
name: code-review
description: Project-specific code review checklist for cdisc-concept-curation. Use when asked to review changes, a diff, or a PR in this repo.
---

# Code review for cdisc-concept-curation

Review the working diff (`git diff` / `git diff --staged`, or the range the
user names). Verify each finding against the actual code before reporting.
Rank findings by severity; note file:line.

## Project-specific checks (highest value)

1. **Layering** — routes handle HTTP only; business logic belongs in
   `services/`; DB models in `models/`. New SQL/ORM queries embedded in
   templates or scattered helpers are a flag. Models must import `db` from
   `extensions`, never from `app`.
2. **Audit coverage** — every mutation of `BiomedicalConcept`,
   `DataElementConcept`, `GovernanceRecord`, or `IngestionRecord` must write
   an `AuditLog` row (before/after state as dicts). A commit that changes
   data without an audit entry is a defect. (Known historical gap:
   `ncit.resolve`.)
3. **Schema changes** — any change to a model requires an Alembic revision
   in `migrations/versions/` (`flask db migrate`), not just the model edit.
   Watch for edits that rely on `db.create_all()` picking up new columns —
   it does not alter existing tables.
4. **External API clients** (`services/cdisc_api.py`, `ncit_api.py`,
   `loinc_api.py`) — errors are returned as `{"error": ...}` values, and
   callers must check for the `"error"` key before using results. New call
   sites that index into a result without that check will crash on API
   failure. Every caught exception must be logged.
5. **Test isolation** — tests must use `TestConfig` (in-memory SQLite) and
   mock external HTTP (`unittest.mock.patch` / `monkeypatch`). Any test that
   hits a real API or touches `instance/cdisc_curation.db` is a defect.
6. **TDD convention** — behavior changes should come with test changes in
   `tests/`. Flag code changes whose tests were not updated.
7. **Route ordering** — static paths must be registered before parameterized
   ones in the same blueprint (e.g. `/bc/export` before `/bc/<bc_id>`).

## General checks

- Broad `except Exception` where a specific exception fits; silent failure
  paths without logging.
- Secrets: no keys/tokens in code; config comes from `config.py` env vars.
- Duplicated blocks that should be a helper (the repeated
  `AuditLog(...) + add + commit` pattern is the canonical example).
- SQL injection is unlikely via the ORM, but flag any raw `text()`/string
  SQL with interpolated input.
- Jinja templates: user-supplied values must not be marked `|safe`.

## Verification

Run before approving:

```bash
source .venv/bin/activate
pytest --tb=short
pre-commit run --all-files
```
