"""Tests for routes/audit.py — log listing and filtering."""
import pytest
from models.audit import AuditLog
from extensions import db


def _add_log(app, entity_type='BiomedicalConcept', entity_id='C001', action='created', actor='alice'):
    with app.app_context():
        log = AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, actor=actor)
        db.session.add(log)
        db.session.commit()


class TestAuditIndex:
    def test_returns_200_empty(self, client):
        r = client.get('/audit/')
        assert r.status_code == 200

    def test_shows_log_entries(self, client, app):
        _add_log(app)
        r = client.get('/audit/')
        assert r.status_code == 200
        assert b'C001' in r.data

    def test_filter_by_entity_type(self, client, app):
        _add_log(app, entity_type='BiomedicalConcept', entity_id='C001')
        _add_log(app, entity_type='GovernanceRecord', entity_id='G001')
        r = client.get('/audit/?entity_type=BiomedicalConcept')
        assert b'C001' in r.data
        assert b'G001' not in r.data

    def test_filter_by_action(self, client, app):
        _add_log(app, entity_id='C001', action='created')
        _add_log(app, entity_id='C002', action='deleted')
        r = client.get('/audit/?action=deleted')
        assert b'C002' in r.data
        assert b'created' not in r.data or b'C001' not in r.data

    def test_filter_by_actor(self, client, app):
        _add_log(app, entity_id='C001', actor='alice')
        _add_log(app, entity_id='C002', actor='bob')
        r = client.get('/audit/?actor=alice')
        assert b'alice' in r.data
        assert b'bob' not in r.data

    def test_pagination_param_accepted(self, client, app):
        _add_log(app)
        r = client.get('/audit/?page=1')
        assert r.status_code == 200
