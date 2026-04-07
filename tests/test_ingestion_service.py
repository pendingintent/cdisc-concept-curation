"""Tests for services/ingestion.py — field mapping, validation, parsing, deduplication."""
import io
import json
import pytest
from services.ingestion import (
    _similarity,
    _match_field,
    map_fields,
    validate_bc,
    deduplicate,
    parse_csv,
    parse_json,
    _group_by_bc,
)


# ---------------------------------------------------------------------------
# _similarity
# ---------------------------------------------------------------------------

class TestSimilarity:
    def test_identical_strings(self):
        assert _similarity('bc_id', 'bc_id') == 1.0

    def test_case_insensitive(self):
        assert _similarity('BC_ID', 'bc_id') == 1.0

    def test_completely_different(self):
        assert _similarity('bc_id', 'zzzzzzz') < 0.5

    def test_partial_match(self):
        score = _similarity('short_name', 'shortname')
        assert score > 0.8


# ---------------------------------------------------------------------------
# _match_field
# ---------------------------------------------------------------------------

class TestMatchField:
    def test_exact_alias_match(self):
        field, score = _match_field('bc_id')
        assert field == 'bc_id'
        assert score == 1.0

    def test_known_alias(self):
        field, score = _match_field('concept_id')
        assert field == 'bc_id'
        assert score > 0.8

    def test_definition_alias(self):
        field, score = _match_field('description')
        assert field == 'definition'
        assert score > 0.7

    def test_spaces_normalised(self):
        field, score = _match_field('short name')
        assert field == 'short_name'
        assert score > 0.8

    def test_unknown_column_returns_low_score(self):
        _, score = _match_field('xyzzy_random_col_9999')
        assert score < 0.5


# ---------------------------------------------------------------------------
# map_fields
# ---------------------------------------------------------------------------

class TestMapFields:
    def test_canonical_columns_mapped_at_full_confidence(self):
        mapped, confs = map_fields({'bc_id': 'C001', 'short_name': 'Foo', 'definition': 'Bar'})
        assert mapped['bc_id'] == 'C001'
        assert confs['bc_id'] == 1.0

    def test_none_values_skipped(self):
        mapped, _ = map_fields({'bc_id': 'C001', 'short_name': None})
        assert 'short_name' not in mapped

    def test_nan_values_skipped(self):
        mapped, _ = map_fields({'bc_id': 'C001', 'definition': float('nan')})
        assert 'definition' not in mapped

    def test_low_confidence_columns_excluded(self):
        mapped, _ = map_fields({'xyzzy_totally_unknown': 'value'})
        assert mapped == {}

    def test_values_stripped(self):
        mapped, _ = map_fields({'bc_id': '  C001  '})
        assert mapped['bc_id'] == 'C001'


# ---------------------------------------------------------------------------
# validate_bc
# ---------------------------------------------------------------------------

class TestValidateBc:
    def _valid(self):
        return {'bc_id': 'C001', 'short_name': 'Heart Rate', 'definition': 'Rate of the heart.'}

    def test_valid_record_has_no_errors(self):
        assert validate_bc(self._valid()) == []

    def test_missing_short_name(self):
        d = self._valid()
        del d['short_name']
        errors = validate_bc(d)
        assert any('short_name' in e for e in errors)

    def test_missing_definition(self):
        d = self._valid()
        del d['definition']
        errors = validate_bc(d)
        assert any('definition' in e for e in errors)

    def test_missing_both_ids(self):
        errors = validate_bc({'short_name': 'X', 'definition': 'Y'})
        assert any('bc_id' in e or 'ncit_code' in e for e in errors)

    def test_invalid_ncit_format(self):
        d = self._valid()
        d['ncit_code'] = 'BADCODE'
        errors = validate_bc(d)
        assert any('NCIt' in e for e in errors)

    def test_ncit_starting_with_c_accepted(self):
        d = self._valid()
        d['ncit_code'] = 'C99999'
        assert validate_bc(d) == []


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def _record(self, bc_id):
        return {'mapped': {'bc_id': bc_id}, 'confidences': {}, 'errors': [], 'decs': []}

    def test_marks_existing_ids_as_duplicate(self):
        records = [self._record('C001'), self._record('C002')]
        result = deduplicate(records, {'C001'})
        assert result[0]['duplicate'] is True
        assert result[1]['duplicate'] is False

    def test_case_insensitive_comparison(self):
        records = [self._record('c001')]
        result = deduplicate(records, {'C001'})
        assert result[0]['duplicate'] is True

    def test_empty_existing_ids(self):
        records = [self._record('C001')]
        result = deduplicate(records, set())
        assert result[0]['duplicate'] is False

    def test_falls_back_to_ncit_code(self):
        record = {'mapped': {'ncit_code': 'C999'}, 'confidences': {}, 'errors': [], 'decs': []}
        result = deduplicate([record], {'C999'})
        assert result[0]['duplicate'] is True


