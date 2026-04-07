"""Tests for routes/governance.py — Kanban advance and reject."""
import pytest
from models.bc import BiomedicalConcept
from models.governance import GovernanceRecord
from models.audit import AuditLog
from extensions import db


STATUS_ORDER = ['provisional', 'sme_review', 'cdisc_approval', 'published']


class TestGovernanceBoard:
    def test_board_returns_200(self, client):
        r = client.get('/governance/board')
        assert r.status_code == 200


class TestAdvance:
    def test_advances_provisional_to_sme_review(self, client, app, sample_bc):
        client.post('/governance/advance/C12345')
        with app.app_context():
            bc = BiomedicalConcept.query.get('C12345')
            assert bc.status == 'sme_review'

    def test_advance_through_all_stages(self, client, app, sample_bc):
        for expected in ['sme_review', 'cdisc_approval', 'published']:
            client.post('/governance/advance/C12345')
        with app.app_context():
            bc = BiomedicalConcept.query.get('C12345')
            assert bc.status == 'published'

    def test_already_published_stays_published(self, client, app, sample_bc):
        # Advance to published
        for _ in range(3):
            client.post('/governance/advance/C12345')
        # Extra advance should not error or change status
        r = client.post('/governance/advance/C12345', follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            bc = BiomedicalConcept.query.get('C12345')
            assert bc.status == 'published'

    def test_advance_creates_governance_record(self, client, app, sample_bc):
        client.post('/governance/advance/C12345')
        with app.app_context():
            rec = GovernanceRecord.query.filter_by(bc_id='C12345', action='advanced').first()
            assert rec is not None

    def test_advance_writes_audit_log(self, client, app, sample_bc):
        client.post('/governance/advance/C12345')
        with app.app_context():
            log = AuditLog.query.filter_by(entity_id='C12345', action='status_changed').first()
            assert log is not None
            assert log.before_state == {'status': 'provisional'}
            assert log.after_state == {'status': 'sme_review'}

    def test_advance_nonexistent_bc_returns_404(self, client):
        r = client.post('/governance/advance/NOPE')
        assert r.status_code == 404

    def test_advance_ajax_returns_json(self, client, sample_bc):
        r = client.post(
            '/governance/advance/C12345',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'sme_review'
        assert data['bc_id'] == 'C12345'


class TestReject:
    def test_reject_returns_to_provisional(self, client, app, sample_bc):
        # First advance to sme_review, then reject
        client.post('/governance/advance/C12345')
        client.post('/governance/reject/C12345')
        with app.app_context():
            bc = BiomedicalConcept.query.get('C12345')
            assert bc.status == 'provisional'

    def test_reject_creates_governance_record(self, client, app, sample_bc):
        client.post('/governance/reject/C12345')
        with app.app_context():
            rec = GovernanceRecord.query.filter_by(bc_id='C12345', action='rejected').first()
            assert rec is not None

    def test_reject_writes_audit_log(self, client, app, sample_bc):
        client.post('/governance/advance/C12345')  # move to sme_review
        client.post('/governance/reject/C12345')
        with app.app_context():
            log = AuditLog.query.filter_by(entity_id='C12345', action='rejected').first()
            assert log is not None
            assert log.after_state == {'status': 'provisional'}

    def test_reject_ajax_returns_json(self, client, sample_bc):
        r = client.post(
            '/governance/reject/C12345',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'provisional'

    def test_reject_nonexistent_bc_returns_404(self, client):
        r = client.post('/governance/reject/NOPE')
        assert r.status_code == 404
