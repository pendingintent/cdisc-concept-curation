# Project Progress

## Overview

CDISC Biomedical Concept Curation — a Flask/Jinja web application for curating, governing, and exporting CDISC Biomedical Concepts (BCs) and Data Element Concepts (DECs). Current phase: **MVP Complete / Initial Build**.

## Feature Status

| Module                     | Status         | Details                                                              |
| -------------------------- | -------------- | -------------------------------------------------------------------- |
| Flask App Foundation       | ✅ Complete    | `app.py`, `extensions.py`, `config.py`                               |
| Database Models            | ✅ Complete    | BC, DEC, Governance, Audit, Ingestion, Specialization                |
| Dashboard                  | ✅ Complete    | KPI stats, live CDISC Library API counts + BC/Spec panels, route `/` |
| Ingestion (Upload + Parse) | ✅ Complete    | XLSX/CSV/JSON upload, AI field mapping, BC/DEC + Specialization grouping |
| BC CRUD + Export           | ✅ Complete    | JSON/XLSX/ODM-XML export                                             |
| NCIt Mapping               | ✅ Complete    | EVS REST API search + mapping resolution                             |
| LOINC API Explorer         | ✅ Complete    | LOINC search + BC metadata integration, `routes/loinc.py`            |
| Dataset Specializations    | ✅ Complete    | Full CRUD, BC selection (local + Library, auto-stub), bulk import via ingestion |
| Governance Workflow        | ✅ Complete    | 4-stage Kanban board, covers both BCs and Dataset Specializations    |
| Notes (Governance Collaboration) | ✅ Complete | Per-BC/per-spec notes: create/edit/resolve/flag, locked at Ready to Publish, never exported, fully audited |
| Audit Trail                | ✅ Complete    | Filterable audit log                                                 |
| CDISC Library API Client   | ✅ Complete    | `services/cdisc_api.py`                                              |
| NCIt EVS API Client        | ✅ Complete    | `services/ncit_api.py`                                               |
| LOINC API Client           | ✅ Complete    | `services/loinc_api.py`                                              |
| Export Service             | ✅ Complete    | XLSX, JSON, ODM-XML                                                  |
| UI (Bootstrap 5)           | ✅ Complete    | Sidebar layout, custom CDISC design tokens                           |
| Pre-commit Hooks           | ✅ Complete    | flake8 + black enforced on commit                                    |
| Test Suite                 | 🚧 In Progress | BC routes, LOINC, NCIt coverage added                                |

## Daily Changelog

### 2026-09-01

#### Added a Notes Feature to Governance (Issue #35)

