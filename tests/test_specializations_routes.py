"""Tests for routes/specializations.py."""

from unittest.mock import MagicMock, patch

from extensions import db
from models.audit import AuditLog
from models.bc import DataElementConcept
from models.specialization import DatasetSpecialization

LIBRARY_LINKS = [
    {"href": "/mdr/bc/biomedicalconcepts/C64849", "title": "Hemoglobin A1c"},
]


def _patch_client(**kwargs):
    """Patch the CDISCApiClient used by the specializations blueprint."""
    client = MagicMock()
    client.get_biomedical_concepts.return_value = kwargs.get("bcs", LIBRARY_LINKS)
    client.get_specialization.return_value = kwargs.get("spec", {})
    patcher = patch("routes.specializations.CDISCApiClient", return_value=client)
    return patcher, client


class TestIndex:
    def test_lists_specializations(self, client, app, sample_bc):
        with app.app_context():
            spec = DatasetSpecialization(vlm_group_id="C12345.SDTM", bc_id=sample_bc, domain="SDTM", short_name="Test Spec")
            db.session.add(spec)
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            resp = client.get("/specializations/")
        assert resp.status_code == 200
        assert b"C12345.SDTM" in resp.data

    def test_index_survives_library_error(self, client):
        patcher, _ = _patch_client(bcs=[{"error": "401"}])
        with patcher:
            resp = client.get("/specializations/")
        assert resp.status_code == 200


class TestCreate:
    def test_create_persists_spec(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM1", "bc_id": sample_bc, "domain": "CDASH", "short_name": "Manual Spec"},
            )
        assert resp.status_code == 302
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, "VLM1")
            assert spec is not None
            assert spec.domain == "CDASH"
            assert spec.variables == []

    def test_create_requires_ids(self, client, app):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post("/specializations/", data={"vlm_group_id": "", "bc_id": ""})
        assert resp.status_code == 302
        with app.app_context():
            assert DatasetSpecialization.query.count() == 0

    def test_create_writes_audit_log(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM1", "bc_id": sample_bc, "domain": "SDTM", "short_name": "Manual Spec"},
            )
        with app.app_context():
            log = AuditLog.query.filter_by(entity_type="DatasetSpecialization", entity_id="VLM1", action="created").first()
            assert log is not None
            assert log.after_state["short_name"] == "Manual Spec"


class TestDelete:
    def test_delete_removes_spec(self, client, app, sample_bc):
        with app.app_context():
            db.session.add(DatasetSpecialization(vlm_group_id="VLM1", bc_id=sample_bc, domain="SDTM"))
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post("/specializations/VLM1/delete")
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(DatasetSpecialization, "VLM1") is None

    def test_delete_writes_audit_log(self, client, app, sample_bc):
        with app.app_context():
            db.session.add(DatasetSpecialization(vlm_group_id="VLM1", bc_id=sample_bc, domain="SDTM", short_name="Doomed Spec"))
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            client.post("/specializations/VLM1/delete")
        with app.app_context():
            log = AuditLog.query.filter_by(entity_type="DatasetSpecialization", entity_id="VLM1", action="deleted").first()
            assert log is not None
            assert log.before_state["short_name"] == "Doomed Spec"

    def test_delete_unknown_404(self, client):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post("/specializations/NOPE/delete")
        assert resp.status_code == 404


class TestDetail:
    def test_detail_renders(self, client, app, sample_bc):
        with app.app_context():
            db.session.add(DatasetSpecialization(vlm_group_id="VLM1", bc_id=sample_bc, domain="SDTM"))
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            resp = client.get("/specializations/VLM1")
        assert resp.status_code == 200

    def test_detail_404_for_unknown(self, client):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.get("/specializations/NOPE")
        assert resp.status_code == 404


class TestLibraryDetail:
    def test_renders_library_spec(self, client):
        patcher, _ = _patch_client(spec={"shortName": "HBA1C Spec", "datasetSpecializationId": "HBA1C"})
        with patcher:
            resp = client.get("/specializations/library/mdr/specializations/sdtm/datasetspecializations/HBA1C")
        assert resp.status_code == 200

    def test_error_redirects_to_dashboard(self, client):
        patcher, _ = _patch_client(spec={"error": "404 not found"})
        with patcher:
            resp = client.get("/specializations/library/mdr/specializations/sdtm/datasetspecializations/NOPE")
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "http://localhost/")


class TestGenerate:
    def _add_decs(self, app, bc_id):
        with app.app_context():
            db.session.add_all(
                [
                    DataElementConcept(dec_id=f"{bc_id}.DEC.1", bc_id=bc_id, dec_label="Result", data_type="decimal", required=True, sort_order=0),
                    DataElementConcept(dec_id=f"{bc_id}.DEC.2", bc_id=bc_id, dec_label="Unit", data_type="string", sort_order=1),
                ]
            )
            db.session.commit()

    def test_generate_builds_variables_from_decs(self, client, app, sample_bc):
        self._add_decs(app, sample_bc)
        resp = client.post(f"/specializations/generate/{sample_bc}", data={"domain": "SDTM"})
        assert resp.status_code == 302
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, f"{sample_bc}.SDTM")
            assert spec is not None
            assert [v["name"] for v in spec.variables] == ["Result", "Unit"]
            assert spec.variables[0]["required"] is True

    def test_generate_duplicate_is_rejected(self, client, app, sample_bc):
        self._add_decs(app, sample_bc)
        client.post(f"/specializations/generate/{sample_bc}", data={"domain": "SDTM"})
        resp = client.post(f"/specializations/generate/{sample_bc}", data={"domain": "SDTM"})
        assert resp.status_code == 302
        with app.app_context():
            assert DatasetSpecialization.query.count() == 1

    def test_generate_unknown_bc_404(self, client):
        resp = client.post("/specializations/generate/NOPE", data={"domain": "SDTM"})
        assert resp.status_code == 404

    def test_generate_writes_audit_log(self, client, app, sample_bc):
        self._add_decs(app, sample_bc)
        client.post(f"/specializations/generate/{sample_bc}", data={"domain": "SDTM"})
        with app.app_context():
            log = AuditLog.query.filter_by(entity_type="DatasetSpecialization", entity_id=f"{sample_bc}.SDTM", action="created").first()
            assert log is not None


class TestGenerateFromDec:
    def test_returns_variables_json(self, client, app, sample_bc):
        with app.app_context():
            db.session.add(DataElementConcept(dec_id="D1", bc_id=sample_bc, dec_label="Result", data_type="decimal", sort_order=0))
            db.session.commit()
        resp = client.post("/specializations/generate-from-dec", json={"bc_id": sample_bc})
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["variables"][0]["name"] == "Result"

    def test_missing_bc_id_returns_400(self, client):
        resp = client.post("/specializations/generate-from-dec", json={})
        assert resp.status_code == 400
