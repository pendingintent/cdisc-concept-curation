from datetime import datetime, timezone

from extensions import db


class Note(db.Model):
    """A free-text comment attached to a BC or a Specialization.

    Never exported in the governance spreadsheet/BC export — visible only in
    the app and in the audit trail (see services/notes_service.py).
    """

    __tablename__ = "notes"
    __table_args__ = (
        db.CheckConstraint(
            "(bc_id IS NOT NULL) + (vlm_group_id IS NOT NULL) = 1",
            name="ck_notes_one_entity",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    bc_id = db.Column(db.String(50), db.ForeignKey("biomedical_concepts.bc_id"), nullable=True)
    vlm_group_id = db.Column(db.String(100), db.ForeignKey("dataset_specializations.vlm_group_id"), nullable=True)
    text = db.Column(db.Text, nullable=False)
    flagged = db.Column(db.Boolean, default=False, nullable=False)
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.String(100), nullable=True)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    bc = db.relationship("BiomedicalConcept", backref=db.backref("notes", lazy="dynamic"))
    specialization = db.relationship("DatasetSpecialization", backref=db.backref("notes", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "bc_id": self.bc_id,
            "vlm_group_id": self.vlm_group_id,
            "text": self.text,
            "flagged": self.flagged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
