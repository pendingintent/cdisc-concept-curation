"""Notes on a BC or Specialization — shared by routes and the MCP server.

Notes are collaborative commentary only: never exported in the governance
spreadsheet/BC export, never deleted (only resolved/flagged/edited), and
locked once the parent entity reaches Ready to Publish (status="published"),
matching the edit-lock already enforced on the entity's own fields.
"""

import logging
from datetime import datetime, timezone

from extensions import db
from models.note import Note
from services.audit import log_change
from services.bc_service import NotFoundError, _get_bc_or_raise
from services.governance_service import _get_spec_or_raise

logger = logging.getLogger(__name__)


def _check_not_locked(entity):
    if entity.status == "published":
        raise ValueError("This item has reached Ready to Publish status; notes cannot be added or changed")


def _get_note_or_raise(note_id):
    note = db.session.get(Note, note_id)
    if note is None:
        raise NotFoundError(f"Note {note_id!r} not found")
    return note


def _parent_entity(note):
    return note.bc if note.bc_id else note.specialization


def create_note(id_field, id_value, text, actor="user"):
    """Create a note on a BC (id_field="bc_id") or Specialization (id_field="vlm_group_id")."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Note text is required")
    entity = _get_bc_or_raise(id_value) if id_field == "bc_id" else _get_spec_or_raise(id_value)
    _check_not_locked(entity)
    note = Note(**{id_field: id_value}, text=text, created_by=actor)
    db.session.add(note)
    db.session.flush()  # assign note.id for the audit record
    log_change("Note", note.id, "created", actor=actor, after=note.to_dict())
    db.session.commit()
    return note


def create_bc_note(bc_id, text, actor="user"):
    return create_note("bc_id", bc_id, text, actor=actor)


def create_spec_note(vlm_group_id, text, actor="user"):
    return create_note("vlm_group_id", vlm_group_id, text, actor=actor)


def update_note_text(note_id, text, actor="user"):
    text = (text or "").strip()
    if not text:
        raise ValueError("Note text is required")
    note = _get_note_or_raise(note_id)
    _check_not_locked(_parent_entity(note))
    before = note.to_dict()
    note.text = text
    note.updated_at = datetime.now(timezone.utc)
    log_change("Note", note.id, "updated", actor=actor, before=before, after=note.to_dict())
    db.session.commit()
    return note


def set_resolved(note_id, resolved, actor="user"):
    note = _get_note_or_raise(note_id)
    _check_not_locked(_parent_entity(note))
    before = note.to_dict()
    note.resolved = bool(resolved)
    note.resolved_at = datetime.now(timezone.utc) if resolved else None
    note.resolved_by = actor if resolved else None
    log_change("Note", note.id, "resolved" if resolved else "unresolved", actor=actor, before=before, after=note.to_dict())
    db.session.commit()
    return note


def set_flagged(note_id, flagged, actor="user"):
    note = _get_note_or_raise(note_id)
    _check_not_locked(_parent_entity(note))
    before = note.to_dict()
    note.flagged = bool(flagged)
    log_change("Note", note.id, "flagged" if flagged else "unflagged", actor=actor, before=before, after=note.to_dict())
    db.session.commit()
    return note


def list_notes_for_entity(id_field, id_value):
    """Return notes for a BC or Specialization, most recent first."""
    return Note.query.filter_by(**{id_field: id_value}).order_by(Note.created_at.desc()).all()


def list_bc_notes(bc_id):
    return list_notes_for_entity("bc_id", bc_id)


def list_spec_notes(vlm_group_id):
    return list_notes_for_entity("vlm_group_id", vlm_group_id)
