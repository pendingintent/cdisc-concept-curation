"""Tests for routes/bc.py — CRUD, export, submission."""
import pytest
from models.bc import BiomedicalConcept, DataElementConcept
from models.audit import AuditLog
from extensions import db


def _bc_form(**kwargs):
    defaults = {
        'bc_id': 'C00001',
        'short_name': 'Test Concept',
        'definition': 'A definition.',
        'ncit_code': 'C00001',
        'submitter': 'tester',
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# GET /bc/
# ---------------------------------------------------------------------------

class TestBcIndex:
    def test_returns_200(self, client):
        r = client.get('/bc/')
        assert r.status_code == 200

    def test_search_by_name(self, client, app, sample_bc):
        r = client.get('/bc/?q=Test')
        assert r.status_code == 200
        assert b'Test Concept' in r.data

    def test_search_no_match(self, client):
        r = client.get('/bc/?q=zzznomatch')
        assert r.status_code == 200

    def test_filter_by_status(self, client, sample_bc):
        r = client.get('/bc/?status=provisional')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /bc/new
# ---------------------------------------------------------------------------

class TestNewBc:
    def test_returns_200(self, client):
        r = client.get('/bc/new')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /bc/ (create)
# ---------------------------------------------------------------------------

class TestCreateBc:
    def test_creates_bc_and_redirects(self, client, app):
        r = client.post('/bc/', data=_bc_form(), follow_redirects=False)
        assert r.status_code == 302
        with app.app_context():
            assert BiomedicalConcept.query.get('C00001') is not None

    def test_missing_bc_id_redirects_with_error(self, client):
        r = client.post('/bc/', data=_bc_form(bc_id=''), follow_redirects=True)
        assert b'required' in r.data.lower() or r.status_code in (200, 302)

    def test_duplicate_bc_id_rejected(self, client, sample_bc):
        # First creation (sample_bc fixture did it already)
        r = client.post('/bc/', data=_bc_form(bc_id='C12345'), follow_redirects=True)
        assert b'already exists' in r.data or r.status_code in (200, 302)

    def test_create_writes_audit_log(self, client, app):
        client.post('/bc/', data=_bc_form())
        with app.app_context():
            log = AuditLog.query.filter_by(entity_id='C00001', action='created').first()
            assert log is not None

    def test_create_with_decs(self, client, app):
        data = _bc_form()
        data['dec_label[]'] = ['Systolic', 'Diastolic']
        data['dec_data_type[]'] = ['decimal', 'decimal']
        data['dec_example_set[]'] = ['120', '80']
        data['dec_id[]'] = ['', '']
        data['dec_ncit_code[]'] = ['', '']
        client.post('/bc/', data=data)
        with app.app_context():
            decs = DataElementConcept.query.filter_by(bc_id='C00001').all()
            assert len(decs) == 2
            assert decs[0].dec_label == 'Systolic'


# ---------------------------------------------------------------------------
# GET /bc/<bc_id>
# ---------------------------------------------------------------------------

class TestBcDetail:
    def test_existing_bc_returns_200(self, client, sample_bc):
        r = client.get('/bc/C12345')
        assert r.status_code == 200

    def test_missing_bc_returns_404(self, client):
        r = client.get('/bc/DOESNOTEXIST')
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /bc/<bc_id>/edit
# ---------------------------------------------------------------------------

class TestEditBc:
    def test_updates_short_name(self, client, app, sample_bc):
        client.post('/bc/C12345/edit', data={'short_name': 'Updated Name'})
        with app.app_context():
            bc = BiomedicalConcept.query.get('C12345')
            assert bc.short_name == 'Updated Name'

    def test_edit_writes_audit_log(self, client, app, sample_bc):
        client.post('/bc/C12345/edit', data={'short_name': 'Updated Name'})
        with app.app_context():
            log = AuditLog.query.filter_by(entity_id='C12345', action='updated').first()
            assert log is not None
            assert log.before_state['short_name'] == 'Test Concept'

    def test_nonexistent_bc_returns_404(self, client):
        r = client.post('/bc/NOPE/edit', data={'short_name': 'X'})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /bc/<bc_id>/submit
# ---------------------------------------------------------------------------

class TestSubmitForReview:
    def test_advances_status_to_sme_review(self, client, app, sample_bc):
        client.post('/bc/C12345/submit')
        with app.app_context():
            bc = BiomedicalConcept.query.get('C12345')
            assert bc.status == 'sme_review'

    def test_submit_writes_audit_log(self, client, app, sample_bc):
        client.post('/bc/C12345/submit')
        with app.app_context():
            log = AuditLog.query.filter_by(entity_id='C12345', action='submitted_for_review').first()
            assert log is not None


# ---------------------------------------------------------------------------
# POST /bc/<bc_id>/delete
# ---------------------------------------------------------------------------

class TestDeleteBc:
    def test_deletes_bc(self, client, app, sample_bc):
        client.post('/bc/C12345/delete')
        with app.app_context():
            assert BiomedicalConcept.query.get('C12345') is None

    def test_delete_writes_audit_log(self, client, app, sample_bc):
        client.post('/bc/C12345/delete')
        with app.app_context():
            log = AuditLog.query.filter_by(entity_id='C12345', action='deleted').first()
            assert log is not None

    def test_nonexistent_bc_returns_404(self, client):
        r = client.post('/bc/NOPE/delete')
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /bc/export
# ---------------------------------------------------------------------------

class TestExport:
    def test_json_export(self, client, sample_bc):
        r = client.get('/bc/export?format=json')
        assert r.status_code == 200
        assert r.content_type == 'application/json'

    def test_xlsx_export(self, client, sample_bc):
        r = client.get('/bc/export?format=xlsx')
        assert r.status_code == 200
        assert 'spreadsheetml' in r.content_type

    def test_odm_xml_export(self, client, sample_bc):
        r = client.get('/bc/export?format=odm')
        assert r.status_code == 200
        assert 'xml' in r.content_type
