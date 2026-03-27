---
name: Frontend Architecture
description: Template hierarchy, CSS design system, JS module structure, and naming conventions for the CDISC BC Curation front-end
type: project
---

All templates extend `templates/base.html` using `{% extends "base.html" %}`.

**Block definitions in base.html:**
- `title` — HTML page title
- `page_title` — shown in the topbar
- `user_info` — user display (topbar right)
- `content` — main page body
- `extra_js` — page-specific JS at bottom of body

**Sidebar nav pattern:** Each `<a class="nav-item">` uses `request.endpoint.startswith('<blueprint>.')` for active state detection.

**CSS class naming conventions (custom.css):**
- Layout: `.app-layout`, `.sidebar`, `.main-area`, `.topbar`, `.content-area`
- Cards: `.bc-card`, `.bc-card-sm`, `.bc-card-header`, `.bc-card-title`
- Badges: `.bc-badge` + modifier — `bc-badge-provisional`, `bc-badge-sme-review`, `bc-badge-cdisc-approval`, `bc-badge-published`, `bc-badge-conflict`, `bc-badge-rejected`, `bc-badge-new`
- Confidence badges: `.confidence-badge` + `confidence-high` (>=80%), `confidence-mid` (60-79%), `confidence-low` (<60%)
- Metric cards: `.metric-card` + `metric-card-blue/green/amber/purple`; `.metric-val` + `metric-val-blue/green/amber/purple`
- Tables: `.bc-table` (standard), `.dec-table` (compact DEC variant)
- Kanban: `.kanban-grid`, `.kanban-column`, `.kanban-column-header` + `kanban-header-provisional/sme-review/cdisc-approval/published`, `.kanban-card`, `.kanban-card-title`, `.kanban-card-meta`
- Upload: `.upload-zone` (drag-over state toggled by JS adding `.drag-over`)
- Info boxes: `.info-box` + `info-amber/blue/green/red`
- Two-col layout: `.two-col-grid` (CSS grid 1fr 1fr)

**CSS design tokens (matches mockup exactly):**
- Sidebar bg: `var(--bg-secondary)` (#f7f6f2) — NOT dark; sidebar uses light warm-gray
- Active nav link: `var(--blue600)` bg tint `var(--blue50)`, left border `var(--blue600)`
- Primary action color: `var(--blue600)` (#185FA5)

**JavaScript modules (static/js/main.js — IIFE, no globals):**
- `initFlashDismiss()` — auto-close Bootstrap alerts after 5s
- `initFileUpload()` — drag-drop + file input for `#upload-zone` / `#file-input`
- `initNcitLookup()` — `#ncit-lookup-btn` → fetch `/ncit/search?term=` → render into `#ncit-results-panel / #ncit-results-container`
- `initDecTable()` — `#add-dec-btn` appends rows to `#dec-table-body`; delete via `.dec-delete-btn` delegation
- `initKanban()` — `.kanban-advance-btn` / `.kanban-reject-btn` POST to `/governance/advance/<id>` and `/governance/reject/<id>`; removes card on success
- `initAuditDiff()` — `.audit-diff-toggle` toggles `.d-none` on adjacent `.audit-diff-row`
- `initNcitSearch()` — `#ncit-search-btn` + `#ncit-search-input` on ncit_mapping page
- `showInlineToast(message, type)` — creates Bootstrap toast in `#toast-container`

**Template-to-route mapping:**
- `dashboard.html` → `dashboard.index`
- `ingestion.html` → `ingestion.index`
- `bc_list.html` → `bc.index`
- `bc_detail.html` → `bc.detail` (edit) and `bc.new_bc` (create)
- `ncit_mapping.html` → `ncit.mapping`
- `specializations.html` → `specializations.index`
- `governance.html` → `governance.board`
- `audit.html` → `audit.index`

**Template context variable conventions:**
- BC list: `bcs`, `pagination`, `categories`, `total_count`, `form`
- BC detail: `bc` (model instance or None for new), `form`
- Dashboard: `stats` dict (keys: `total_bcs`, `pending_review`, `published`, `recent_additions`), `recent_submissions`, `governance_items`
- Governance: `columns` dict (keys: `provisional`, `sme_review`, `cdisc_approval`, `published`)
- Audit: `audit_logs`, `pagination`
- Ingestion: `parsed_results`, `form`
- NCIT mapping: `conflict_bcs`
- Specializations: `specializations`, `available_bcs`, `editing_spec`, `form`

**Known avoidance:** Complex Jinja `replace` filters with quote escaping inside HTML `onsubmit` attributes cause syntax errors. Use simple string literals or move confirm logic to JS.
