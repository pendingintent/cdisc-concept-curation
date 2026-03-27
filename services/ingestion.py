import io
import json
import pandas as pd
from difflib import SequenceMatcher


# Canonical BC field names and known aliases for fuzzy field mapping
FIELD_MAP = {
    'bc_id': ['bc_id', 'bcid', 'concept_id', 'id', 'identifier'],
    'short_name': ['short_name', 'shortname', 'name', 'bc_name', 'concept_name', 'title'],
    'definition': ['definition', 'def', 'description', 'desc'],
    'ncit_code': ['ncit_code', 'ncit', 'nci_code', 'c_code', 'ccode'],
    'parent_bc_id': ['parent_bc_id', 'parent_id', 'parent', 'parentid'],
    'bc_categories': ['bc_categories', 'categories', 'category', 'class', 'domain'],
    'synonyms': ['synonyms', 'synonym', 'aliases', 'alt_names'],
    'result_scales': ['result_scales', 'scale', 'scales', 'result_scale', 'data_scale'],
    'system': ['system', 'coding_system', 'system_url', 'system_uri'],
    'system_name': ['system_name', 'systemname', 'coding_system_name'],
    'code': ['code', 'external_code', 'loinc', 'snomed'],
    'package_date': ['package_date', 'date', 'release_date'],
    'dec_id': ['dec_id', 'decid', 'data_element_id'],
    'ncit_dec_code': ['ncit_dec_code', 'dec_ncit', 'dec_code'],
    'dec_label': ['dec_label', 'label', 'dec_name', 'element_label'],
    'data_type': ['data_type', 'datatype', 'type', 'value_type'],
    'example_set': ['example_set', 'examples', 'example_values', 'values'],
}


def _similarity(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _match_field(col_name):
    """Return (canonical_field, confidence) for a column name."""
    col_lower = col_name.lower().replace(' ', '_').replace('-', '_')
    best_field, best_score = None, 0.0
    for canonical, aliases in FIELD_MAP.items():
        for alias in aliases:
            score = _similarity(col_lower, alias)
            if score > best_score:
                best_score = score
                best_field = canonical
    return best_field, round(best_score, 2)


def map_fields(raw_dict):
    """
    Map a raw dict (from any source) to canonical BC field names.
    Returns (mapped_dict, field_confidences).
    """
    mapped = {}
    confidences = {}
    for col, value in raw_dict.items():
        if value is None or (isinstance(value, float) and str(value) == 'nan'):
            continue
        field, score = _match_field(str(col))
        if field and score > 0.5:
            mapped[field] = str(value).strip() if value is not None else ''
            confidences[field] = score
    return mapped, confidences


def validate_bc(bc_dict):
    """
    Validate a BC dict against CDISC curation rules.
    Returns list of validation error strings.
    """
    errors = []
    if not bc_dict.get('short_name'):
        errors.append('short_name is required')
    if not bc_dict.get('definition'):
        errors.append('definition is required')
    if not bc_dict.get('bc_id') and not bc_dict.get('ncit_code'):
        errors.append('Either bc_id (NCIt C-code) or ncit_code is required')
    # NCIt code format check
    ncit = bc_dict.get('ncit_code') or bc_dict.get('bc_id', '')
    if ncit and not ncit.upper().startswith('C'):
        errors.append(f'NCIt code should start with C (got: {ncit})')
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
        bc_id = mapped.get('bc_id') or mapped.get('ncit_code', '')
        if not bc_id:
            continue
        if bc_id not in groups:
            groups[bc_id] = {'mapped': {}, 'confidences': {}, 'decs': [], 'source_sheet': sheet}
        g = groups[bc_id]
        if mapped.get('definition') and not g['mapped'].get('definition'):
            # Absorb BC-level fields from this row
            for k, v in mapped.items():
                if k not in ('dec_id', 'ncit_dec_code', 'dec_label', 'data_type', 'example_set'):
                    g['mapped'][k] = v
            g['confidences'].update(confs)
        if mapped.get('dec_id') or mapped.get('dec_label'):
            g['decs'].append({
                'dec_id': mapped.get('dec_id', ''),
                'ncit_dec_code': mapped.get('ncit_dec_code', ''),
                'dec_label': mapped.get('dec_label', ''),
                'data_type': mapped.get('data_type', 'string'),
                'example_set': mapped.get('example_set', ''),
            })
        # If still no definition absorbed, keep the mapped fields
        if not g['mapped']:
            g['mapped'].update(mapped)
            g['confidences'].update(confs)

    results = []
    for bc_id, g in groups.items():
        mapped = g['mapped']
        if not mapped.get('bc_id') and bc_id:
            mapped['bc_id'] = bc_id
        errors = validate_bc(mapped)
        results.append({
            'mapped': mapped,
            'confidences': g['confidences'],
            'decs': g['decs'],
            'errors': errors,
            'source_sheet': g['source_sheet'],
        })
    return results


def parse_xlsx(file_obj):
    """
    Parse an XLSX file, grouping DEC sub-rows under their parent BC by bc_id.
    Returns one record per unique BC.
    """
    results = []
    try:
        xl = pd.ExcelFile(file_obj)
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            rows = []
            for _, row in df.iterrows():
                raw = row.to_dict()
                mapped, confs = map_fields(raw)
                if mapped:
                    rows.append((mapped, confs))
            results.extend(_group_by_bc(rows, sheet=sheet))
    except Exception as e:
        results.append({'error': str(e), 'mapped': {}, 'confidences': {}, 'decs': [], 'errors': [str(e)]})
    return results


def parse_csv(file_obj):
    """Parse a CSV file into BC records."""
    results = []
    try:
        df = pd.read_csv(file_obj)
        for _, row in df.iterrows():
            raw = row.to_dict()
            mapped, confs = map_fields(raw)
            if not mapped:
                continue
            errors = validate_bc(mapped)
            results.append({
                'raw': {k: str(v) for k, v in raw.items() if v is not None},
                'mapped': mapped,
                'confidences': confs,
                'errors': errors,
            })
    except Exception as e:
        results.append({'error': str(e), 'raw': {}, 'mapped': {}, 'confidences': {}, 'errors': [str(e)]})
    return results


def parse_json(file_obj):
    """Parse a JSON file (array of objects) into BC records."""
    results = []
    try:
        data = json.load(file_obj)
        if isinstance(data, dict):
            data = [data]
        for item in data:
            mapped, confs = map_fields(item)
            if not mapped:
                continue
            errors = validate_bc(mapped)
            results.append({
                'raw': {k: str(v) for k, v in item.items()},
                'mapped': mapped,
                'confidences': confs,
                'errors': errors,
            })
    except Exception as e:
        results.append({'error': str(e), 'raw': {}, 'mapped': {}, 'confidences': {}, 'errors': [str(e)]})
    return results


def deduplicate(parsed_records, existing_ids):
    """
    Flag records that duplicate existing BC IDs.
    existing_ids: set of bc_id strings already in the library.
    Returns same list with 'duplicate': True/False added.
    """
    for rec in parsed_records:
        bc_id = rec.get('mapped', {}).get('bc_id') or rec.get('mapped', {}).get('ncit_code', '')
        rec['duplicate'] = bc_id.upper() in {e.upper() for e in existing_ids}
    return parsed_records
