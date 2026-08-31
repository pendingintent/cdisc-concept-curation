import json
import logging
from difflib import SequenceMatcher

import pandas as pd

from models.bc import RESULT_SCALES, split_result_scales

logger = logging.getLogger(__name__)

# Canonical BC field names and known aliases for fuzzy field mapping
FIELD_MAP = {
    "bc_id": ["bc_id", "bcid", "concept_id", "id", "identifier"],
    "short_name": ["short_name", "shortname", "name", "bc_name", "concept_name", "title"],
    "definition": ["definition", "def", "description", "desc"],
    "ncit_code": ["ncit_code", "ncit", "nci_code", "c_code", "ccode"],
    "parent_bc_id": ["parent_bc_id", "parent_id", "parent", "parentid"],
    "bc_categories": ["bc_categories", "categories", "category", "class", "domain"],
    "synonyms": ["synonyms", "synonym", "aliases", "alt_names"],
    "result_scales": ["result_scales", "scale", "scales", "result_scale", "data_scale"],
    "system": ["system", "coding_system", "system_url", "system_uri"],
    "system_name": ["system_name", "systemname", "coding_system_name"],
    "code": ["code", "external_code", "loinc", "snomed"],
    "package_date": ["package_date", "date", "release_date"],
    "dec_id": ["dec_id", "decid", "data_element_id"],
    "ncit_dec_code": ["ncit_dec_code", "dec_ncit", "dec_code"],
    "dec_label": ["dec_label", "label", "dec_name", "element_label"],
    "data_type": ["data_type", "datatype", "type", "value_type"],
    "example_set": ["example_set", "examples", "example_values", "values"],
}

# Spec-level fields (one value per specialization, taken from the first row
# of its vlm_group_id group).
SPEC_HEADER_FIELDS = ("vlm_group_id", "bc_id", "domain", "short_name", "package_date")

# Per-variable fields (one row per SDTM VLM variable, columns I-AF of the
# SDTM_LB/SDTM_VS worksheets) — every one of these is a real worksheet
# column, listed in source-column order. Each maps to itself only: with
# ~24 similarly-named columns in these sheets (e.g. mandatory_variable vs
# mandatory_value, assigned_term vs assigned_value), fuzzy-matching against
# a short curated alias list caused silent cross-column overwrites (e.g.
# assigned_value scoring high enough against sdtm_variable's aliases to
# clobber the real variable name) — an exact 1:1 map for every column
# sidesteps that entirely, since a column always scores 1.0 against itself.
VARIABLE_FIELD_DEFS = (
    ("sdtm_variable", "Variable"),
    ("dec_id", "DEC ID"),
    ("nsv_flag", "NSV Flag"),
    ("codelist", "Codelist"),
    ("codelist_submission_value", "Codelist Submission Value"),
    ("subset_codelist", "Subset Codelist"),
    ("value_list", "Value List"),
    ("assigned_term", "Assigned Term"),
    ("assigned_value", "Assigned Value"),
    ("role", "Role"),
    ("subject", "Subject"),
    ("linking_phrase", "Linking Phrase"),
    ("predicate_term", "Predicate Term"),
    ("object", "Object"),
    ("data_type", "Data Type"),
    ("length", "Length"),
    ("format", "Format"),
    ("significant_digits", "Significant Digits"),
    ("mandatory_variable", "Mandatory Variable"),
    ("mandatory_value", "Mandatory Value"),
    ("origin_type", "Origin Type"),
    ("origin_source", "Origin Source"),
    ("comparator", "Comparator"),
    ("vlm_target", "VLM Target"),
)
VARIABLE_FIELDS = tuple(f for f, _ in VARIABLE_FIELD_DEFS)

