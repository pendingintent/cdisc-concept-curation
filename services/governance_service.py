"""Governance stage transitions shared by routes and the MCP server."""

import logging
from datetime import datetime, timezone

from extensions import db
from models.governance import GovernanceRecord
from services.audit import log_change
from services.bc_service import _get_bc_or_raise

logger = logging.getLogger(__name__)

STATUS_ORDER = ["provisional", "sme_review", "cdisc_approval", "published"]


def advance_governance(bc_id, actor="user", comment=""):
    """Advance a BC one stage along STATUS_ORDER.

    Returns {"bc_id", "short_name", "status", "advanced"}; advanced is
    False when the BC is already published (no records written).
    """
    bc = _get_bc_or_raise(bc_id)
    before_status = bc.status
    current_idx = STATUS_ORDER.index(bc.status) if bc.status in STATUS_ORDER else 0
    if current_idx >= len(STATUS_ORDER) - 1:
        return {"bc_id": bc_id, "short_name": bc.short_name, "status": bc.status, "advanced": False}
    bc.status = STATUS_ORDER[current_idx + 1]
    bc.updated_at = datetime.now(timezone.utc)
    db.session.add(
        GovernanceRecord(
            bc_id=bc_id,
            stage=current_idx + 1,
            action="advanced",
            actor=actor,
            comment=comment or "",
        )
    )
    log_change("BiomedicalConcept", bc_id, "status_changed", actor=actor, before={"status": before_status}, after={"status": bc.status})
    db.session.commit()
    return {"bc_id": bc_id, "short_name": bc.short_name, "status": bc.status, "advanced": True}


def reject_bc(bc_id, actor="user", comment=""):
    """Reject a BC back to provisional (stage 0)."""
    bc = _get_bc_or_raise(bc_id)
    before_status = bc.status
    bc.status = "provisional"
    bc.updated_at = datetime.now(timezone.utc)
    db.session.add(
        GovernanceRecord(
            bc_id=bc_id,
            stage=0,
            action="rejected",
            actor=actor,
            comment=comment or "",
        )
    )
    log_change("BiomedicalConcept", bc_id, "rejected", actor=actor, before={"status": before_status}, after={"status": "provisional"})
    db.session.commit()
    return {"bc_id": bc_id, "short_name": bc.short_name, "status": "provisional", "advanced": False}
