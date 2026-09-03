from datetime import datetime, timezone

from extensions import db


class AlignmentJob(db.Model):
    """Tracks one background run of the cdisc-bc-ncit-alignment submodule's
    two-stage pipeline (populate_complete_list, then augment_cdisc).

    See services/alignment_runner.py for the pipeline that populates these
    fields from a separate thread.
    """

    __tablename__ = "alignment_jobs"

    id = db.Column(db.Integer, primary_key=True)
    # pending / running_populate / running_augment / generating_json / completed / failed
    status = db.Column(db.String(20), default="pending", nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    # Stage 1 (populate_complete_list) progress
    populate_batches_done = db.Column(db.Integer, nullable=True)
    populate_batches_total = db.Column(db.Integer, nullable=True)

    # Stage 2 (augment_cdisc) results
    augment_rows_total = db.Column(db.Integer, nullable=True)
    augment_cdisc_hits = db.Column(db.Integer, nullable=True)

    # Output file locations (absolute paths, server-generated only)
    xlsx_path = db.Column(db.String(500), nullable=True)
    json_path = db.Column(db.String(500), nullable=True)

    created_by = db.Column(db.String(100), default="user")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "error_message": self.error_message,
            "populate_batches_done": self.populate_batches_done,
            "populate_batches_total": self.populate_batches_total,
            "augment_rows_total": self.augment_rows_total,
            "augment_cdisc_hits": self.augment_cdisc_hits,
            "xlsx_path": self.xlsx_path,
            "json_path": self.json_path,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
