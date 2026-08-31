"""Tests for routes/specializations.py."""

from unittest.mock import MagicMock, patch

from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept, DataElementConcept
from models.specialization import DatasetSpecialization

LIBRARY_LINKS = [
    {"href": "/mdr/bc/biomedicalconcepts/C64849", "title": "Hemoglobin A1c"},
]

DOMAIN_CODES = [
    {"code": "AE", "label": "Adverse Event Domain"},
    {"code": "LB", "label": "Laboratory Test Results Domain"},
    {"code": "VS", "label": "Vital Signs Domain"},
]


def _patch_client(**kwargs):
    """Patch the CDISCApiClient used by the specializations blueprint."""
    client = MagicMock()
    client.get_biomedical_concepts.return_value = kwargs.get("bcs", LIBRARY_LINKS)
    client.get_specialization.return_value = kwargs.get("spec", {})
    client.get_sdtm_domain_codes.return_value = kwargs.get("domains", DOMAIN_CODES)
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

    def test_create_defaults_to_provisional_status(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM2", "bc_id": sample_bc, "domain": "CDASH", "short_name": "Manual Spec"},
            )
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, "VLM2")
            assert spec.status == "provisional"

    def test_create_requires_ids(self, client, app):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post("/specializations/", data={"vlm_group_id": "", "bc_id": ""})
        assert resp.status_code == 302
        with app.app_context():
            assert DatasetSpecialization.query.count() == 0

    def test_create_requires_domain(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM1", "bc_id": sample_bc, "domain": ""},
            )
        assert resp.status_code == 302
        with app.app_context():
            assert DatasetSpecialization.query.count() == 0

    def test_real_sdtm_domain_code_persists(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM1", "bc_id": sample_bc, "domain": "VS", "short_name": "Vitals Spec"},
            )
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, "VLM1")
            assert spec.domain == "VS"

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

    def test_create_persists_variable_rows_from_form(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post(
                "/specializations/",
                data={
                    "vlm_group_id": "VLM1",
                    "bc_id": sample_bc,
                    "domain": "SDTM",
                    "short_name": "Manual Spec",
                    "variables[0][sdtm_variable]": "RESULT",
                    "variables[0][data_type]": "decimal",
                    "variables[0][mandatory_variable]": "Y",
                },
            )
        assert resp.status_code == 302
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, "VLM1")
            assert len(spec.variables) == 1
            assert spec.variables[0]["sdtm_variable"] == "RESULT"
            assert spec.variables[0]["data_type"] == "decimal"
            assert spec.variables[0]["mandatory_variable"] == "Y"


