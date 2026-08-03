"""Tests for db_bootstrap.ensure_db() — the Alembic baseline bootstrap."""

import pytest
from sqlalchemy import inspect, text

from app import create_app
from db_bootstrap import LEGACY_REVISIONS, ensure_db
from extensions import db

EXPECTED_TABLES = {
    "audit_logs",
    "biomedical_concepts",
    "data_element_concepts",
    "dataset_specializations",
    "governance_records",
    "ingestion_records",
}


def _make_app(tmp_path, name="boot.db"):
    class TmpConfig:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path}/{name}"
        SECRET_KEY = "test-secret-key"
        CDISC_API_KEY = ""
        CDISC_API_BASE_URL = "https://api.library.cdisc.org/api/cosmos/v2"
        NCIT_API_BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    return create_app(TmpConfig)


def _tables(app):
    with app.app_context():
        return set(inspect(db.engine).get_table_names())


def _stamped_revision(app):
    with app.app_context():
        return db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()


class TestEnsureDb:
    def test_fresh_db_upgraded_from_baseline(self, tmp_path):
        app = _make_app(tmp_path)
        ensure_db(app)
        assert EXPECTED_TABLES <= _tables(app)
        assert _stamped_revision(app) not in LEGACY_REVISIONS

    def test_legacy_create_all_db_is_stamped(self, tmp_path):
        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
        assert "alembic_version" not in _tables(app)
        ensure_db(app)
        assert "alembic_version" in _tables(app)
        assert _stamped_revision(app) not in LEGACY_REVISIONS

    def test_pre_squash_stamped_db_is_restamped(self, tmp_path):
        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
            db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            db.session.execute(text("INSERT INTO alembic_version VALUES ('c2d4e6f8a0b1')"))
            # Seed a row to prove data survives the restamp
            db.session.execute(text("INSERT INTO biomedical_concepts (bc_id, short_name) VALUES ('C1', 'Kept')"))
            db.session.commit()
        ensure_db(app)
        assert _stamped_revision(app) not in LEGACY_REVISIONS
        with app.app_context():
            assert db.session.execute(text("SELECT count(*) FROM biomedical_concepts")).scalar() == 1

    def test_outdated_schema_raises(self, tmp_path):
        app = _make_app(tmp_path)
        with app.app_context():
            # A biomedical_concepts table missing post-baseline columns
            db.session.execute(text("CREATE TABLE biomedical_concepts (bc_id VARCHAR(50) PRIMARY KEY, short_name VARCHAR(255))"))
            db.session.commit()
        with pytest.raises(RuntimeError, match="flask db stamp head"):
            ensure_db(app)

    def test_idempotent_second_run(self, tmp_path):
        app = _make_app(tmp_path)
        ensure_db(app)
        first = _stamped_revision(app)
        ensure_db(app)  # must be a no-op, not an error
        assert _stamped_revision(app) == first
