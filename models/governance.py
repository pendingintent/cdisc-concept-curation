from extensions import db
from datetime import datetime


class GovernanceRecord(db.Model):
    __tablename__ = 'governance_records'
    id = db.Column(db.Integer, primary_key=True)
    bc_id = db.Column(db.String(50), db.ForeignKey('biomedical_concepts.bc_id'), nullable=False)
    stage = db.Column(db.Integer, default=0)  # 0=Scoping, 1=Development, 2=Draft, 3a=Internal Review, 3b=Public Review, 3c=Publication, 4=Maintenance
    action = db.Column(db.String(100))  # submitted, advanced, rejected, approved, published
    actor = db.Column(db.String(100))
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bc = db.relationship('BiomedicalConcept', backref=db.backref('governance_records', lazy='dynamic'))
