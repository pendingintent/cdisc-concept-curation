"""Tests for services/bc_service.py — write operations shared by routes/MCP."""

from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept, DataElementConcept
from services.bc_service import build_bc_clone, get_or_create_bc_stub, save_decs


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


class TestBuildBcClone:
    def test_returns_none_for_missing_bc(self, app):
        with app.app_context():
            bc, decs = build_bc_clone("NOPE")
            assert bc is None
            assert decs is None

    def test_copies_group_level_fields_but_not_bc_id(self, app, sample_bc):
        with app.app_context():
            bc, _ = build_bc_clone(sample_bc)
            assert bc.bc_id is None
            assert bc.short_name == "Test Concept"
            assert bc.definition == "A test BC definition."
            assert bc.ncit_code == "C12345"

    def test_copies_decs_ordered_with_dec_id_blanked(self, app, sample_bc):
        with app.app_context():
            db.session.add_all(
                [
                    DataElementConcept(dec_id=f"{sample_bc}.DEC.1", bc_id=sample_bc, dec_label="Systolic", data_type="decimal", required=True, sort_order=0),
                    DataElementConcept(dec_id=f"{sample_bc}.DEC.2", bc_id=sample_bc, dec_label="Diastolic", data_type="decimal", required=False, sort_order=1),
                ]
            )
            db.session.commit()

            _, decs = build_bc_clone(sample_bc)

            assert [d["dec_label"] for d in decs] == ["Systolic", "Diastolic"]
            assert all(d["dec_id"] == "" for d in decs)
            assert decs[0]["required"] is True
            assert decs[0]["data_type"] == "decimal"

    def test_no_decs_returns_empty_list(self, app, sample_bc):
        with app.app_context():
            _, decs = build_bc_clone(sample_bc)
            assert decs == []
