import json
from datetime import datetime, timezone

from extensions import db


class DatasetSpecialization(db.Model):
    __tablename__ = "dataset_specializations"
    vlm_group_id = db.Column(db.String(100), primary_key=True)
    bc_id = db.Column(db.String(50), db.ForeignKey("biomedical_concepts.bc_id"), nullable=False)
    domain = db.Column(db.String(20))  # SDTM Domain Abbreviation codelist (C66734) submissionValue, e.g. "LB", "VS"
    short_name = db.Column(db.String(255))
    _variables = db.Column("variables", db.Text, default="[]")
    status = db.Column(db.String(50), default="provisional")  # provisional/sme_review/cdisc_approval/published
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def variables(self):
        return json.loads(self._variables) if self._variables else []

    @variables.setter
    def variables(self, value):
        self._variables = json.dumps(value)

    def to_dict(self):
        return {
            "vlm_group_id": self.vlm_group_id,
            "bc_id": self.bc_id,
            "domain": self.domain,
            "short_name": self.short_name,
            "variables": self.variables,
            "status": self.status,
        }
