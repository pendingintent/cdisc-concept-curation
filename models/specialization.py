from extensions import db
import json


class DatasetSpecialization(db.Model):
    __tablename__ = 'dataset_specializations'
    vlm_group_id = db.Column(db.String(100), primary_key=True)
    bc_id = db.Column(db.String(50), db.ForeignKey('biomedical_concepts.bc_id'), nullable=False)
    domain = db.Column(db.String(20))  # SDTM or CDASH
    short_name = db.Column(db.String(255))
    _variables = db.Column('variables', db.Text, default='[]')
    created_at = db.Column(db.DateTime)

    @property
    def variables(self):
        return json.loads(self._variables) if self._variables else []

    @variables.setter
    def variables(self, value):
        self._variables = json.dumps(value)
