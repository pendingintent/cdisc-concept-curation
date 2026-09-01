"""Tests for services/notes_service.py."""

import pytest

from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept
from models.note import Note
from models.specialization import DatasetSpecialization
from services import notes_service


class TestCreateNote:
    def test_create_bc_note(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "Please double-check units", actor="alice")
            assert note.id is not None
            assert note.bc_id == sample_bc
            assert note.vlm_group_id is None
            assert note.text == "Please double-check units"
            assert note.created_by == "alice"
            assert note.flagged is False
            assert note.resolved is False

    def test_create_spec_note(self, app, sample_spec):
        with app.app_context():
            note = notes_service.create_spec_note(sample_spec, "Check variable mapping", actor="bob")
            assert note.vlm_group_id == sample_spec
            assert note.bc_id is None

    def test_blank_text_raises(self, app, sample_bc):
        with app.app_context():
            with pytest.raises(ValueError, match="required"):
                notes_service.create_bc_note(sample_bc, "   ")

    def test_missing_bc_raises(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                notes_service.create_bc_note("NOPE", "text")

    def test_missing_spec_raises(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                notes_service.create_spec_note("NOPE.SDTM", "text")

    def test_writes_audit_log(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text", actor="alice")
            log = AuditLog.query.filter_by(entity_type="Note", entity_id=str(note.id), action="created").first()
            assert log is not None
            assert log.after_state["text"] == "text"

    def test_locked_when_bc_published(self, app, sample_bc):
        with app.app_context():
            bc = db.session.get(BiomedicalConcept, sample_bc)
            bc.status = "published"
            db.session.commit()
            with pytest.raises(ValueError, match="Ready to Publish"):
                notes_service.create_bc_note(sample_bc, "text")

    def test_locked_when_spec_published(self, app, sample_spec):
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, sample_spec)
            spec.status = "published"
            db.session.commit()
            with pytest.raises(ValueError, match="Ready to Publish"):
                notes_service.create_spec_note(sample_spec, "text")


class TestUpdateNoteText:
    def test_updates_text(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "original")
            updated = notes_service.update_note_text(note.id, "revised", actor="alice")
            assert updated.text == "revised"

    def test_blank_text_raises(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "original")
            with pytest.raises(ValueError, match="required"):
                notes_service.update_note_text(note.id, "  ")

    def test_missing_note_raises(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                notes_service.update_note_text(999, "text")

    def test_writes_audit_log_with_before_after(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "original")
            notes_service.update_note_text(note.id, "revised", actor="alice")
            log = AuditLog.query.filter_by(entity_type="Note", entity_id=str(note.id), action="updated").first()
            assert log.before_state["text"] == "original"
            assert log.after_state["text"] == "revised"

    def test_locked_when_parent_published(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "original")
            bc = db.session.get(BiomedicalConcept, sample_bc)
            bc.status = "published"
            db.session.commit()
            with pytest.raises(ValueError, match="Ready to Publish"):
                notes_service.update_note_text(note.id, "revised")


class TestSetResolved:
    def test_resolve_sets_fields(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            resolved = notes_service.set_resolved(note.id, True, actor="alice")
            assert resolved.resolved is True
            assert resolved.resolved_at is not None
            assert resolved.resolved_by == "alice"

    def test_unresolve_clears_fields(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            notes_service.set_resolved(note.id, True, actor="alice")
            unresolved = notes_service.set_resolved(note.id, False, actor="bob")
            assert unresolved.resolved is False
            assert unresolved.resolved_at is None
            assert unresolved.resolved_by is None

    def test_writes_audit_log(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            notes_service.set_resolved(note.id, True, actor="alice")
            log = AuditLog.query.filter_by(entity_type="Note", entity_id=str(note.id), action="resolved").first()
            assert log is not None
            notes_service.set_resolved(note.id, False, actor="alice")
            log = AuditLog.query.filter_by(entity_type="Note", entity_id=str(note.id), action="unresolved").first()
            assert log is not None

    def test_locked_when_parent_published(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            bc = db.session.get(BiomedicalConcept, sample_bc)
            bc.status = "published"
            db.session.commit()
            with pytest.raises(ValueError, match="Ready to Publish"):
                notes_service.set_resolved(note.id, True)


class TestSetFlagged:
    def test_flag_sets_field(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            flagged = notes_service.set_flagged(note.id, True, actor="alice")
            assert flagged.flagged is True

    def test_unflag_clears_field(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            notes_service.set_flagged(note.id, True)
            unflagged = notes_service.set_flagged(note.id, False)
            assert unflagged.flagged is False

    def test_writes_audit_log(self, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            notes_service.set_flagged(note.id, True, actor="alice")
            log = AuditLog.query.filter_by(entity_type="Note", entity_id=str(note.id), action="flagged").first()
            assert log is not None

    def test_locked_when_parent_published(self, app, sample_spec):
        with app.app_context():
            note = notes_service.create_spec_note(sample_spec, "text")
            spec = db.session.get(DatasetSpecialization, sample_spec)
            spec.status = "published"
            db.session.commit()
            with pytest.raises(ValueError, match="Ready to Publish"):
                notes_service.set_flagged(note.id, True)


class TestListNotes:
    def test_most_recent_first(self, app, sample_bc):
        with app.app_context():
            first = notes_service.create_bc_note(sample_bc, "first")
            second = notes_service.create_bc_note(sample_bc, "second")
            notes = notes_service.list_bc_notes(sample_bc)
            assert [n.id for n in notes] == [second.id, first.id]

    def test_scoped_per_entity(self, app, sample_bc, sample_spec):
        with app.app_context():
            notes_service.create_bc_note(sample_bc, "bc note")
            notes_service.create_spec_note(sample_spec, "spec note")
            assert len(notes_service.list_bc_notes(sample_bc)) == 1
            assert len(notes_service.list_spec_notes(sample_spec)) == 1

    def test_no_delete_capability(self, app, sample_bc):
        """Regression guard for the issue's 'no delete' requirement: the
        service module intentionally has no delete_note function."""
        with app.app_context():
            assert not hasattr(notes_service, "delete_note")


class TestNoteOneEntityConstraintViaService:
    def test_note_query_filters_do_not_cross_entities(self, app, sample_bc, sample_spec):
        with app.app_context():
            notes_service.create_bc_note(sample_bc, "bc note")
            all_notes = Note.query.all()
            assert len(all_notes) == 1
