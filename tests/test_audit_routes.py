"""Tests for routes/audit.py — log listing and filtering."""

import csv
import io
import json

from extensions import db
from models.audit import AuditLog


def _add_log(app, entity_type="BiomedicalConcept", entity_id="C001", action="created", actor="alice"):
    with app.app_context():
        log = AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, actor=actor)
        db.session.add(log)
        db.session.commit()


class TestAuditIndex:
    def test_returns_200_empty(self, client):
        r = client.get("/audit/")
        assert r.status_code == 200

    def test_shows_log_entries(self, client, app):
        _add_log(app)
        r = client.get("/audit/")
        assert r.status_code == 200
        assert b"C001" in r.data

    def test_filter_by_entity_type(self, client, app):
        _add_log(app, entity_type="BiomedicalConcept", entity_id="C001")
        _add_log(app, entity_type="GovernanceRecord", entity_id="G001")
        r = client.get("/audit/?entity_type=BiomedicalConcept")
        assert b"C001" in r.data
        assert b"G001" not in r.data

    def test_filter_by_action(self, client, app):
        _add_log(app, entity_id="C001", action="created")
        _add_log(app, entity_id="C002", action="deleted")
        r = client.get("/audit/?action=deleted")
        assert b"C002" in r.data
        assert b"created" not in r.data or b"C001" not in r.data

    def test_filter_by_actor(self, client, app):
        _add_log(app, entity_id="C001", actor="alice")
        _add_log(app, entity_id="C002", actor="bob")
        r = client.get("/audit/?actor=alice")
        assert b"alice" in r.data
        assert b"bob" not in r.data

    def test_pagination_param_accepted(self, client, app):
        _add_log(app)
        r = client.get("/audit/?page=1")
        assert r.status_code == 200


class TestAuditExportCSV:
    def test_returns_csv_attachment(self, client, app):
        _add_log(app, entity_id="C001", action="created", actor="alice")
        r = client.get("/audit/?export=csv")
        assert r.status_code == 200
        assert r.mimetype == "text/csv"
        assert "attachment" in r.headers["Content-Disposition"]
        assert "audit_log.csv" in r.headers["Content-Disposition"]

    def test_csv_contains_rows(self, client, app):
        _add_log(app, entity_id="C001", action="created", actor="alice")
        _add_log(app, entity_id="C002", action="deleted", actor="bob")
        r = client.get("/audit/?export=csv")
        rows = list(csv.reader(io.StringIO(r.get_data(as_text=True))))
        header, *data_rows = rows
        assert "entity_id" in header
        entity_ids = [row[header.index("entity_id")] for row in data_rows]
        assert "C001" in entity_ids
        assert "C002" in entity_ids

    def test_csv_respects_filters(self, client, app):
        _add_log(app, entity_type="BiomedicalConcept", entity_id="C001")
        _add_log(app, entity_type="GovernanceRecord", entity_id="G001")
        r = client.get("/audit/?export=csv&entity_type=BiomedicalConcept")
        text = r.get_data(as_text=True)
        assert "C001" in text
        assert "G001" not in text

    def test_csv_exports_beyond_one_page(self, client, app):
        for i in range(60):
            _add_log(app, entity_id=f"C{i:03d}")
        r = client.get("/audit/?export=csv")
        rows = list(csv.reader(io.StringIO(r.get_data(as_text=True))))
        assert len(rows) - 1 == 60


class TestAuditExportJSON:
    def test_returns_json_attachment(self, client, app):
        _add_log(app, entity_id="C001")
        r = client.get("/audit/?export=json")
        assert r.status_code == 200
        assert r.mimetype == "application/json"
        assert "attachment" in r.headers["Content-Disposition"]
        assert "audit_log.json" in r.headers["Content-Disposition"]

    def test_json_contains_records(self, client, app):
        _add_log(app, entity_id="C001", action="created", actor="alice")
        r = client.get("/audit/?export=json")
        data = json.loads(r.get_data(as_text=True))
        assert isinstance(data, list)
        assert any(rec["entity_id"] == "C001" and rec["actor"] == "alice" for rec in data)

    def test_json_respects_filters(self, client, app):
        _add_log(app, actor="alice", entity_id="C001")
        _add_log(app, actor="bob", entity_id="C002")
        r = client.get("/audit/?export=json&actor=alice")
        data = json.loads(r.get_data(as_text=True))
        assert {rec["entity_id"] for rec in data} == {"C001"}
