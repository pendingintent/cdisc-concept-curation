"""Governance stage transitions shared by routes and the MCP server."""

import logging
from datetime import datetime, timezone

from extensions import db
from models.governance import GovernanceRecord
from models.specialization import DatasetSpecialization
from services.audit import log_change
from services.bc_service import NotFoundError, _get_bc_or_raise

logger = logging.getLogger(__name__)

STATUS_ORDER = ["provisional", "sme_review", "cdisc_approval", "published"]


def _get_spec_or_raise(vlm_group_id):
    spec = db.session.get(DatasetSpecialization, vlm_group_id)
    if spec is None:
        raise NotFoundError(f"Specialization {vlm_group_id!r} not found")
    return spec


def _advance(entity, id_field, id_value, actor, comment):
    """Advance entity (a BC or DatasetSpecialization) one stage along STATUS_ORDER.

    Writes a GovernanceRecord (bc_id= or vlm_group_id= based on id_field) and
    an audit log entry. Returns {id_field, "short_name", "status", "advanced"};
    advanced is False when the entity is already published (no records written).
    """
    before_status = entity.status
    current_idx = STATUS_ORDER.index(entity.status) if entity.status in STATUS_ORDER else 0
    if current_idx >= len(STATUS_ORDER) - 1:
        return {id_field: id_value, "short_name": entity.short_name, "status": entity.status, "advanced": False}
    entity.status = STATUS_ORDER[current_idx + 1]
    entity.updated_at = datetime.now(timezone.utc)
    db.session.add(
        GovernanceRecord(
            **{id_field: id_value},
            stage=current_idx + 1,
            action="advanced",
            actor=actor,
            comment=comment or "",
        )
    )
    log_change(entity.__class__.__name__, id_value, "status_changed", actor=actor, before={"status": before_status}, after={"status": entity.status})
    db.session.commit()
    return {id_field: id_value, "short_name": entity.short_name, "status": entity.status, "advanced": True}


def _reject(entity, id_field, id_value, actor, comment):
    """Reject entity (a BC or DatasetSpecialization) back to provisional (stage 0)."""
    before_status = entity.status
    entity.status = "provisional"
    entity.updated_at = datetime.now(timezone.utc)
    db.session.add(
        GovernanceRecord(
            **{id_field: id_value},
            stage=0,
            action="rejected",
            actor=actor,
            comment=comment or "",
        )
    )
    log_change(entity.__class__.__name__, id_value, "rejected", actor=actor, before={"status": before_status}, after={"status": "provisional"})
    db.session.commit()
    return {id_field: id_value, "short_name": entity.short_name, "status": "provisional", "advanced": False}


def advance_governance(bc_id, actor="user", comment=""):
    """Advance a BC one stage along STATUS_ORDER."""
    bc = _get_bc_or_raise(bc_id)
    return _advance(bc, "bc_id", bc_id, actor, comment)


def reject_bc(bc_id, actor="user", comment=""):
    """Reject a BC back to provisional (stage 0)."""
    bc = _get_bc_or_raise(bc_id)
    return _reject(bc, "bc_id", bc_id, actor, comment)


def advance_specialization_governance(vlm_group_id, actor="user", comment=""):
    """Advance a DatasetSpecialization one stage along STATUS_ORDER."""
    spec = _get_spec_or_raise(vlm_group_id)
    return _advance(spec, "vlm_group_id", vlm_group_id, actor, comment)


def reject_specialization(vlm_group_id, actor="user", comment=""):
    """Reject a DatasetSpecialization back to provisional (stage 0)."""
    spec = _get_spec_or_raise(vlm_group_id)
    return _reject(spec, "vlm_group_id", vlm_group_id, actor, comment)
