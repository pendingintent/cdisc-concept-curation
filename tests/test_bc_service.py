"""Tests for services/bc_service.py — write operations shared by routes/MCP."""

from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept
from services.bc_service import get_or_create_bc_stub


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
