"""Tests for services/bc_service.py — write operations shared by routes/MCP."""

from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept, DataElementConcept
from services.bc_service import get_or_create_bc_stub, save_decs


class TestGetOrCreateBcStub:
    def test_creates_stub_when_missing(self, app):
        with app.app_context():
            bc = get_or_create_bc_stub("C999", short_name="New Concept", actor="user")
            assert bc.bc_id == "C999"
            assert bc.short_name == "New Concept"
            assert bc.status == "provisional"
            assert db.session.get(BiomedicalConcept, "C999") is not None

    def test_returns_existing_bc_unchanged(self, app, sample_bc):
        with app.app_context():
            bc = get_or_create_bc_stub(sample_bc, short_name="Ignored Name")
            assert bc.bc_id == sample_bc
            assert bc.short_name == "Test Concept"

    def test_writes_audit_log_on_create(self, app):
        with app.app_context():
            get_or_create_bc_stub("C999", short_name="New Concept", actor="user")
            log = AuditLog.query.filter_by(entity_type="BiomedicalConcept", entity_id="C999", action="created").first()
            assert log is not None

    def test_no_audit_log_when_already_exists(self, app, sample_bc):
        with app.app_context():
            AuditLog.query.delete()
            db.session.commit()
            get_or_create_bc_stub(sample_bc, short_name="Ignored Name")
            assert AuditLog.query.count() == 0


class TestSaveDecs:
    def test_creates_decs_from_list(self, app, sample_bc):
        with app.app_context():
            save_decs(sample_bc, [{"dec_label": "Systolic", "data_type": "decimal", "example_set": "120", "required": True}])
            decs = DataElementConcept.query.filter_by(bc_id=sample_bc).all()
            assert len(decs) == 1
            assert decs[0].dec_label == "Systolic"
            assert decs[0].required is True
            assert decs[0].dec_id == f"{sample_bc}.DEC.1"

    def test_blank_label_rows_are_skipped_but_keep_position(self, app, sample_bc):
        with app.app_context():
            save_decs(sample_bc, [{"dec_label": ""}, {"dec_label": "Diastolic"}])
            decs = DataElementConcept.query.filter_by(bc_id=sample_bc).all()
            assert len(decs) == 1
            assert decs[0].dec_id == f"{sample_bc}.DEC.2"

    def test_replaces_existing_decs(self, app, sample_bc):
        with app.app_context():
            save_decs(sample_bc, [{"dec_label": "Old"}])
            save_decs(sample_bc, [{"dec_label": "New"}])
            decs = DataElementConcept.query.filter_by(bc_id=sample_bc).all()
            assert len(decs) == 1
            assert decs[0].dec_label == "New"

    def test_empty_list_clears_all_decs(self, app, sample_bc):
        with app.app_context():
            save_decs(sample_bc, [{"dec_label": "Old"}])
            save_decs(sample_bc, [])
            assert DataElementConcept.query.filter_by(bc_id=sample_bc).count() == 0

    def test_preserves_provided_dec_id_and_ncit_code(self, app, sample_bc):
        with app.app_context():
            save_decs(sample_bc, [{"dec_id": "CUSTOM.ID", "ncit_dec_code": "C999", "dec_label": "Systolic"}])
            dec = DataElementConcept.query.filter_by(bc_id=sample_bc).first()
            assert dec.dec_id == "CUSTOM.ID"
            assert dec.ncit_dec_code == "C999"
