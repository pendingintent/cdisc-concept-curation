"""Biomedical Concept write operations shared by routes and the MCP server.

Routes are thin adapters (form -> dict -> service -> flash/redirect);
MCP tools call the same functions, so every write goes through one code
path and the AuditLog contract holds everywhere.
"""

import logging
from datetime import datetime, timezone

from extensions import db
from models.bc import BiomedicalConcept, DataElementConcept
from models.governance import GovernanceRecord
from models.specialization import DatasetSpecialization
from services.audit import log_change

logger = logging.getLogger(__name__)


class NotFoundError(ValueError):
    """Raised when a BC id does not exist. Routes translate this to 404."""


# Plain-text fields copied verbatim from a form/dict onto the model.
_BC_TEXT_FIELDS = ("short_name", "definition", "bc_categories", "synonyms", "result_scales", "package_date")


def _get_bc_or_raise(bc_id):
    bc = db.session.get(BiomedicalConcept, bc_id)
    if bc is None:
        raise NotFoundError(f"BC {bc_id!r} not found")
    return bc


def apply_bc_fields(bc, data, is_new):
    """Copy BC fields from a submitted form (or plain dict) onto the model.

    Create keeps raw values (empty strings allowed); update normalizes
    cleared ncit/parent/loinc to None and preserves the existing value
    for any field omitted from the input.
    """
    for field in _BC_TEXT_FIELDS:
        setattr(bc, field, data.get(field, "" if is_new else getattr(bc, field)))
    if is_new:
        bc.ncit_code = data.get("ncit_code", "")
        bc.parent_bc_id = data.get("parent_bc_id") or None
        bc.loinc_code = data.get("loinc_code", "")
        has_loinc = bool((data.get("loinc_code") or "").strip())
        bc.system = data.get("system", "") if has_loinc else ""
        bc.system_name = data.get("system_name", "") if has_loinc else ""
        bc.loinc_metadata = data.get("loinc_metadata", "") or None
        bc.ncit_metadata = data.get("ncit_metadata", "") or None
    else:
        new_ncit_code = (data.get("ncit_code", "") or "").strip() or None
        bc.ncit_code = new_ncit_code
        bc.ncit_metadata = (data.get("ncit_metadata", "") or bc.ncit_metadata) if new_ncit_code else None
        bc.parent_bc_id = (data.get("parent_bc_id", "") or "").strip() or None
        new_loinc_code = (data.get("loinc_code", "") or "").strip() or None
        bc.loinc_code = new_loinc_code
        bc.system = data.get("system", bc.system) if new_loinc_code else ""
        bc.system_name = data.get("system_name", bc.system_name) if new_loinc_code else ""
        bc.loinc_metadata = (data.get("loinc_metadata", "") or bc.loinc_metadata) if new_loinc_code else None
        bc.updated_at = datetime.now(timezone.utc)


def create_bc(data, actor=None):
    """Create a provisional BC from a dict of fields. Returns the BC.

    Raises ValueError when bc_id is missing or already exists.
    """
    bc_id = (data.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("BC ID is required")
    if db.session.get(BiomedicalConcept, bc_id):
        raise ValueError(f"BC {bc_id} already exists")
    bc = BiomedicalConcept(
        bc_id=bc_id,
        status="provisional",
        submitter=data.get("submitter", "unknown"),
    )
    apply_bc_fields(bc, data, is_new=True)
    db.session.add(bc)
    log_change("BiomedicalConcept", bc_id, "created", actor=actor or bc.submitter, after=bc.to_dict())
    db.session.commit()
    return bc


def get_or_create_bc_stub(bc_id, short_name="", actor=None):
    """Return the local BC for bc_id, creating a minimal provisional stub if
    none exists yet (e.g. when a user picks a CDISC-Library-only BC on a
    form that requires a local bc_id to link against)."""
    bc = db.session.get(BiomedicalConcept, bc_id)
    if bc:
        return bc
    return create_bc({"bc_id": bc_id, "short_name": short_name}, actor=actor or "system")


def update_bc(bc_id, data, actor="user"):
    """Update an existing BC from a dict of fields. Returns the BC."""
    bc = _get_bc_or_raise(bc_id)
    before = bc.to_dict()
    apply_bc_fields(bc, data, is_new=False)
    log_change("BiomedicalConcept", bc_id, "updated", actor=actor, before=before, after=bc.to_dict())
    db.session.commit()
    return bc


def save_decs(bc_id, decs):
    """Replace the BC's Data Element Concepts with the given list of dicts.

    Each dict may carry dec_id, ncit_dec_code, dec_label, data_type,
    example_set. An empty list clears all DECs; rows with a blank label are skipped but
    keep their position for default dec_id numbering.
    """
    DataElementConcept.query.filter_by(bc_id=bc_id).delete()
    for i, dec in enumerate(decs or []):
        label = (dec.get("dec_label") or "").strip()
        if not label:
            continue
        db.session.add(
            DataElementConcept(
                dec_id=dec.get("dec_id") or f"{bc_id}.DEC.{i + 1}",
                bc_id=bc_id,
                ncit_dec_code=dec.get("ncit_dec_code", ""),
                dec_label=label,
                data_type=dec.get("data_type") or "string",
                example_set=dec.get("example_set", ""),
                sort_order=i,
            )
        )
    db.session.commit()


def map_ncit_to_bc(bc_id, ncit_code, actor="user"):
    """Attach an NCIt code to a BC, promoting temporary IMPORT_ ids.

    Behavior fix vs the original /ncit/resolve route: this write is now
    recorded in the AuditLog like every other mutation.
    """
    ncit_code = (ncit_code or "").strip()
    if not ncit_code:
        raise ValueError("ncit_code is required")
    bc = _get_bc_or_raise(bc_id)
    before = bc.to_dict()
    bc.ncit_code = ncit_code
    # Promote temporary IMPORT_ IDs to their resolved NCIt code
    if not bc.bc_id or bc.bc_id.startswith("IMPORT_"):
        old_bc_id = bc.bc_id
        if ncit_code != old_bc_id and db.session.get(BiomedicalConcept, ncit_code):
            raise ValueError(f"BC {ncit_code} already exists")
        DataElementConcept.query.filter_by(bc_id=old_bc_id).update({"bc_id": ncit_code})
        DatasetSpecialization.query.filter_by(bc_id=old_bc_id).update({"bc_id": ncit_code})
        GovernanceRecord.query.filter_by(bc_id=old_bc_id).update({"bc_id": ncit_code})
        BiomedicalConcept.query.filter_by(parent_bc_id=old_bc_id).update({"parent_bc_id": ncit_code})
        bc.bc_id = ncit_code
    log_change("BiomedicalConcept", bc.bc_id, "ncit_mapped", actor=actor, before=before, after=bc.to_dict())
    db.session.commit()
    return bc


def submit_bc_for_review(bc_id, actor="user"):
    """Move a BC from provisional to sme_review."""
    bc = _get_bc_or_raise(bc_id)
    before = bc.to_dict()
    bc.status = "sme_review"
    bc.updated_at = datetime.now(timezone.utc)
    log_change("BiomedicalConcept", bc_id, "submitted_for_review", actor=actor, before=before, after=bc.to_dict())
    db.session.commit()
    return bc
