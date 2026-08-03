"""Shared audit-trail helper.

Every mutation of a curated entity must be recorded in the immutable
AuditLog. Routes (and, later, MCP tools) call log_change() instead of
constructing AuditLog rows inline so the write pattern stays uniform.
"""

import logging

from extensions import db
from models.audit import AuditLog

logger = logging.getLogger(__name__)


def log_change(entity_type, entity_id, action, actor, before=None, after=None):
    """Queue an AuditLog row on the current session.

    The caller owns the commit so the audit row and the change it
    records land in the same transaction. `before`/`after` are plain
    dicts (or None); the model serializes them to JSON.
    """
    db.session.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            before_state=before,
            after_state=after,
        )
    )
