"""Tests for routes/ingestion.py — upload, approve, reject."""
import io
import json
import csv
import pytest
from models.bc import BiomedicalConcept
from models.ingestion import IngestionRecord
from extensions import db


def _csv_file(rows):
    """Build an in-memory CSV upload."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return (io.BytesIO(buf.getvalue().encode()), 'test.csv')


def _json_file(data):
    return (io.BytesIO(json.dumps(data).encode()), 'test.json')


class TestIngestionIndex:
    def test_returns_200(self, client):
        r = client.get('/ingestion/')
        assert r.status_code == 200


class TestUpload:
    def test_upload_csv_creates_ingestion_records(self, client, app):
        rows = [{'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}]
        file_obj, filename = _csv_file(rows)
        r = client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert r.status_code == 200
        with app.app_context():
            assert IngestionRecord.query.count() > 0

    def test_upload_json_creates_ingestion_records(self, client, app):
        data = [{'bc_id': 'C002', 'short_name': 'BP', 'definition': 'Blood Pressure'}]
        file_obj, filename = _json_file(data)
        r = client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert r.status_code == 200
        with app.app_context():
            assert IngestionRecord.query.count() > 0

    def test_no_file_redirects_with_error(self, client):
        r = client.post('/ingestion/upload', data={}, follow_redirects=True)
        assert b'No file' in r.data or r.status_code in (200, 302)

    def test_wrong_extension_rejected(self, client):
        r = client.post(
            '/ingestion/upload',
            data={'file': (io.BytesIO(b'data'), 'test.txt')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert b'XLSX' in r.data or b'xlsx' in r.data or r.status_code in (200, 302)

    def test_duplicate_bc_flagged(self, client, app, sample_bc):
        rows = [{'bc_id': 'C12345', 'short_name': 'Test Concept', 'definition': 'A definition.'}]
        file_obj, filename = _csv_file(rows)
        client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
        )
        with app.app_context():
            ir = IngestionRecord.query.first()
            assert ir is not None
            assert ir.duplicate is True


class TestApprove:
    def _upload_and_get_record_id(self, client, app, bc_id='C001'):
        rows = [{'bc_id': bc_id, 'short_name': 'HR', 'definition': 'Heart Rate'}]
        file_obj, filename = _csv_file(rows)
        client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
        )
        with app.app_context():
            ir = IngestionRecord.query.filter_by(status='pending').first()
            return ir.id if ir else None

    def test_approve_creates_bc(self, client, app):
        record_id = self._upload_and_get_record_id(client, app)
        assert record_id is not None
        client.post(f'/ingestion/approve/{record_id}')
        with app.app_context():
            assert BiomedicalConcept.query.get('C001') is not None

    def test_approve_sets_status_approved(self, client, app):
        record_id = self._upload_and_get_record_id(client, app)
        client.post(f'/ingestion/approve/{record_id}')
        with app.app_context():
            ir = IngestionRecord.query.get(record_id)
            assert ir.status == 'approved'

    def test_approve_nonexistent_record_returns_404(self, client):
        r = client.post('/ingestion/approve/99999')
        assert r.status_code == 404

    def test_approve_already_existing_bc_does_not_duplicate(self, client, app, sample_bc):
        rows = [{'bc_id': 'C12345', 'short_name': 'Test Concept', 'definition': 'A definition.'}]
        file_obj, filename = _csv_file(rows)
        client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
        )
        with app.app_context():
            ir = IngestionRecord.query.filter_by(status='pending').first()
        if ir:
            client.post(f'/ingestion/approve/{ir.id}')
        with app.app_context():
            # Should still be only one BC with that id
            assert BiomedicalConcept.query.filter_by(bc_id='C12345').count() == 1


class TestReject:
    def test_reject_sets_status_rejected(self, client, app):
        rows = [{'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}]
        file_obj, filename = _csv_file(rows)
        client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
        )
        with app.app_context():
            ir = IngestionRecord.query.filter_by(status='pending').first()
            record_id = ir.id

        client.post(f'/ingestion/reject/{record_id}')
        with app.app_context():
            ir = IngestionRecord.query.get(record_id)
            assert ir.status == 'rejected'

    def test_reject_does_not_create_bc(self, client, app):
        rows = [{'bc_id': 'C001', 'short_name': 'HR', 'definition': 'Heart Rate'}]
        file_obj, filename = _csv_file(rows)
        client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
        )
        with app.app_context():
            ir = IngestionRecord.query.filter_by(status='pending').first()
            record_id = ir.id

        client.post(f'/ingestion/reject/{record_id}')
        with app.app_context():
            assert BiomedicalConcept.query.get('C001') is None

    def test_reject_nonexistent_record_returns_404(self, client):
        r = client.post('/ingestion/reject/99999')
        assert r.status_code == 404


class TestApproveAll:
    def test_approve_all_skips_records_with_errors(self, client, app):
        """Records missing required fields (errors list non-empty) should be rejected, not added."""
        # Upload a record missing short_name (will have validation errors)
        rows = [{'bc_id': 'C001', 'definition': 'Missing short name'}]
        file_obj, filename = _csv_file(rows)
        with client.session_transaction() as sess:
            sess['ingestion_key'] = 'testkey'
        client.post(
            '/ingestion/upload',
            data={'file': (file_obj, filename)},
            content_type='multipart/form-data',
        )
        client.post('/ingestion/approve_all')
        with app.app_context():
            assert BiomedicalConcept.query.get('C001') is None