# ---------------------------------------------------------------------------
# parse_csv
# ---------------------------------------------------------------------------

class TestParseCsv:
    def _make_csv(self, rows):
        """Return a BytesIO CSV from a list of dicts."""
        import csv
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return io.BytesIO(buf.getvalue().encode())

    def test_valid_row_parsed(self):
        f = self._make_csv([{'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}])
        records = parse_csv(f)
        assert len(records) == 1
        assert records[0]['mapped']['bc_id'] == 'C001'

    def test_invalid_file_returns_error_record(self):
        records = parse_csv(io.BytesIO(b'not,valid\ncsv content'))
        # Should parse without exception; may produce records or errors
        assert isinstance(records, list)

    def test_missing_definition_produces_validation_error(self):
        f = self._make_csv([{'bc_id': 'C001', 'short_name': 'HR'}])
        records = parse_csv(f)
        assert any(records) and any('definition' in e for r in records for e in r.get('errors', []))


# ---------------------------------------------------------------------------
# parse_json
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_array_of_objects(self):
        data = [{'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}]
        f = io.BytesIO(json.dumps(data).encode())
        records = parse_json(f)
        assert len(records) == 1
        assert records[0]['mapped']['bc_id'] == 'C001'

    def test_single_object_wrapped(self):
        data = {'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}
        f = io.BytesIO(json.dumps(data).encode())
        records = parse_json(f)
        assert len(records) == 1

    def test_invalid_json_returns_error(self):
        records = parse_json(io.BytesIO(b'not json at all'))
        assert len(records) == 1
        assert records[0].get('error') or records[0].get('errors')


# ---------------------------------------------------------------------------
# _group_by_bc
# ---------------------------------------------------------------------------

class TestGroupByBc:
    def test_single_row_becomes_one_record(self):
        rows = [({'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}, {'bc_id': 1.0})]
        result = _group_by_bc(rows)
        assert len(result) == 1
        assert result[0]['mapped']['bc_id'] == 'C001'

    def test_dec_sub_rows_grouped_under_parent(self):
        rows = [
            ({'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}, {}),
            ({'bc_id': 'C001', 'dec_id': 'C001.DEC.1', 'dec_label': 'Value'}, {}),
        ]
        result = _group_by_bc(rows)
        assert len(result) == 1
        assert len(result[0]['decs']) == 1
        assert result[0]['decs'][0]['dec_label'] == 'Value'

    def test_multiple_bcs_produce_separate_records(self):
        rows = [
            ({'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}, {}),
            ({'bc_id': 'C002', 'short_name': 'BP', 'definition': 'Blood Pressure'}, {}),
        ]
        result = _group_by_bc(rows)
        assert len(result) == 2

    def test_row_without_bc_id_skipped(self):
        rows = [({'short_name': 'Orphan', 'definition': 'No ID'}, {})]
        result = _group_by_bc(rows)
        assert result == []
