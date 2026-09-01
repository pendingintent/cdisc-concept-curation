"""Tests for routes/notes.py — HTTP-level contract."""

from extensions import db
from models.bc import BiomedicalConcept
from models.specialization import DatasetSpecialization
from services import notes_service


class TestCreateBcNote:
    def test_create_returns_201_with_note(self, client, sample_bc):
        r = client.post(f"/notes/bc/{sample_bc}", json={"text": "hello"})
        assert r.status_code == 201
        data = r.get_json()
        assert data["text"] == "hello"
        assert data["bc_id"] == sample_bc

    def test_missing_bc_returns_404(self, client):
        r = client.post("/notes/bc/NOPE", json={"text": "hello"})
        assert r.status_code == 404

    def test_blank_text_returns_400(self, client, sample_bc):
        r = client.post(f"/notes/bc/{sample_bc}", json={"text": "  "})
        assert r.status_code == 400

    def test_locked_when_published_returns_400(self, client, app, sample_bc):
        with app.app_context():
            bc = db.session.get(BiomedicalConcept, sample_bc)
            bc.status = "published"
            db.session.commit()
        r = client.post(f"/notes/bc/{sample_bc}", json={"text": "hello"})
        assert r.status_code == 400
        assert "Ready to Publish" in r.get_json()["error"]


class TestCreateSpecNote:
    def test_create_returns_201(self, client, sample_spec):
        r = client.post(f"/notes/spec/{sample_spec}", json={"text": "hello"})
        assert r.status_code == 201
        assert r.get_json()["vlm_group_id"] == sample_spec

    def test_missing_spec_returns_404(self, client):
        r = client.post("/notes/spec/NOPE.SDTM", json={"text": "hello"})
        assert r.status_code == 404

    def test_locked_when_published_returns_400(self, client, app, sample_spec):
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, sample_spec)
            spec.status = "published"
            db.session.commit()
        r = client.post(f"/notes/spec/{sample_spec}", json={"text": "hello"})
        assert r.status_code == 400


class TestUpdateNoteRoute:
    def test_update_returns_200(self, client, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "original")
            note_id = note.id
        r = client.post(f"/notes/{note_id}/update", json={"text": "revised"})
        assert r.status_code == 200
        assert r.get_json()["text"] == "revised"

    def test_missing_note_returns_404(self, client):
        r = client.post("/notes/999/update", json={"text": "revised"})
        assert r.status_code == 404


class TestResolveNoteRoute:
    def test_resolve_returns_200(self, client, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            note_id = note.id
        r = client.post(f"/notes/{note_id}/resolve", json={"resolved": True})
        assert r.status_code == 200
        assert r.get_json()["resolved"] is True

    def test_unresolve(self, client, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            note_id = note.id
        client.post(f"/notes/{note_id}/resolve", json={"resolved": True})
        r = client.post(f"/notes/{note_id}/resolve", json={"resolved": False})
        assert r.get_json()["resolved"] is False

    def test_missing_note_returns_404(self, client):
        r = client.post("/notes/999/resolve", json={"resolved": True})
        assert r.status_code == 404


class TestFlagNoteRoute:
    def test_flag_returns_200(self, client, app, sample_bc):
        with app.app_context():
            note = notes_service.create_bc_note(sample_bc, "text")
            note_id = note.id
        r = client.post(f"/notes/{note_id}/flag", json={"flagged": True})
        assert r.status_code == 200
        assert r.get_json()["flagged"] is True

    def test_missing_note_returns_404(self, client):
        r = client.post("/notes/999/flag", json={"flagged": True})
        assert r.status_code == 404


class TestNoDeleteRoute:
    def test_no_delete_endpoint_registered(self, app):
        rules = [str(r) for r in app.url_map.iter_rules() if r.rule.startswith("/notes")]
        assert not any("delete" in r for r in rules)


class TestNotesVisibleOnDetailPages:
    def test_bc_detail_page_renders_notes_panel(self, client, app, sample_bc):
        with app.app_context():
            notes_service.create_bc_note(sample_bc, "a helpful note")
        r = client.get(f"/bc/{sample_bc}")
        assert r.status_code == 200
        assert b"a helpful note" in r.data

    def test_spec_detail_page_renders_notes_panel(self, client, app, sample_spec):
        with app.app_context():
            notes_service.create_spec_note(sample_spec, "a spec note")
        r = client.get(f"/specializations/{sample_spec}")
        assert r.status_code == 200
        assert b"a spec note" in r.data


class TestNotesExcludedFromGovernanceExport:
    def test_governance_export_has_no_notes(self, client, app, sample_bc):
        with app.app_context():
            notes_service.create_bc_note(sample_bc, "should not be exported")
            for _ in range(3):
                pass
        for _ in range(3):
            client.post(f"/governance/advance/{sample_bc}")
        r = client.get("/governance/export")
        assert b"should not be exported" not in r.data

    def test_bc_json_export_has_no_notes_key(self, client, app, sample_bc):
        with app.app_context():
            notes_service.create_bc_note(sample_bc, "should not be exported")
        r = client.get("/bc/export?format=json")
        assert b'"notes"' not in r.data
        assert b"should not be exported" not in r.data
