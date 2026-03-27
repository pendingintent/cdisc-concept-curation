from extensions import db
from datetime import datetime
import json


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50))  # BiomedicalConcept, GovernanceRecord, etc.
    entity_id = db.Column(db.String(100))
    action = db.Column(db.String(100))  # created, updated, status_changed, deleted
    actor = db.Column(db.String(100), default='system')
    _before_state = db.Column('before_state', db.Text)
    _after_state = db.Column('after_state', db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def before_state(self):
        return json.loads(self._before_state) if self._before_state else None

    @before_state.setter
    def before_state(self, value):
        self._before_state = json.dumps(value) if value else None

    @property
    def after_state(self):
        return json.loads(self._after_state) if self._after_state else None

    @after_state.setter
    def after_state(self, value):
        self._after_state = json.dumps(value) if value else None