# Canonical Dataset Specialization field names and aliases. Kept separate
# from FIELD_MAP (rather than merged) so the wide SDTM VLM sheets don't get
# force-matched onto unrelated BC/DEC fields by fuzzy similarity.
#
# domain holds the actual SDTM domain codelist value (e.g. "LB", "VS"), as
# stored in the worksheet's own `domain` column — not a literal "SDTM"/
# "CDASH" toggle.
SPEC_FIELD_MAP = {
    "vlm_group_id": ["vlm_group_id", "vlmgroupid", "group_id"],
    "bc_id": ["bc_id", "bcid", "concept_id"],
    "domain": ["domain", "sdtm_domain"],
    "short_name": ["short_name", "shortname", "name"],
    "package_date": ["package_date", "date", "release_date"],
    **{field: [field] for field in VARIABLE_FIELDS},
}


def _similarity(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _match_field(col_name, field_map=FIELD_MAP):
    """Return (canonical_field, confidence) for a column name."""
    col_lower = col_name.lower().replace(" ", "_").replace("-", "_")
    best_field, best_score = None, 0.0
    for canonical, aliases in field_map.items():
        for alias in aliases:
            score = _similarity(col_lower, alias)
            if score > best_score:
                best_score = score
                best_field = canonical
    return best_field, round(best_score, 2)


def map_fields(raw_dict, field_map=FIELD_MAP):
    """
    Map a raw dict (from any source) to canonical field names.
    Returns (mapped_dict, field_confidences).
    """
    mapped = {}
    confidences = {}
    for col, value in raw_dict.items():
        if value is None or (isinstance(value, float) and str(value) == "nan"):
            continue
        field, score = _match_field(str(col), field_map)
        if field and score > 0.5:
            mapped[field] = str(value).strip() if value is not None else ""
            confidences[field] = score
    return mapped, confidences


def _detect_record_type(columns, sheet_name=None):
    """Decide whether a sheet/file holds BC rows or Dataset Specialization rows.

    An explicit BC_/SDTM_/CDASH_ sheet-name prefix is authoritative when
    present; otherwise fall back to checking for a vlm_group_id column,
    which is the signature of the specialization VLM export shape.
    """
    if sheet_name:
        upper = sheet_name.upper()
        if upper.startswith("SDTM_") or upper.startswith("CDASH_"):
            return "specialization"
        if upper.startswith("BC_"):
            return "bc"
    for col in columns:
        field, score = _match_field(str(col), SPEC_FIELD_MAP)
        if field == "vlm_group_id" and score > 0.8:
            return "specialization"
    return "bc"


def validate_bc(bc_dict):
    """
    Validate a BC dict against CDISC curation rules.
    Returns list of validation error strings.
    """
    errors = []
    if not bc_dict.get("short_name"):
        errors.append("short_name is required")
    if not bc_dict.get("definition"):
        errors.append("definition is required")
    if not bc_dict.get("bc_id") and not bc_dict.get("ncit_code"):
        errors.append("Either bc_id (NCIt C-code) or ncit_code is required")
    # NCIt code format check
    ncit = bc_dict.get("ncit_code") or bc_dict.get("bc_id", "")
    if ncit and not ncit.upper().startswith("C"):
        errors.append(f"NCIt code should start with C (got: {ncit})")
    unsupported = [s for s in split_result_scales(bc_dict.get("result_scales")) if s not in RESULT_SCALES]
    if unsupported:
        errors.append(f"Unsupported result scale(s): {', '.join(unsupported)} — not in allowed list ({', '.join(RESULT_SCALES)})")
    return errors


def validate_specialization(mapped):
    """
    Validate a Dataset Specialization dict. Format-only (parse-time) checks —
    whether bc_id refers to an existing local BC is a runtime concern checked
    at approval time, not here.
    Returns list of validation error strings.
    """
    errors = []
    if not mapped.get("vlm_group_id"):
        errors.append("vlm_group_id is required")
    if not mapped.get("bc_id"):
        errors.append("bc_id is required")
    return errors


def _group_by_bc(rows, sheet=None):
    """
    Group flat rows (each may be a BC row or a DEC sub-row) by bc_id.
    Rows sharing the same bc_id are merged: the first row with a definition
    becomes the BC record; rows with dec_id are collected as DECs.
    Returns a list of merged dicts ready for IngestionRecord creation.
    """
    from collections import OrderedDict

    groups = OrderedDict()
    for mapped, confs in rows:
        bc_id = mapped.get("bc_id") or mapped.get("ncit_code", "")
        if not bc_id:
            continue
        if bc_id not in groups:
            groups[bc_id] = {"mapped": {}, "confidences": {}, "decs": [], "source_sheet": sheet}
        g = groups[bc_id]
        if mapped.get("definition") and not g["mapped"].get("definition"):
            # Absorb BC-level fields from this row
            for k, v in mapped.items():
                if k not in ("dec_id", "ncit_dec_code", "dec_label", "data_type", "example_set"):
                    g["mapped"][k] = v
            g["confidences"].update(confs)
        if mapped.get("dec_id") or mapped.get("dec_label"):
            g["decs"].append(
                {
                    "dec_id": mapped.get("dec_id", ""),
                    "ncit_dec_code": mapped.get("ncit_dec_code", ""),
                    "dec_label": mapped.get("dec_label", ""),
                    "data_type": mapped.get("data_type", "string"),
                    "example_set": mapped.get("example_set", ""),
                }
            )
        # If still no definition absorbed, keep the mapped fields
        if not g["mapped"]:
            g["mapped"].update(mapped)
            g["confidences"].update(confs)

    results = []
    for bc_id, g in groups.items():
        mapped = g["mapped"]
        if not mapped.get("bc_id") and bc_id:
            mapped["bc_id"] = bc_id
        errors = validate_bc(mapped)
        results.append(
            {
                "record_type": "bc",
                "mapped": mapped,
                "confidences": g["confidences"],
                "decs": g["decs"],
                "errors": errors,
                "source_sheet": g["source_sheet"],
            }
        )
    return results


def _group_by_spec(rows, sheet=None):
    """
    Group flat rows (one per SDTM VLM variable) by vlm_group_id.
    The first row's spec-level fields (bc_id, domain, short_name,
    package_date) are kept; every row contributes one entry to the
    resulting record's variables list. domain holds the actual SDTM domain
    codelist value from the worksheet (e.g. "LB", "VS").
    Returns a list of merged dicts ready for IngestionRecord creation.
    """
    from collections import OrderedDict

    groups = OrderedDict()
    for mapped, confs in rows:
        vlm_group_id = mapped.get("vlm_group_id", "")
        if not vlm_group_id:
            continue
        if vlm_group_id not in groups:
            groups[vlm_group_id] = {"mapped": {}, "confidences": {}, "variables": [], "source_sheet": sheet}
        g = groups[vlm_group_id]
        for key in SPEC_HEADER_FIELDS:
            if mapped.get(key) and not g["mapped"].get(key):
                g["mapped"][key] = mapped[key]
        g["confidences"].update(confs)
        if mapped.get("sdtm_variable"):
            g["variables"].append({field: mapped.get(field, "") for field in VARIABLE_FIELDS})

    results = []
    for vlm_group_id, g in groups.items():
        mapped = g["mapped"]
        mapped.setdefault("vlm_group_id", vlm_group_id)
        mapped.setdefault("domain", "")
        errors = validate_specialization(mapped)
        results.append(
            {
                "record_type": "specialization",
                "mapped": mapped,
                "confidences": g["confidences"],
                "variables": g["variables"],
                "errors": errors,
                "source_sheet": g["source_sheet"],
            }
        )
    return results


def parse_xlsx(file_obj):
    """
    Parse an XLSX file. Each sheet is detected as either a BC sheet (DEC
    sub-rows grouped under their parent by bc_id) or a Dataset Specialization
    sheet (variable rows grouped under their parent by vlm_group_id).
    Returns one record per unique BC / specialization.
    """
    results = []
    try:
        xl = pd.ExcelFile(file_obj)
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            record_type = _detect_record_type(df.columns, sheet_name=sheet)
            field_map = SPEC_FIELD_MAP if record_type == "specialization" else FIELD_MAP
            rows = []
            for _, row in df.iterrows():
                raw = row.to_dict()
                mapped, confs = map_fields(raw, field_map)
                if mapped:
                    rows.append((mapped, confs))
            if record_type == "specialization":
                results.extend(_group_by_spec(rows, sheet=sheet))
            else:
                results.extend(_group_by_bc(rows, sheet=sheet))
    except Exception as e:
        # Broad by design: user-supplied files can fail in arbitrary ways
        # and the error is surfaced to the review queue via the record.
        logger.error("XLSX ingestion parse failed: %s", e, exc_info=True)
        results.append({"error": str(e), "mapped": {}, "confidences": {}, "decs": [], "errors": [str(e)]})
    return results


def parse_csv(file_obj):
    """Parse a CSV file into BC or Dataset Specialization records (one row each)."""
    results = []
    try:
        df = pd.read_csv(file_obj)
        record_type = _detect_record_type(df.columns)
        field_map = SPEC_FIELD_MAP if record_type == "specialization" else FIELD_MAP
        validate = validate_specialization if record_type == "specialization" else validate_bc
        for _, row in df.iterrows():
            raw = row.to_dict()
            mapped, confs = map_fields(raw, field_map)
            if not mapped:
                continue
            errors = validate(mapped)
            results.append(
                {
                    "record_type": record_type,
                    "raw": {k: str(v) for k, v in raw.items() if v is not None},
                    "mapped": mapped,
                    "confidences": confs,
                    "errors": errors,
                }
            )
    except Exception as e:
        # Broad by design — see parse_xlsx.
        logger.error("CSV ingestion parse failed: %s", e, exc_info=True)
        results.append({"error": str(e), "raw": {}, "mapped": {}, "confidences": {}, "errors": [str(e)]})
    return results


def parse_json(file_obj):
    """Parse a JSON file (array of objects) into BC or Dataset Specialization records."""
    results = []
    try:
        data = json.load(file_obj)
        if isinstance(data, dict):
            data = [data]
        record_type = _detect_record_type(data[0].keys()) if data else "bc"
        field_map = SPEC_FIELD_MAP if record_type == "specialization" else FIELD_MAP
        validate = validate_specialization if record_type == "specialization" else validate_bc
        for item in data:
            mapped, confs = map_fields(item, field_map)
            if not mapped:
                continue
            errors = validate(mapped)
            results.append(
                {
                    "record_type": record_type,
                    "raw": {k: str(v) for k, v in item.items()},
                    "mapped": mapped,
                    "confidences": confs,
                    "errors": errors,
                }
            )
    except Exception as e:
        # Broad by design — see parse_xlsx.
        logger.error("JSON ingestion parse failed: %s", e, exc_info=True)
        results.append({"error": str(e), "raw": {}, "mapped": {}, "confidences": {}, "errors": [str(e)]})
    return results


def deduplicate(parsed_records, existing_ids, existing_spec_ids=None):
    """
    Flag records that duplicate an existing BC id or specialization vlm_group_id.
    existing_ids: set of bc_id strings already in the library.
    existing_spec_ids: set of vlm_group_id strings already in the library.
    Returns same list with 'duplicate': True/False added.
    """
    existing_spec_ids = existing_spec_ids or set()
    for rec in parsed_records:
        if rec.get("record_type") == "specialization":
            key = rec.get("mapped", {}).get("vlm_group_id", "")
            rec["duplicate"] = key.upper() in {e.upper() for e in existing_spec_ids}
        else:
            bc_id = rec.get("mapped", {}).get("bc_id") or rec.get("mapped", {}).get("ncit_code", "")
            rec["duplicate"] = bc_id.upper() in {e.upper() for e in existing_ids}
    return parsed_records