class TestEditUpsert:
    def test_posting_existing_vlm_group_id_updates_instead_of_duplicating(self, client, app, sample_bc):
        with app.app_context():
            db.session.add(DatasetSpecialization(vlm_group_id="VLM1", bc_id=sample_bc, domain="SDTM", short_name="Original"))
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post(
                "/specializations/",
                data={
                    "vlm_group_id": "VLM1",
                    "bc_id": sample_bc,
                    "domain": "CDASH",
                    "short_name": "Renamed",
                    "variables[0][sdtm_variable]": "RESULT",
                    "variables[0][data_type]": "decimal",
                },
            )
        assert resp.status_code == 302
        with app.app_context():
            assert DatasetSpecialization.query.count() == 1
            spec = db.session.get(DatasetSpecialization, "VLM1")
            assert spec.domain == "CDASH"
            assert spec.short_name == "Renamed"
            assert len(spec.variables) == 1
            assert spec.variables[0]["sdtm_variable"] == "RESULT"
            assert spec.variables[0]["data_type"] == "decimal"

    def test_edit_writes_updated_audit_log(self, client, app, sample_bc):
        with app.app_context():
            db.session.add(DatasetSpecialization(vlm_group_id="VLM1", bc_id=sample_bc, domain="SDTM", short_name="Original"))
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM1", "bc_id": sample_bc, "domain": "SDTM", "short_name": "Renamed"},
            )
        with app.app_context():
            log = AuditLog.query.filter_by(entity_type="DatasetSpecialization", entity_id="VLM1", action="updated").first()
            assert log is not None
            assert log.before_state["short_name"] == "Original"
            assert log.after_state["short_name"] == "Renamed"


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

    def test_detail_expands_the_edit_form_panel(self, client, app, sample_bc):
        """The Edit link on the list page routes here; the pre-filled form
        must actually be visible, not left inside a collapsed <div>."""
        with app.app_context():
            db.session.add(DatasetSpecialization(vlm_group_id="VLM1", bc_id=sample_bc, domain="SDTM"))
            db.session.commit()
        patcher, _ = _patch_client()
        with patcher:
            resp = client.get("/specializations/VLM1")
        body = resp.data.decode()
        assert 'id="specialization-form-panel"' in body
        assert 'class="collapse mb-3 show"' in body

    def test_index_form_panel_collapsed_by_default(self, client):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.get("/specializations/")
        body = resp.data.decode()
        assert 'class="collapse mb-3 "' in body


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

    def test_generate_requires_domain(self, client, app, sample_bc):
        self._add_decs(app, sample_bc)
        resp = client.post(f"/specializations/generate/{sample_bc}", data={"domain": ""})
        assert resp.status_code == 302
        with app.app_context():
            assert DatasetSpecialization.query.count() == 0

    def test_generate_builds_variables_from_decs(self, client, app, sample_bc):
        self._add_decs(app, sample_bc)
        resp = client.post(f"/specializations/generate/{sample_bc}", data={"domain": "SDTM"})
        assert resp.status_code == 302
        with app.app_context():
            spec = db.session.get(DatasetSpecialization, f"{sample_bc}.SDTM")
            assert spec is not None
            assert [v["sdtm_variable"] for v in spec.variables] == ["Result", "Unit"]
            assert spec.variables[0]["dec_id"] == f"{sample_bc}.DEC.1"

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
        assert payload["variables"][0]["sdtm_variable"] == "Result"
        assert payload["variables"][0]["dec_id"] == "D1"

    def test_missing_bc_id_returns_400(self, client):
        resp = client.post("/specializations/generate-from-dec", json={})
        assert resp.status_code == 400


class TestCreateWithLibraryOnlyBc:
    def test_selecting_library_only_bc_creates_local_stub(self, client, app):
        """Picking a 'CDISC Library' option that has no local BC row yet
        must not create an orphaned FK reference — it should create a
        minimal local BC stub so the specialization links correctly."""
        patcher, _ = _patch_client(bcs=[{"href": "/mdr/bc/biomedicalconcepts/C64849", "title": "Hemoglobin A1c"}])
        with patcher:
            resp = client.post(
                "/specializations/",
                data={"vlm_group_id": "C64849.SDTM", "bc_id": "C64849", "domain": "SDTM", "short_name": "HBA1C Spec"},
            )
        assert resp.status_code == 302
        with app.app_context():
            bc = db.session.get(BiomedicalConcept, "C64849")
            assert bc is not None
            assert bc.status == "provisional"
            spec = db.session.get(DatasetSpecialization, "C64849.SDTM")
            assert spec is not None
            assert spec.bc_id == "C64849"
            assert spec.bc is not None
            assert spec.bc.bc_id == "C64849"

    def test_existing_local_bc_is_not_modified(self, client, app, sample_bc):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.post(
                "/specializations/",
                data={"vlm_group_id": "VLM1", "bc_id": sample_bc, "domain": "SDTM", "short_name": "Manual Spec"},
            )
        assert resp.status_code == 302
        with app.app_context():
            bc = db.session.get(BiomedicalConcept, sample_bc)
            assert bc.short_name == "Test Concept"


class TestBcOptionsSorting:
    def test_library_bcs_sorted_alphabetically(self, client):
        unsorted_links = [
            {"href": "/mdr/bc/biomedicalconcepts/C2", "title": "Zebra Concept"},
            {"href": "/mdr/bc/biomedicalconcepts/C1", "title": "Alpha Concept"},
        ]
        patcher, _ = _patch_client(bcs=unsorted_links)
        with patcher:
            resp = client.get("/specializations/")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert body.index("Alpha Concept") < body.index("Zebra Concept")


class TestDomainSelector:
    def test_domain_options_rendered_from_sdtm_codelist(self, client):
        patcher, _ = _patch_client()
        with patcher:
            resp = client.get("/specializations/")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Adverse Event Domain" in body
        assert "Vital Signs Domain" in body

    def test_error_entries_excluded_from_options(self, client):
        patcher, _ = _patch_client(domains=[{"error": "unreachable"}])
        with patcher:
            resp = client.get("/specializations/")
        assert resp.status_code == 200
