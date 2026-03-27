from extensions import db
from datetime import datetime
import json


class IngestionRecord(db.Model):
    __tablename__ = 'ingestion_records'
    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(64), index=True)
    source_file = db.Column(db.String(255))
    source_sheet = db.Column(db.String(100))
    _mapped = db.Column('mapped', db.Text)
    _confidences = db.Column('confidences', db.Text)
    _errors = db.Column('errors', db.Text)
    _decs = db.Column('decs', db.Text)
    duplicate = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending')  # pending / approved / rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def mapped(self):
        return json.loads(self._mapped) if self._mapped else {}

    @mapped.setter
    def mapped(self, value):
        self._mapped = json.dumps(value)

    @property
    def confidences(self):
        return json.loads(self._confidences) if self._confidences else {}

    @confidences.setter
    def confidences(self, value):
        self._confidences = json.dumps(value)

    @property
    def errors(self):
        return json.loads(self._errors) if self._errors else []

    @errors.setter
    def errors(self, value):
        self._errors = json.dumps(value)

    @property
    def decs(self):
        return json.loads(self._decs) if self._decs else []

    @decs.setter
    def decs(self, value):
        self._decs = json.dumps(value)

    @property
    def avg_confidence(self):
        vals = [v for v in self.confidences.values() if isinstance(v, (int, float))]
        return round(sum(vals) / len(vals) * 100) if vals else 0
