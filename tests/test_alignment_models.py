"""Tests for models.alignment.AlignmentJob."""

from datetime import datetime, timezone

from extensions import db
from models.alignment import AlignmentJob


class TestAlignmentJobDefaults:
    def test_defaults_on_minimal_row(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()

            assert job.id is not None
            assert job.status == "pending"
            assert job.error_message is None
            assert job.populate_batches_done is None
            assert job.populate_batches_total is None
            assert job.augment_rows_total is None
            assert job.augment_cdisc_hits is None
            assert job.xlsx_path is None
            assert job.json_path is None
            assert job.created_by == "user"
            assert isinstance(job.created_at, datetime)
            assert isinstance(job.updated_at, datetime)
            assert job.started_at is None
            assert job.completed_at is None

    def test_updated_at_changes_on_update(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()
            first_updated = job.updated_at

            job.status = "running_populate"
            db.session.commit()

            assert job.updated_at >= first_updated


class TestAlignmentJobToDict:
    def test_to_dict_shape(self, app):
        with app.app_context():
            job = AlignmentJob(
                status="completed",
                populate_batches_done=424,
                populate_batches_total=424,
                augment_rows_total=212345,
                augment_cdisc_hits=1345,
                xlsx_path="/tmp/report.xlsx",
                json_path="/tmp/report.json",
                completed_at=datetime.now(timezone.utc),
            )
            db.session.add(job)
            db.session.commit()

            d = job.to_dict()
            assert d["id"] == job.id
            assert d["status"] == "completed"
            assert d["populate_batches_done"] == 424
            assert d["populate_batches_total"] == 424
            assert d["augment_rows_total"] == 212345
            assert d["augment_cdisc_hits"] == 1345
            assert d["xlsx_path"] == "/tmp/report.xlsx"
            assert d["json_path"] == "/tmp/report.json"
            assert d["error_message"] is None
            # datetimes are ISO strings, not datetime objects
            assert isinstance(d["created_at"], str)
            assert isinstance(d["updated_at"], str)
            assert isinstance(d["completed_at"], str)
            assert d["started_at"] is None

    def test_to_dict_null_datetimes_are_none(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()

            d = job.to_dict()
            assert d["started_at"] is None
            assert d["completed_at"] is None
