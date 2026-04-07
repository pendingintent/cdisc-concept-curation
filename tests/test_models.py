"""Tests for model property serialization and helper methods."""
import pytest
from models.audit import AuditLog
from models.ingestion import IngestionRecord
from models.bc import BiomedicalConcept, DataElementConcept
from extensions import db


class TestAuditLogJsonProperties:
    def test_before_state_round_trips(self, app):
        with app.app_context():
            log = AuditLog()
            log.before_state = {'status': 'provisional', 'bc_id': 'C001'}
            assert log.before_state == {'status': 'provisional', 'bc_id': 'C001'}

    def test_after_state_round_trips(self, app):
        with app.app_context():
            log = AuditLog()
            log.after_state = {'status': 'sme_review'}
            assert log.after_state == {'status': 'sme_review'}

    def test_none_before_state_returns_none(self, app):
        with app.app_context():
            log = AuditLog()
            assert log.before_state is None

    def test_none_after_state_returns_none(self, app):
        with app.app_context():
            log = AuditLog()
            assert log.after_state is None

    def test_persisted_log_retrieves_state(self, app):
        with app.app_context():
            log = AuditLog(
                entity_type='BiomedicalConcept',
                entity_id='C001',
                action='created',
                actor='tester',
            )
            log.after_state = {'bc_id': 'C001', 'short_name': 'Test'}
            db.session.add(log)
            db.session.commit()
            fetched = AuditLog.query.first()
            assert fetched.after_state['bc_id'] == 'C001'


class TestIngestionRecordProperties:
    def test_mapped_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.mapped = {'bc_id': 'C001', 'short_name': 'HR'}
            assert ir.mapped == {'bc_id': 'C001', 'short_name': 'HR'}

    def test_confidences_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.confidences = {'bc_id': 1.0, 'short_name': 0.9}
            assert ir.confidences == {'bc_id': 1.0, 'short_name': 0.9}

    def test_errors_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.errors = ['short_name is required']
            assert ir.errors == ['short_name is required']

    def test_decs_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.decs = [{'dec_id': 'C001.DEC.1', 'dec_label': 'Value'}]
            assert ir.decs[0]['dec_label'] == 'Value'

    def test_empty_mapped_returns_empty_dict(self, app):
        with app.app_context():
            ir = IngestionRecord()
            assert ir.mapped == {}

    def test_avg_confidence_computed_correctly(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.confidences = {'bc_id': 1.0, 'short_name': 0.8, 'definition': 0.6}
            assert ir.avg_confidence == round((1.0 + 0.8 + 0.6) / 3 * 100)

    def test_avg_confidence_empty_confidences(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.confidences = {}
            assert ir.avg_confidence == 0


class TestBiomedicalConceptToDict:
    def test_to_dict_contains_required_keys(self, app):
        with app.app_context():
            bc = BiomedicalConcept(
                bc_id='C001',
                short_name='Heart Rate',
                definition='Rate of the heart.',
                ncit_code='C001',
                status='provisional',
            )
            d = bc.to_dict()
            for key in ('bc_id', 'short_name', 'definition', 'ncit_code', 'status'):
                assert key in d

    def test_to_dict_values_match(self, app):
        with app.app_context():
            bc = BiomedicalConcept(bc_id='C002', short_name='BP', definition='Blood Pressure', ncit_code='C002')
            d = bc.to_dict()
            assert d['bc_id'] == 'C002'
            assert d['short_name'] == 'BP'

    def test_default_status_is_provisional(self, app):
        with app.app_context():
            bc = BiomedicalConcept(bc_id='C003', short_name='X', definition='Y')
            db.session.add(bc)
            db.session.commit()
            assert bc.status == 'provisional'
