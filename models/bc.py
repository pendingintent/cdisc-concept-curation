from extensions import db
from datetime import datetime


class BiomedicalConcept(db.Model):
    __tablename__ = 'biomedical_concepts'
    bc_id = db.Column(db.String(50), primary_key=True)  # NCIt C-code e.g. C49237
    short_name = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text)
    ncit_code = db.Column(db.String(50))
    parent_bc_id = db.Column(db.String(50), db.ForeignKey('biomedical_concepts.bc_id'), nullable=True)
    bc_categories = db.Column(db.String(500))  # semicolon-separated
    synonyms = db.Column(db.Text)
    result_scales = db.Column(db.String(255))  # e.g. "Quantitative; Ordinal"
    system = db.Column(db.String(255))  # e.g. http://loinc.org/
    system_name = db.Column(db.String(100))  # e.g. LOINC
    code = db.Column(db.String(50))  # code in external system
    package_date = db.Column(db.String(20))
    status = db.Column(db.String(50), default='provisional')  # provisional/sme_review/cdisc_approval/published
    submitter = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    history_of_change = db.Column(db.Text)
    source = db.Column(db.String(50), default='local')  # 'local' or 'cdisc_api'

    children = db.relationship('BiomedicalConcept', backref=db.backref('parent', remote_side='BiomedicalConcept.bc_id'), lazy='dynamic')
    decs = db.relationship('DataElementConcept', backref='bc', lazy='dynamic', cascade='all, delete-orphan')
    specializations = db.relationship('DatasetSpecialization', backref='bc', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'bc_id': self.bc_id,
            'short_name': self.short_name,
            'definition': self.definition,
            'ncit_code': self.ncit_code,
            'parent_bc_id': self.parent_bc_id,
            'bc_categories': self.bc_categories,
            'synonyms': self.synonyms,
            'result_scales': self.result_scales,
            'system': self.system,
            'system_name': self.system_name,
            'code': self.code,
            'package_date': self.package_date,
            'status': self.status,
            'submitter': self.submitter,
        }


class DataElementConcept(db.Model):
    __tablename__ = 'data_element_concepts'
    id = db.Column(db.Integer, primary_key=True)
    dec_id = db.Column(db.String(50), nullable=False)
    bc_id = db.Column(db.String(50), db.ForeignKey('biomedical_concepts.bc_id'), nullable=False)
    ncit_dec_code = db.Column(db.String(50))
    dec_label = db.Column(db.String(255))
    data_type = db.Column(db.String(50))  # string, decimal, boolean, datetime
    example_set = db.Column(db.Text)
    required = db.Column(db.Boolean, default=False)
    generic_dec = db.Column(db.Boolean, default=False)
    template_type = db.Column(db.String(100))  # Default, Vital Signs Tests, etc.
    sort_order = db.Column(db.Integer, default=0)
