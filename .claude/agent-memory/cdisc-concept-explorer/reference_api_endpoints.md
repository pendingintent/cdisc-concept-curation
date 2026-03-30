---
name: CDISC Library API Endpoints and Response Structure
description: Verified endpoint paths, response shapes, field names, and pagination behavior for CDISC COSMOS v2 API (biomedical concepts and dataset specializations)
type: reference
---

## Base URL
`https://api.library.cdisc.org/api/cosmos/v2`
Auth header: `api-key: $CDISC_API_KEY`

## Working Endpoints

| Purpose | Path |
|---|---|
| List all BCs | GET /mdr/bc/biomedicalconcepts |
| Single BC | GET /mdr/bc/biomedicalconcepts/{conceptId} |
| List all dataset specializations | GET /mdr/specializations/datasetspecializations |
| Single SDTM specialization | GET /mdr/specializations/sdtm/datasetspecializations/{id} |

**404**: `/mdr/bc/datasetspecializations` does not exist.

## Pagination
None. Both list endpoints return the full collection in one response (~1127 BCs, ~1123 SDTM specs as of 2026-03-30). `page`/`size` query params are silently ignored.

## List Response Shape
Top-level keys: `name`, `label`, `_links`
- BC list: `_links.biomedicalConcepts` is a flat array of `{href, title, type}`
- DS list: `_links.datasetSpecializations.sdtm` is an array of `{href, title, type}` (nested under standard key)

## Single BC Record Fields
`conceptId`, `ncitCode`, `shortName`, `definition`, `categories` (string[]), `resultScales` (string[]), `synonyms` (string[]), `dataElementConcepts` (object[]), `href`, `_links`

## Single Dataset Specialization Record Fields
`datasetSpecializationId`, `domain`, `shortName`, `source`, `sdtmigStartVersion`, `sdtmigEndVersion`, `variables` (object[]), `_links`

Each variable has: `name`, `dataElementConceptId`, `role`, `dataType`, `length`, `relationship`, `mandatoryVariable`, `mandatoryValue`, `originType`, `originSource`, `isNonStandard`