- Curators had no way to leave collaborative commentary on a BC or Dataset Specialization as it moves through governance — hand-off context (questions, caveats) had to travel outside the tool. Added a per-entity Notes panel at the bottom of the BC and Specialization detail pages, saved independently of the entity's own fields, per [issue #35](https://github.com/pendingintent/cdisc-concept-curation/issues/35).
- `models/note.py` — new `Note` model, scoped to exactly one of a BC or a Specialization via two nullable FKs plus a `ck_notes_one_entity` CHECK constraint, the same polymorphic-association pattern already used by `GovernanceRecord`. Fields: `text`, `flagged`, `resolved`/`resolved_at`/`resolved_by`, `created_by`, timestamps. New Alembic revision `59f58378e692_add_notes_table.py` (tested upgrade + downgrade).
- `services/notes_service.py` — `create_note`/`update_note_text`/`set_resolved`/`set_flagged`/`list_notes_for_entity`, shared by both entity types (mirrors `governance_service`'s `_advance`/`_reject(entity, id_field, ...)` shape). Every mutation is locked once the parent reaches `published` ("Ready to Publish") status — this applies to *all* note actions (create, edit, resolve, flag), not just creation, matching the existing edit-lock added in the prior "Locked Editing" change below. Resolve and Flag are reversible toggles. There is intentionally no `delete_note` — an audit trail is required for every note per the issue, so notes are only ever created, edited, resolved/unresolved, or flagged/unflagged.
- `routes/notes.py` (new blueprint, mounted at `/notes`) — JSON create/update/resolve/flag endpoints; `templates/_notes_panel.html` (new shared partial) renders the list most-recent-first with an inline edit/save toggle and Outlook-style "!" flag badge (CDISC Orange `#D57E00`, per `cdisc-brand-guidelines`), included from both `bc_detail.html` and `specializations.html`. `static/js/main.js` — `initNotesPanel()` follows the existing `initKanban()` fetch-then-reload pattern.
- Notes are deliberately **excluded** from every BC/governance export: `services/export.py`'s field lists (`GOVERNANCE_BC_FIELDS`/`GOVERNANCE_DEC_FIELDS`) and both `to_dict()` methods are explicit allow-lists, so nothing needed to change there — verified no `notes` key/column appears in the governance xlsx, `/bc/export?format=json`, or ODM-XML output. Conversely, every note action **is** captured in the audit trail for free (`log_change("Note", ...)` — the existing `/audit/` CSV/JSON export is generic over `entity_type`); added "Note" and Resolve/Flag options to the `templates/audit.html` filter dropdowns.
- Added 5 MCP tools (`add_note`, `update_note`, `resolve_note`, `flag_note`, `list_notes`) to `mcp_server/server.py` for parity with the rest of the read/write tool surface, following the same `@_with_app_context` + shared-service dispatch pattern as the governance tools.
- Wrote tests first (TDD): `tests/test_notes_service.py` and `tests/test_notes_routes.py` (new, 44 tests) cover create/update/resolve/flag for both entity types, the Ready-to-Publish lock on every action, most-recent-first ordering, and export exclusion; extended `tests/test_models.py` (CHECK constraint), `tests/test_audit_routes.py` (Note actions in CSV/JSON export, Resolve/Flag filters), and `tests/test_mcp_server.py` (all 5 new tools); 446 tests passing, isort/black/flake8 clean ✅
- Verified end-to-end against a live dev server on a throwaway DB/port: created a BC, added/edited/flagged/resolved a note via the JSON endpoints and confirmed the detail page rendered the text, flag indicator, and Resolved badge; advanced the BC to Ready to Publish and confirmed both creating a new note and resolving an existing one were rejected (400) with the read-only banner showing; confirmed the note text was absent from `/governance/export` and `/bc/export?format=json`, and that all four note actions (created/updated/flagged/resolved) appeared in `/audit/?export=json`.

#### Locked Editing and Added Reject at "Ready to Publish" Status

- Governance stages run `provisional → sme_review → cdisc_approval → published`; the `published` stage is labeled "Ready to Publish" on the Governance Kanban board (`templates/governance.html`) but was inconsistently labeled "Published" everywhere else, and nothing in the app treated it as a terminal, locked state — every BC/specialization edit and delete route worked identically regardless of status.
- `services/bc_service.py` — `update_bc()` and `map_ncit_to_bc()` now raise `ValueError` when the BC is already `published`; this guard is inherited automatically by the MCP `update_bc`/`map_ncit_to_bc` tools since they call the same functions.
- `routes/bc.py` — `edit()`, `clear_ncit()`, `clear_loinc()`, and `delete()` now refuse the action (flash + redirect) for a published BC; `routes/ncit.py` `resolve()` catches the new `ValueError`; `routes/specializations.py`'s upsert route (update branch only, not create) and `delete()` refuse the action for a published specialization.
- The Governance board's `published`/"Ready to Publish" Kanban column previously rendered no action buttons at all, so there was no way to reject an item once it reached that column even though `reject_bc`/`reject_specialization` already worked unconditionally from any status — added a Reject button there for both BCs and specs, reusing the existing `kanban-reject-btn` JS wiring and routes.
- `templates/bc_detail.html` and `templates/specializations.html` now show a locked notice and wrap their editable fields in a disabled `<fieldset>` when `published`; `templates/bc_list.html` and `templates/specializations.html` disable the row Delete button for published items; relabeled `published` as "Ready to Publish" consistently across `bc_detail.html`, `bc_list.html`, and `specializations.html` to match the Kanban board.
- Wrote tests first (TDD) covering every new guard across `tests/test_bc_routes.py`, `tests/test_specializations_routes.py`, `tests/test_ncit.py`, `tests/test_governance_routes.py`, and `tests/test_mcp_server.py`; manually verified end-to-end against a running server (create → advance through all 4 stages → edit/delete blocked → reject via the new board button → edit/delete work again) for both a BC and a specialization; 383 tests passing, isort/black/flake8 clean ✅

#### Fixed Export CSV/JSON Buttons on the Audit Trail Page

- The "Export CSV" and "Export JSON" buttons on `/audit/` appended `?export=csv`/`?export=json` to the URL, but `routes/audit.py`'s `index()` never read that parameter — it just re-rendered the same filtered HTML page, so clicking either button silently did nothing.
- `routes/audit.py` — extracted the existing filter-building logic into `_filtered_query()`; `index()` now checks `request.args.get("export")` and, when set to `csv` or `json`, returns the full filtered (unpaginated) result set as a download via Flask `Response` (`text/csv` / `application/json`, `Content-Disposition: attachment; filename=audit_log.{csv,json}`), matching the existing export pattern in `routes/bc.py`. Added `_log_to_dict()` and `_export_csv()`/`_export_json()` helpers; `before_state`/`after_state` are JSON-serialized in the CSV and left as nested objects in the JSON export.
- Wrote tests first (TDD): `TestAuditExportCSV` and `TestAuditExportJSON` in `tests/test_audit_routes.py` cover attachment headers/mimetypes, row/record content, filter pass-through (`entity_type`, `actor`), and exporting past the 50-row pagination limit (60 rows in, 60 rows out); 368 tests passing, isort/black/flake8 clean ✅

#### Made the ncit_dec_code Export Column Mirror dec_id

- In the exported `BC_LB`/`BC_VS` xlsx sheet, column M (`dec_id`) was populated correctly but column N (`ncit_dec_code`) was left at whatever was stored on the DEC (typically blank, since the BC detail form no longer exposes it as a separate field — see the DEC ID entry below). Made the export always populate column N with the same value as column M.
- `services/export.py` — `export_governance_xlsx()`'s per-DEC row loop now special-cases the `ncit_dec_code` header to use `dec.dec_id` instead of the DEC's stored `ncit_dec_code` attribute. This is an export-time transformation only (nothing is rewritten in the database), applied uniformly since both `/bc/export?format=xlsx` and `/governance/export` share this function.
- Wrote the test first (TDD): `TestExportGovernanceXlsx.test_ncit_dec_code_column_mirrors_dec_id` and `test_ncit_dec_code_column_overrides_a_stored_distinct_value` in `tests/test_export_service.py` confirm column N always equals column M, even when a DEC has a different stored `ncit_dec_code`; 361 tests passing, isort/black/flake8 clean ✅
- Verified against a live dev server on a throwaway DB/port: created a BC with a DEC (`dec_id=C64849.DEC.1`), downloaded `/bc/export?format=xlsx`, and confirmed columns M and N both read `C64849.DEC.1` on the DEC row (both blank on the BC-only row, as expected).

#### Added a Visible, Editable DEC ID Field to the BC Detail Form

- The DEC table's `dec_id` value (the column that populates `dec_id` in `files/BC Examples.xlsx`) was a hidden input, silently auto-generated as `{bc_id}.DEC.{n}` if left blank — curators had no way to see or set it directly, e.g. to match a CDISC-published DEC id like `C64849.DEC.1`. Made it a visible text column, positioned before "DEC Label" as requested.
- `templates/bc_detail.html` — added a `DEC ID` `<th>` before `DEC Label`; the per-row `dec_id` input changed from `type="hidden"` to a visible `form-control form-control-sm` text input (matching the styling of the other DEC fields), still positioned first in the row. `ncit_dec_code` remains a hidden input (not part of this request).
- `static/js/main.js` — `buildDecRow()` updated to match: new rows get the same visible DEC ID cell ahead of DEC Label.
- No backend changes needed — `routes/bc.py`'s `_decs_from_form()` and `services/bc_service.save_decs()` already read/persist `dec_id` (from the earlier DEC-save-bug fix) and still auto-generate one when the field is left blank, so this is purely a UI change plus a regression test.
- Wrote the test first (TDD): `TestBcDetail.test_dec_id_field_is_visible_and_precedes_label` in `tests/test_bc_routes.py` asserts the "DEC ID" header precedes "DEC Label" and that the input is a visible `type="text"` field carrying the DEC's value; 359 tests passing, isort/black/flake8 clean ✅
- Verified end-to-end against a live dev server on a throwaway DB/port: created a BC with an explicit custom `dec_id` (`C64849.DEC.1`) via the form, confirmed it rendered in the new visible field, and confirmed it flowed through unchanged into the `dec_id` column of the `/bc/export?format=xlsx` output.

#### Fixed DECs Disappearing on Save; Included DECs in All BC Exports

- Adding DECs to a BC on the detail form and clicking Save silently deleted them: the rendered table and `static/js/main.js` submit DEC fields as `decs[N][dec_label]` etc., but `routes/bc.py`'s `_decs_from_form()` was still reading obsolete flat-array names (`dec_label[]`) that the form never sent, so it always parsed zero DECs and `save_decs()`'s delete-then-recreate logic wiped every existing DEC and added nothing back — on both create and edit.
- `routes/bc.py` — rewrote `_decs_from_form()` to parse the actual `decs[N][field]` keys via regex, grouped and ordered by row index.
- `templates/bc_detail.html` / `static/js/main.js` — added hidden `decs[N][dec_id]`/`decs[N][ncit_dec_code]` inputs (previously never emitted at all) so editing an existing DEC preserves its identity/NCIt code instead of `save_decs` regenerating a new `dec_id` on every save.
- `services/bc_service.py` — `save_decs()` now also persists the `required` checkbox onto `DataElementConcept.required`, which the form submitted but the service silently discarded.
- Separately, DECs weren't reaching any BC export either: `/bc/export?format=xlsx` used an old exporter (`export_xlsx`/`BC_EXPORT_FIELDS`) with no DEC columns/rows at all and the wrong sheet name, while a newer exporter (`export_governance_xlsx`) already matched the reference `files/BC Examples.xlsx` `BC_LB` shape (BC row + one row per DEC, BC columns repeated) but was wired only to the published-only `/governance/export` route. Pointed `/bc/export`'s xlsx branch at `export_governance_xlsx` instead and removed the now-dead `export_xlsx`/`BC_EXPORT_FIELDS`.
- `models/bc.py` — `BiomedicalConcept.to_dict()` now includes a `decs` list (skipped gracefully for a transient, not-yet-session-bound BC), so JSON export carries DEC data too.
- `services/export.py` — `export_odm_xml()` now emits a DEC-derived `ItemDef` per DEC (data-type mapped to ODM's, NCIt alias when present).
- Wrote tests first (TDD): fixed `TestCreateBc.test_create_with_decs` (previously posted a fictitious flat-array shape the browser never sends), added DEC coverage to `TestEditBc` (unchanged/updated/added/removed rows, `required` persistence), a new `TestSaveDecs` unit-test class in `tests/test_bc_service.py` (previously zero coverage), strengthened `TestExport` in `tests/test_bc_routes.py` and `TestExportOdmXml`/removed the now-dead `TestExportXlsx` in `tests/test_export_service.py`, and added `to_dict()` DEC tests to `tests/test_models.py`; 358 tests passing, isort/black/flake8 clean ✅
- Verified end-to-end against a live dev server on a throwaway DB/port: created a BC with 2 DECs via the real `decs[N][field]` form shape and confirmed both rendered; edited it (updated one DEC, dropped one, added one) in a single save and confirmed the detail page reflected exactly that; confirmed `/bc/export` in JSON, XLSX (`BC_LB` sheet, correct row/column shape), and ODM-XML all carry the DEC data.

#### Reordered the Definition Section on the BC Detail Form

- `templates/bc_detail.html` — moved the "Definition" `bc-card` block (textarea for `definition`) to appear right after the top summary section, ahead of the NCIt/LOINC panels; it previously sat lower on the page, after the LOINC results container. Template-only reorder, no field/logic changes.

#### Added a DEC-Scoped NCIt Card for Populating New DEC Rows

- The DEC table's `ncit_dec_code` column has existed in the model/DB and round-tripped through save/export since the DEC-save-bug fix, but nothing in the UI ever set it — curators had to type DEC ID and DEC Label by hand for every new DEC, even when a matching NCIt concept existed. Added a second "NCIt" card, scoped to DEC creation, mirroring the existing BC-level NCIt search card (same search/results/metadata-panel layout and CSS classes) but positioned in the right column directly under the "Data Element Concepts (DECs)" card.
- `templates/bc_detail.html` — new card with `#dec_ncit_code` search input + `#dec-ncit-lookup-btn`, `#dec-ncit-results-panel`/`#dec-ncit-results-container`, and `#dec-ncit-meta-display`; omits the BC-level card's "Parent BC ID" field and "Clear" button since neither applies to DEC search. The search input intentionally has no `name` attribute — it's a scratch field, not a submitted form value.
- `static/js/main.js` — refactored `initDecTable()`'s row-creation logic into `addDecRow()`, which also tracks the new row as `activeDecRow` (module-level state). Added `initDecNcitLookup()` / `renderDecNcitResults()` / `renderDecNcitMetaDisplay()`, mirroring the BC-level `initNcitLookup()` / `renderNcitResults()` / `renderNcitMetaDisplay()` against the same `/ncit/search` and `/ncit/concept/<code>` endpoints. Selecting a result sets `activeDecRow`'s `dec_id` (from the NCIt code), `dec_label` (from the preferred name), and hidden `ncit_dec_code` inputs directly; if no row is currently tracked (or it was deleted), a new one is created automatically so the card also works when searched before "Add DEC" is clicked. Existing/already-saved DEC rows are never touched by a card selection — only the most recently added row is ever a target, and deleting that row clears the tracked reference.
- No backend/model/route changes — reuses `routes/ncit.py`'s existing `/ncit/search` and `/ncit/concept/<code>` endpoints and the existing `ncit_dec_code` hidden input/column as-is.
- 361 tests passing (unchanged — no backend logic touched), isort/black/flake8 clean ✅
- Verified against a live dev server on a throwaway DB/port using a scripted Playwright session (the real NCI EVS API is unreachable from this sandbox, so the two NCIt endpoints were mocked client-side to exercise the DOM logic): clicked Add DEC, searched and selected a mocked concept, confirmed the new row's DEC ID/DEC Label/hidden NCIt code populated correctly and the metadata panel rendered, then saved and reloaded to confirm the DEC persisted with the expected values.
- Follow-up same day: with two "NCIt" cards now on the page, relabeled the headers so each is unambiguous — `templates/bc_detail.html` now reads "NCIt for Biomedical Concept" (BC-level card) and "NCIt for DEC" (the new DEC-scoped card). Header text only, no functional change.

### 2026-08-31

#### Constrained Result Scales to a Fixed Checklist on the BC Create/Edit Form

- The BC create/edit form previously took `result_scales` as free text (`e.g. Quantitative`), so nothing stopped a curator from typing an arbitrary value. Replaced it with a checkbox group for the 5 allowed values (`Narrative, Nominal, Ordinal, Quantitative, Temporal`, alphabetically sorted), and made spreadsheet ingestion flag any value outside that list instead of silently accepting it.
- `models/bc.py` — new `RESULT_SCALES` tuple (the 5 allowed values) and `split_result_scales()` helper to parse the semicolon-separated string stored on the model.
- `templates/bc_detail.html` — `result_scales` is now 5 checkboxes instead of a text input; any existing value not in `RESULT_SCALES` (e.g. a legacy/imported value like "Continuous") is rendered separately below in red with a "Not supported" label, and preserved via hidden inputs on save rather than silently dropped.
- `routes/bc.py` — `create()`/`edit()` join the checked checkbox values back into the semicolon-separated string `bc_service` expects. `edit()` uses a hidden `result_scales_submitted` marker to distinguish "all checkboxes unchecked" (clear the field) from "this field wasn't part of the request" (preserve the existing value) — plain HTML checkboxes submit nothing at all when unchecked, so without the marker those two cases are indistinguishable.
- `services/ingestion.py` — `validate_bc()` now flags any spreadsheet-imported `result_scales` value outside `RESULT_SCALES` as a validation error, surfaced through the existing red error badge on the `/ingestion` review screen (no new UI needed there).
- Wrote tests first (TDD): extended `tests/test_models.py` (`RESULT_SCALES`/`split_result_scales`), `tests/test_ingestion_service.py` (unsupported/mixed scale validation), and `tests/test_bc_routes.py` (checkbox round-trip, unsupported-value preservation and red display); 337 tests passing, isort/black/flake8 clean ✅
- Not yet verified in a live browser session — implementation and full test suite only.

#### Extended the Governance Workflow to Dataset Specializations

- Dataset Specializations previously had no governance lifecycle at all — no `status` field, no `GovernanceRecord` linkage, no Kanban presence — while BCs had the full 4-stage `provisional → sme_review → cdisc_approval → published` workflow. Brought specializations to parity so they're tracked, advanced, and rejected the same way.
- New Alembic migration `df33730cf8d2` — `dataset_specializations` gains `status` (default `provisional`) and `updated_at`; `governance_records.bc_id` is now nullable and a new `vlm_group_id` FK (→ `dataset_specializations.vlm_group_id`) was added, with a check constraint (`ck_governance_records_one_entity`) enforcing exactly one of `bc_id`/`vlm_group_id` is set on every row. Hit and fixed an Alembic SQLite batch-mode gotcha along the way (`create_foreign_key(None, ...)` fails with "Constraint must have a name" during a table rebuild — needs an explicit name).
- `services/governance_service.py` — refactored `advance_governance`/`reject_bc` into shared `_advance()`/`_reject()` helpers generic over either entity type (both `BiomedicalConcept` and `DatasetSpecialization` expose `.status`/`.short_name`/`.updated_at`), then added `advance_specialization_governance()`/`reject_specialization()` on top; existing BC function signatures/return shapes unchanged.
- `routes/governance.py` — new `POST /governance/spec/advance/<vlm_group_id>` and `POST /governance/spec/reject/<vlm_group_id>`; `board()` now also queries specializations by stage; `export()` now pulls published specializations too.
- `templates/governance.html` — added a "Biomedical Concepts" / "Dataset Specializations" Bootstrap nav-tab toggle, each with its own 4-column Kanban board; reused the existing status-based CSS classes (`bc-badge-*`, `kanban-header-*`) since they were already generic rather than BC-specific, so no new CSS was needed. `templates/specializations.html` — added a Status badge column to the specializations list.
- `static/js/main.js` — generalized the Kanban advance/reject click handlers to branch on `data-vlm-group-id` vs `data-bc-id` and POST to the matching endpoint, additive to the existing BC button markup.
- `mcp_server/server.py` — added `advance_specialization_governance`/`reject_specialization` tools (parity with `advance_governance`/`reject_bc`); `list_review_queue` now includes a `specializations` key; `get_bc`'s specialization dicts now include `status`.
- `services/export.py` — `export_governance_xlsx()` gained an optional `spec_objects` param that adds specialization worksheet(s) when given; backward compatible (defaults to `None`). (Sheet shape corrected below same day — see "Made the Governance Export Round-Trip Through the Ingestion Importer".)
- Extended `tests/test_governance_routes.py` (new `TestSpecAdvance`/`TestSpecReject`/`TestGovernanceRecordOneEntityConstraint` classes), `tests/test_mcp_server.py`, `tests/test_specializations_routes.py`, and added a `sample_spec` fixture to `tests/conftest.py`; 312 tests passing, isort/black/flake8 clean ✅
- Verified end-to-end against the live dev server: created a specialization, advanced it through all 4 stages and rejected it via the new routes, confirmed the `ck_governance_records_one_entity` constraint actually rejects both-null/both-set rows, and confirmed the governance XLSX export contains both worksheets.

#### Fixed the Governance Board Kanban Tab Resetting on Every Advance/Reject

- Reported bug: clicking Advance/Reject while on the "Dataset Specializations" tab bounced the user back to the "Biomedical Concepts" tab. Cause: the click handlers call `location.reload()` on success, and a fresh page load always renders the first Bootstrap tab as active — nothing remembered which tab had been selected.
- `static/js/main.js` — added `initGovernanceTabs()`: on `shown.bs.tab`, the active tab's `data-bs-target` is written into the URL hash via `history.replaceState` (no extra navigation); on page load, a matching hash reactivates that tab via Bootstrap's Tab API before anything else runs. Since `location.reload()` reloads the same URL (hash included), the tab now survives the reload.
- No Python changes; verified the rendered `data-bs-target`/hash wiring matches and the file passes `node --check`. Not click-tested in an actual browser this session (Chrome extension not installed) — asked the user to confirm.

#### Made the Governance Export Round-Trip Through the Ingestion Importer

- Reported bug: the Dataset Specializations sheet added to the governance XLSX export didn't match what `/ingestion/upload` expects, so an exported file couldn't be re-imported. The first cut had written a single summary sheet named "Dataset Specializations" with 7 rollup columns (`vlm_group_id, bc_id, bc_short_name, domain, short_name, status, variable_count`) — nothing like the real per-domain, per-variable worksheet shape `services/ingestion.py` parses.
- Inspected the real reference workbook (`files/BC Examples.xlsx`) to confirm the actual expected shape: one worksheet per domain named `SDTM_<domain>` (e.g. `SDTM_LB`, `SDTM_VS` — the `SDTM_`/`CDASH_` sheet-name prefix is what `_detect_record_type()` keys off), header row = `vlm_group_id, bc_id, domain, short_name, package_date` followed by all 24 `VARIABLE_FIELDS` in their exact snake_case worksheet-column form, one row per SDTM VLM variable with the spec-level fields repeated on every row (same repeat-per-child-row pattern the `BC_LB` sheet already uses for DECs).
- Promoted `services/ingestion._SPEC_HEADER_FIELDS` to a public `SPEC_HEADER_FIELDS` (now needed by `services/export.py` too) and rewrote `export_governance_xlsx()`'s specialization branch to group `spec_objects` by `domain`, create one `SDTM_<domain>` sheet per group, and emit rows in the importer's exact shape (a specialization with zero variables still emits one header-only row so it round-trips instead of silently disappearing).
- Added `TestExportGovernanceXlsxSpecializations` to `tests/test_export_service.py`, including a round-trip test that feeds the exported `BytesIO` straight into `services.ingestion.parse_xlsx()` and asserts the resulting record matches the original; 318 tests passing, isort/black/flake8 clean ✅
- Verified against the live dev server with the real HTTP path end-to-end: created a specialization with a variable via the UI, advanced it to published, downloaded `/governance/export`, and re-uploaded that exact file through `/ingestion/upload` — it parsed back out as a `Dataset Specialization` ingestion record with the same `vlm_group_id`/`bc_id`/`domain`/variables.
- **Follow-up same day**: the header row above was importer-parseable but not byte-for-byte identical to the reference file — column order was wrong (`vlm_group_id, bc_id, domain, short_name, package_date, ...`) and it was missing 3 real columns the reference sheet has (`sdtmig_start_version`, `sdtmig_end_version`, `vlm_source`) that the model doesn't track but the importer still expects to see as headers. Read `files/BC Examples.xlsx`'s `SDTM_LB`/`SDTM_VS` sheets directly to get the exact column order, added `services/export.py:SPEC_SHEET_HEADER_FIELDS` matching it exactly (the 3 untracked columns are exported blank rather than omitted), and switched the test to assert the literal reference header list instead of deriving it from the same constant the implementation uses. Verified with a direct `openpyxl` diff between the reference file's header row and a live export's — exact match.

### 2026-08-28

#### Added Dataset Specialization Import + Fixed the BC-Picker Orphan-FK Gap

- The Specializations page was blank because there was no bulk-import path into `dataset_specializations` — only one-at-a-time manual entry or "Generate from DEC Templates" existed. Taught the existing `/ingestion` upload+review pipeline (previously BC-only) to also recognize and import SDTM Dataset Specialization rows from the same curation workbooks (e.g. `files/BC Examples.xlsx`, whose `SDTM_LB`/`SDTM_VS` sheets are specializations joined to a BC via `bc_id`)
- `services/ingestion.py` — added `SPEC_FIELD_MAP`, `_detect_record_type()` (sheet-name prefix `BC_`/`SDTM_`/`CDASH_` first, falls back to a `vlm_group_id` column signature), `validate_specialization()`, `_group_by_spec()` (groups VLM variable rows by `vlm_group_id`, mirroring `_group_by_bc`'s DEC grouping); parameterized `map_fields()`/`_match_field()` to accept a field map; `parse_xlsx/csv/json` and `deduplicate()` now branch by record type
- `models/ingestion.py` — added `record_type` column (`"bc"` / `"specialization"`, new migration `95643d73ac0e`); `models/specialization.py` — `created_at` now actually defaults instead of always being `NULL`
- `routes/ingestion.py` — `approve()`/`approve_all()` now create `DatasetSpecialization` rows too; `approve_all()` resolves all BC-type records first (flushed) before specialization-type ones, so a single workbook mixing `BC_`/`SDTM_` sheets imports correctly in one click; a specialization whose BC doesn't exist yet is left `pending` with a flash error instead of orphaning or crashing
- `routes/specializations.py` — `create()` now auto-creates a minimal local BC stub (new `services/bc_service.get_or_create_bc_stub()`) when a user picks a CDISC-Library-only BC on the manual Specialization form, fixing a real gap: SQLite FK enforcement is off, so that path previously created specializations with no matching local BC row; also sorted the Library `<optgroup>` alphabetically (it was the only unsorted one)
- `templates/ingestion.html` — split the review queue into separate "Biomedical Concepts" / "Dataset Specializations" sections; `templates/specializations.html` — fixed two dead-attribute bugs (`spec.bc_name`, `spec.variable_count` don't exist on the model) that were silently showing raw `bc_id` and "0 variables" for every row
- Caught via manual smoke test (not just unit tests): the worksheet's `domain` column holds the real SDTM domain codelist value (`LB`, `VS`, ...), not an `SDTM`/`CDASH` toggle — an early version of this change incorrectly forced a literal `"SDTM"` constant; corrected to map the real column value through
- Added `tests/test_bc_service.py` and extended `tests/test_ingestion_service.py`, `tests/test_ingestion_routes.py`, `tests/test_specializations_routes.py` — 280 tests passing, isort/black/flake8 clean ✅
- Verified end-to-end against the real `files/BC Examples.xlsx`: 25 BCs + 23 specializations parsed, 25 BCs + 22 specializations approved (1 correctly held pending — its BC wasn't in that workbook's BC sheets)

#### Replaced the Manual Specialization Form's SDTM/CDASH Toggle with a Real SDTM Domain Codelist Dropdown

- The manual "Add Specialization" form previously let `domain` be either the literal string `SDTM` or `CDASH` via a radio toggle — meaningless once the ingestion import above started populating `domain` with real SDTM domain codes (`LB`, `VS`, ...). Replaced the toggle with a `<select>` populated live from the CDISC Library's own SDTM Domain Abbreviation codelist (C66734), so only real, current domain codes can be chosen
- `services/cdisc_api.py` — added `get_ct_packages()` (lists all CT packages from the Library's general MDR API at `LIBRARY_BASE_URL = "https://library.cdisc.org/api"`, a different host/path than the COSMoS-specific base this client otherwise uses) and `get_sdtm_domain_codes()` (picks the most recent `sdtmct-*` package by date-sorted href, fetches codelist `C66734`, returns `[{code, label}]` from each term's `submissionValue`/`preferredTerm`, cached like the existing BC/specialization list calls); verified the exact response shape against the live API before writing code against it
- `routes/specializations.py` — `index()`/`detail()` now pass `domain_codes` into the template; `create()`/`generate()` now require a non-blank `domain` (previously silently defaulted to `"SDTM"`)
- `templates/specializations.html` — domain `<select>` shows `"CODE — Preferred Term"` options, with a fallback option so editing an existing spec whose domain code has since been retired/superseded doesn't silently blank the field; dropped the SDTM-vs-CDASH conditional badge coloring in the list view (domain is now an open codelist, not a two-value toggle); updated the "Generate from DEC Templates" JS to read the select instead of a checked radio
- `models/specialization.py` — corrected the stale `# SDTM or CDASH` comment on `domain`
- Extended `tests/test_cdisc_api_cache.py` (new package/codelist fetch tests, mocked at the `requests.get` level per this file's existing convention) and `tests/test_specializations_routes.py` (domain required, real domain code persists, dropdown rendered from the mocked codelist); 290 tests passing, isort/black/flake8 clean ✅
- Verified live against the real CDISC Library API (real API key already in this shell's env) that the dropdown renders all 85 real SDTM domain codes from the current package (e.g. `AE — Adverse Event Domain`, `VS — Vital Signs Domain`)

#### Fixed the Edit Button + Rebuilt Variable Import Against Real Worksheet Columns (not a synthesized name/label/data_type/required shape)

- **Edit button did nothing**: `specializations.detail()` renders the same template with `edit_spec` populated, but the pre-filled form lives in a Bootstrap `collapse` div that was never told to expand — the page loaded correctly but the form stayed hidden. `templates/specializations.html` now adds the `show` class whenever `edit_spec` is set.
- **Variables were imported wrong**: for specialization `KETONESURIN`, the worksheet has 11 rows (`sdtm_variable` column), but only 8 garbled entries were showing (e.g. `KETONES`, `URINALYSIS`, `mmol/L` instead of `LBTESTCD`, `LBORRES`, ...). Root cause: `SPEC_FIELD_MAP` only had ~8 curated canonical fields, so the ~20 other real VLM columns (`dec_id`, `codelist`, `assigned_value`, `subject`, `object`, `predicate_term`, ...) fuzzy-matched onto those few fields with score > 0.5 and silently overwrote them within the same row — `assigned_value` was literally clobbering `sdtm_variable` itself.
- Fixed by mapping **every real worksheet column (I-AF, 24 variable-level fields) 1:1 to itself** instead of a small curated+fuzzy list — `services/ingestion.py` now has `VARIABLE_FIELD_DEFS`/`VARIABLE_FIELDS` (the full column list: `sdtm_variable`, `dec_id`, `nsv_flag`, `codelist`, `codelist_submission_value`, `subset_codelist`, `value_list`, `assigned_term`, `assigned_value`, `role`, `subject`, `linking_phrase`, `predicate_term`, `object`, `data_type`, `length`, `format`, `significant_digits`, `mandatory_variable`, `mandatory_value`, `origin_type`, `origin_source`, `comparator`, `vlm_target`), each scoring 1.0 against itself so same-row collisions between similarly-named columns (e.g. `mandatory_variable` vs `mandatory_value`) are now structurally impossible; `_group_by_spec()` builds one full-width dict per variable row instead of the old synthesized `{name, label, data_type, required}` shape
- Dropped the fabricated `label`/`required` fields (not real worksheet columns) per explicit instruction — the UI's variable table now shows/edits exactly the worksheet's I-AF columns, driven from a single `variable_field_defs` list shared between `routes/specializations.py` and the template (header row, form field names, and the JS that builds new/generated rows all read from it, so there's one source of truth instead of three copies)
- `routes/specializations.py` — `_variables_from_form()` rewritten to parse all `VARIABLE_FIELDS` per row (gated on `sdtm_variable` being non-blank); `_variable_from_dec()` seeds `sdtm_variable`/`dec_id`/`data_type` from a BC's DataElementConcept for the "Generate from DEC Templates" flow, leaving the columns a DEC can't supply blank for the user to fill in
- Updated `tests/test_ingestion_service.py`, `tests/test_specializations_routes.py` for the new shape; 293 tests passing, flake8 clean ✅
- Verified end-to-end against the real workbook: `KETONESURIN` now shows exactly 11 variable rows with correct values in the right order (`LBTESTCD`, `LBTEST`, `LBCAT`, `LBORRES`, `LBORRESU`, `LBSTRESC`, `LBSTRESN`, `LBSTRESU`, `LBLOINC`, `LBSPEC`, `LBFAST`), and the Edit link now opens the form expanded

### 2026-08-03

#### Fixed New Copilot Comment on PR #39 — "Code" Column Still Blank in `export_xlsx()`

- Fixed `services/export.py` `export_xlsx()` — the generic per-field loop still read `bc.get(field, "")` for every column, so the "Code" column stayed blank; now special-cases `field == "code"` to source the value from `bc.get("loinc_code", "")`, matching the pattern already used in `export_governance_xlsx()`
- Added `tests/test_export_service.py::TestExportXlsx::test_code_column_uses_loinc_code` as a regression test
- All 246 tests passing, lint clean ✅
- Resolves the last (11th) open Copilot comment on PR #39

#### Closed Out Workstream B.1 — Module-Level Loggers

- Added `import logging` + `logger = logging.getLogger(__name__)` to the 11 route/service files that lacked one: `routes/audit.py`, `routes/dashboard.py`, `routes/governance.py`, `routes/ingestion.py`, `routes/loinc.py`, `routes/ncit.py`, `routes/specializations.py`, `services/audit.py`, `services/bc_service.py`, `services/export.py`, `services/governance_service.py`
- `app.py` and the three API clients (`cdisc_api.py`, `ncit_api.py`, `loinc_api.py`) already had loggers; this closes the remaining gap from PR #39's Workstream B.1 audit
- All 245 tests passing, isort/black/flake8 clean ✅

#### Fixed Broken Governance Export Fix-Up Commits from PR #39

- Fixed `services/bc_service.py` `save_decs()` — removed a stray duplicate `for` loop line (`IndentationError: expected an indented block`) left over from an automated PR-review fix commit
- Fixed `services/export.py` `export_governance_xlsx()` — restored the missing inner `for col_idx, header in enumerate(GOVERNANCE_HEADERS, start=1):` loop (`IndentationError: unindent does not match any outer indentation level`) dropped by the same commit
- Both files failed to even compile after `git pull origin release-v0.3` pulled in 5 "Potential fix for pull request finding" commits responding to PR #39 review comments; the other 3 (`.mcp.json`, `routes/governance.py`, `tests/test_ncit.py`) were fine
- All 239 tests passing after the fix
- Removed unused `GovernanceRecord` import from `routes/governance.py` that failed CI's flake8 F401 check on PR #39

#### Fixed BC ID Promotion Orphaning Dependent Rows

- Fixed `services/bc_service.py` `map_ncit_to_bc()` — promoting an `IMPORT_` id to a resolved NCIt code now bulk-updates `DataElementConcept.bc_id`, `DatasetSpecialization.bc_id`, `GovernanceRecord.bc_id`, and `BiomedicalConcept.parent_bc_id` to the new id instead of leaving them pointed at the old, now-nonexistent `bc_id`
- Added a check that raises `ValueError(f"BC {ncit_code} already exists")` when the target `ncit_code` collides with an existing BC's `bc_id`, instead of surfacing a raw `IntegrityError`
- Added 3 tests to `tests/test_mcp_server.py::TestMapNcit` covering dependent-row re-pointing, child-BC `parent_bc_id` re-pointing, and the collision case
- All 242 tests passing, isort/black/flake8 clean ✅

#### Resolved Remaining Copilot Review Comments on PR #39

- Relabeled the "NCI Thesaurus HREF" field in `templates/library_bc_detail.html` to "CDISC Library HREF" — `bc.href` is the CDISC Library API's own self-link, not an NCIt URL
- Fixed `routes/specializations.py` `create()` — POSTing an existing `vlm_group_id` (the "Edit Specialization" flow) now updates the existing row and logs an `"updated"` audit action instead of attempting a duplicate INSERT and raising an `IntegrityError`/500
- Added `_variables_from_form()` to `routes/specializations.py` to parse the `variables[i][name/label/data_type/required]` form rows, which `create()` previously discarded entirely (always saved `variables = []`)
- Added 3 tests to `tests/test_specializations_routes.py` (`TestCreate.test_create_persists_variable_rows_from_form`, `TestEditUpsert.test_posting_existing_vlm_group_id_updates_instead_of_duplicating`, `TestEditUpsert.test_edit_writes_updated_audit_log`)
- All 245 tests passing, isort/black/flake8 clean ✅

### 2026-04-15

#### Audit Trail Coverage Completion + Specialization Delete Route

- Fixed `templates/specializations.html:221` — Delete form now POSTs to proper `specializations.delete` route keyed on `vlm_group_id` (removed broken `action=delete`/`spec.id` inputs)
- Added `models/specialization.py` — `to_dict()` method for clean audit log serialization
- Added `POST /<vlm_group_id>/delete` route to `routes/specializations.py` — fully audited delete operation
- Updated `routes/specializations.py` — `log_change()` calls on create/generate/delete operations (actor="user")
- Updated `routes/ingestion.py` — `approve_all()` now writes one `AuditLog` per created BiomedicalConcept (action="created_via_ingestion", actor="system")
- Added comprehensive test coverage: 5 new tests in `tests/test_specializations_routes.py` and `tests/test_ingestion_routes.py` (audit logging for create/delete/generate, 404 handling, etc.)
- All 239 tests passing, isort/black/flake8 clean ✅

### 2026-04-14

#### LOINC API Explorer + BC Detail Performance + Specializations + Config

- Added `routes/loinc.py` blueprint — LOINC concept search integrated into the app
- Added `services/loinc_api.py` — LOINC REST API client
- Added DB migrations for NCIt and LOINC metadata fields on `BiomedicalConcept` (`models/bc.py`)
- Extended `routes/bc.py` with LOINC/NCIt metadata display and BC detail improvements
- Performance improvements to BC detail page — optimized `routes/bc.py` and `routes/dashboard.py` queries, reduced redundant API calls
- Enhanced `templates/bc_detail.html` with NCIt and LOINC metadata panels and improved layout
- Fixed BC deletion — added delete route to `routes/bc.py` and updated `templates/bc_list.html` with confirmation UI
- Added BC selection to specializations — `routes/specializations.py` updated with BC association logic
- Fixed specialization search in `routes/specializations.py` and `services/cdisc_api.py`
- Added pagination to dashboard (`templates/dashboard.html` redesigned, `routes/dashboard.py` updated)
- HTTP listening port now configurable via `config.py` env var (updated `app.py`)
- Added `tests/test_bc_routes.py`, `tests/test_loinc.py`, `tests/test_ncit.py` — initial test coverage
- Configured pre-commit hooks with flake8 and black enforcement
- Updated `templates/library_bc_detail.html` and `static/js/main.js` with LOINC/NCIt explorer UX

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
