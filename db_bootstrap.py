"""Database bootstrap — Alembic is the single source of truth.

Historically the schema was built by db.create_all() at import time while
an Alembic chain existed in parallel with no baseline revision. The chain
was squashed to one baseline on 2026-07-08; ensure_db() migrates any
database state that predates the squash.

Tests are unaffected: tests/conftest.py builds its in-memory schema with
create_all() directly.
"""

import logging

from flask_migrate import stamp, upgrade
from sqlalchemy import inspect, text

from extensions import db

logger = logging.getLogger(__name__)

# Revision ids from the pre-squash chain. A database stamped at the old
# head (or built by create_all with all current columns) has a schema
# identical to the new baseline and is restamped rather than migrated.
LEGACY_REVISIONS = {"f27a606163b0", "b9ee22a174fe", "a1c3e5f7b9d2", "c2d4e6f8a0b1"}

# Columns added over the life of the legacy chain; all present == the
# schema matches the new baseline.
_CURRENT_SCHEMA_COLUMNS = {"loinc_metadata", "ncit_metadata", "loinc_code", "code"}


def _schema_is_current(inspector):
    cols = {c["name"] for c in inspector.get_columns("biomedical_concepts")}
    return _CURRENT_SCHEMA_COLUMNS <= cols


def ensure_db(app):
    """Bring the configured database to the current migration head.

    Handles three states:
    - fresh database          -> upgrade() builds the schema from the baseline
    - legacy create_all() DB  -> stamped at head (schema verified first)
    - stamped pre-squash DB   -> restamped at head (schema verified first)

    Raises RuntimeError for a legacy database whose schema is missing
    current columns — recreate it or bring it to the old head manually,
    then run `flask db stamp head`.
    """
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        if "biomedical_concepts" in tables:
            if not _schema_is_current(inspector):
                raise RuntimeError(
                    "Database schema predates the squashed Alembic baseline "
                    "and cannot be auto-migrated. Recreate the database or "
                    "bring it to the pre-squash head manually, then run "
                    "'flask db stamp head'."
                )
            if "alembic_version" not in tables:
                logger.info("Legacy create_all() database detected; stamping at baseline head")
                stamp()
            else:
                current = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if current in LEGACY_REVISIONS:
                    logger.info("Database stamped at pre-squash revision %s; restamping at head", current)
                    db.session.execute(text("DELETE FROM alembic_version"))
                    db.session.commit()
                    stamp()

        upgrade()
