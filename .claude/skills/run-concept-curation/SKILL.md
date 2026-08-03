---
name: run-concept-curation
description: Run, start, smoke-test, or verify the cdisc-concept-curation Flask server. Use when asked to run the app, confirm a change works in the live server, smoke-test the routes, or check an endpoint manually.
---

# Run the cdisc-concept-curation app

## Quick smoke test (preferred)

```bash
bash .claude/skills/run-concept-curation/smoke.sh
```

Starts the app on **port 9881** against a **throwaway SQLite database** in a
temp directory, runs 14 HTTP checks (dashboard, BC list/create/detail/submit/
delete round-trip, governance board, NCIt pages, audit, ingestion,
specializations, export), prints PASS/FAIL per check, and tears everything
down. Takes ~15s. No API key required — external-API panels degrade
gracefully.

## Manual dev server

```bash
source .venv/bin/activate
export CDISC_API_KEY=your_key    # optional; dashboard/library panels need it
python app.py                    # http://localhost:8081 (PORT env overrides)
```

## Rules

- **Never point ad-hoc runs at `instance/cdisc_curation.db`** (the real
  curation data). For experiments, always set
  `DATABASE_URL=sqlite:////tmp/<something>.db`.
- The dev DB is auto-prepared on startup; tests use in-memory SQLite via
  `tests/conftest.py` and need no server.
- Useful manual checks:
  ```bash
  curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/bc/
  curl -s http://127.0.0.1:8081/bc/export | head -c 400   # JSON export
  ```

## Troubleshooting

- **Port in use**: `lsof -ti :8081 | xargs kill` (or set `PORT`).
- **Dashboard slow without network**: `/` fans out two CDISC Library calls
  with 10s timeouts; offline it renders after the timeout with error panels —
  that is expected, not a failure.
- **`CDISC_API_KEY` unset**: app runs fine; only Library-backed panels and
  `/bc/library/<id>` show errors.
