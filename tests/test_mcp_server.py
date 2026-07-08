"""Tests for the MCP server (mcp_server/server.py).

Calls _dispatch directly (no stdio transport) with the shared in-memory
test app injected, mirroring the soa-workbench test pattern.
"""

from unittest.mock import patch

import pytest

import mcp_server.server as mcp_srv
from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept, DataElementConcept
from models.governance import GovernanceRecord
from models.ingestion import IngestionRecord
from models.specialization import DatasetSpecialization


@pytest.fixture(autouse=True)
def inject_test_app(app):
    """Point the MCP server at the test app instead of building its own."""
    mcp_srv._app = app
    yield
    mcp_srv._app = None


def _dispatch(name, args=None):
    return mcp_srv._dispatch(name, args or {})


class TestDispatch:
    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            _dispatch("nope")

    def test_all_declared_tools_are_dispatchable(self):
        expected = {
            "list_bcs",
            "get_bc",
            "search_ncit",
            "get_ncit_concept",
            "search_loinc",
            "search_cdisc_library",
            "get_library_bc",
            "list_review_queue",
            "create_bc",
            "update_bc",
            "map_ncit_to_bc",
            "submit_bc_for_review",
            "advance_governance",
            "reject_bc",
        }
        assert {tool.name for tool in mcp_srv._TOOLS} == expected


class TestListBcs:
    def test_empty_db(self):
        result = _dispatch("list_bcs")
        assert result == {"items": [], "total": 0, "page": 1, "per_page": 25, "pages": 0}

    def test_lists_and_filters(self, app, sample_bc):
        with app.app_context():
            db.session.add(BiomedicalConcept(bc_id="C99999", short_name="Glucose Measurement", status="published", submitter="tester"))
            db.session.commit()

        result = _dispatch("list_bcs")
        assert result["total"] == 2

        by_q = _dispatch("list_bcs", {"q": "glucose"})
        assert by_q["total"] == 1
        assert by_q["items"][0]["bc_id"] == "C99999"

        by_status = _dispatch("list_bcs", {"status": "provisional"})
        assert by_status["total"] == 1
        assert by_status["items"][0]["bc_id"] == sample_bc

    def test_pagination(self, app):
        with app.app_context():
            for i in range(5):
                db.session.add(BiomedicalConcept(bc_id=f"C{i:05d}", short_name=f"Concept {i}", status="provisional"))
            db.session.commit()
        page2 = _dispatch("list_bcs", {"per_page": 2, "page": 2})
        assert page2["total"] == 5
        assert len(page2["items"]) == 2
        assert page2["pages"] == 3


class TestGetBc:
    def test_requires_bc_id(self):
        with pytest.raises(ValueError, match="bc_id is required"):
            _dispatch("get_bc")

    def test_missing_bc_raises(self):
        with pytest.raises(ValueError, match="not found"):
            _dispatch("get_bc", {"bc_id": "NOPE"})

    def test_full_detail(self, app, sample_bc):
        with app.app_context():
            db.session.add(DataElementConcept(dec_id="D1", bc_id=sample_bc, dec_label="Result", data_type="decimal", sort_order=0))
            db.session.add(DatasetSpecialization(vlm_group_id=f"{sample_bc}.SDTM", bc_id=sample_bc, domain="SDTM", short_name="Spec"))
            db.session.add(GovernanceRecord(bc_id=sample_bc, stage=1, action="advanced", actor="tester", comment="ok"))
            db.session.commit()

        result = _dispatch("get_bc", {"bc_id": sample_bc})
        assert result["bc_id"] == sample_bc
        assert result["decs"][0]["dec_label"] == "Result"
        assert result["specializations"][0]["vlm_group_id"] == f"{sample_bc}.SDTM"
        assert result["governance_records"][0]["action"] == "advanced"


class TestExternalApiTools:
    def test_search_ncit_requires_term(self):
        with pytest.raises(ValueError, match="term is required"):
            _dispatch("search_ncit")

    def test_search_ncit(self):
        with patch("services.ncit_api.NCItApiClient.search_concept") as mock_search:
            mock_search.return_value = [{"code": "C64849", "name": "HbA1c"}]
            result = _dispatch("search_ncit", {"term": "hba1c", "size": 5})
        assert result[0]["code"] == "C64849"
        mock_search.assert_called_once_with("hba1c", size=5)

    def test_get_ncit_concept(self):
        with patch("services.ncit_api.NCItApiClient.get_concept") as mock_get:
            mock_get.return_value = {"code": "C64849", "name": "HbA1c"}
            result = _dispatch("get_ncit_concept", {"ncit_code": "C64849"})
        assert result["code"] == "C64849"

    def test_search_loinc(self):
        with patch("services.loinc_api.LoincApiClient.search") as mock_search:
            mock_search.return_value = [{"LOINC_NUM": "4548-4"}]
            result = _dispatch("search_loinc", {"term": "4548-4"})
        assert result[0]["LOINC_NUM"] == "4548-4"

    def test_search_cdisc_library_filters_by_title(self):
        links = [
            {"href": "/mdr/bc/biomedicalconcepts/C64849", "title": "Hemoglobin A1c"},
            {"href": "/mdr/bc/biomedicalconcepts/C25298", "title": "Systolic BP"},
        ]
        with patch("services.cdisc_api.CDISCApiClient.get_biomedical_concepts", return_value=links):
            result = _dispatch("search_cdisc_library", {"q": "hemoglobin"})
        assert len(result) == 1
        assert result[0]["title"] == "Hemoglobin A1c"

    def test_search_cdisc_library_passes_error_through(self):
        with patch("services.cdisc_api.CDISCApiClient.get_biomedical_concepts", return_value=[{"error": "401"}]):
            result = _dispatch("search_cdisc_library", {"q": "x"})
        assert result == [{"error": "401"}]

    def test_get_library_bc(self):
        with patch("services.cdisc_api.CDISCApiClient.get_bc", return_value={"conceptId": "C64849"}):
            result = _dispatch("get_library_bc", {"concept_id": "C64849"})
        assert result["conceptId"] == "C64849"


def _audit_rows(app, action):
    with app.app_context():
        return AuditLog.query.filter_by(action=action).all()


class TestCreateBc:
    def test_creates_with_decs_and_audit(self, app):
        result = _dispatch(
            "create_bc",
            {
                "bc_id": "C64849",
                "short_name": "Hemoglobin A1c Measurement",
                "definition": "HbA1c quantitative measurement",
                "ncit_code": "C64849",
                "decs": [{"dec_label": "Result Value", "data_type": "decimal"}],
            },
        )
        assert result["bc_id"] == "C64849"
        assert result["status"] == "provisional"
        assert result["decs"][0]["dec_label"] == "Result Value"
        rows = _audit_rows(app, "created")
        assert len(rows) == 1
        assert rows[0].actor == "mcp"
        assert rows[0].after_state["bc_id"] == "C64849"

    def test_duplicate_raises(self, sample_bc):
        with pytest.raises(ValueError, match="already exists"):
            _dispatch("create_bc", {"bc_id": sample_bc, "short_name": "Dup"})

    def test_missing_bc_id_raises(self):
        with pytest.raises(ValueError, match="BC ID is required"):
            _dispatch("create_bc", {"bc_id": "", "short_name": "X"})


class TestUpdateBc:
    def test_updates_and_audits_before_after(self, app, sample_bc):
        result = _dispatch("update_bc", {"bc_id": sample_bc, "short_name": "Renamed Concept", "ncit_code": "C12345"})
        assert result["short_name"] == "Renamed Concept"
        rows = _audit_rows(app, "updated")
        assert len(rows) == 1
        assert rows[0].actor == "mcp"
        assert rows[0].before_state["short_name"] == "Test Concept"
        assert rows[0].after_state["short_name"] == "Renamed Concept"

    def test_missing_bc_raises(self):
        with pytest.raises(ValueError, match="not found"):
            _dispatch("update_bc", {"bc_id": "NOPE", "short_name": "X"})


class TestMapNcit:
    def test_maps_and_audits(self, app, sample_bc):
        result = _dispatch("map_ncit_to_bc", {"bc_id": sample_bc, "ncit_code": "C77777"})
        assert result["ncit_code"] == "C77777"
        rows = _audit_rows(app, "ncit_mapped")
        assert len(rows) == 1
        assert rows[0].actor == "mcp"

    def test_promotes_import_id(self, app):
        with app.app_context():
            db.session.add(BiomedicalConcept(bc_id="IMPORT_1", short_name="Imported", status="provisional"))
            db.session.commit()
        result = _dispatch("map_ncit_to_bc", {"bc_id": "IMPORT_1", "ncit_code": "C55555"})
        assert result["bc_id"] == "C55555"
        with app.app_context():
            assert db.session.get(BiomedicalConcept, "IMPORT_1") is None
            assert db.session.get(BiomedicalConcept, "C55555") is not None

    def test_empty_code_raises(self, sample_bc):
        with pytest.raises(ValueError, match="ncit_code is required"):
            _dispatch("map_ncit_to_bc", {"bc_id": sample_bc, "ncit_code": " "})


class TestGovernanceWrites:
    def test_submit_then_advance_to_published(self, app, sample_bc):
        submitted = _dispatch("submit_bc_for_review", {"bc_id": sample_bc})
        assert submitted["status"] == "sme_review"

        first = _dispatch("advance_governance", {"bc_id": sample_bc, "comment": "looks good"})
        assert first == {"bc_id": sample_bc, "short_name": "Test Concept", "status": "cdisc_approval", "advanced": True}

        second = _dispatch("advance_governance", {"bc_id": sample_bc})
        assert second["status"] == "published"

        third = _dispatch("advance_governance", {"bc_id": sample_bc})
        assert third["advanced"] is False
        assert third["status"] == "published"

        with app.app_context():
            recs = GovernanceRecord.query.filter_by(bc_id=sample_bc).order_by(GovernanceRecord.id).all()
            assert [r.action for r in recs] == ["advanced", "advanced"]
            assert recs[0].actor == "mcp"
            assert recs[0].comment == "looks good"
        assert len(_audit_rows(app, "status_changed")) == 2
        assert len(_audit_rows(app, "submitted_for_review")) == 1

    def test_reject_returns_to_provisional(self, app, sample_bc):
        _dispatch("submit_bc_for_review", {"bc_id": sample_bc})
        result = _dispatch("reject_bc", {"bc_id": sample_bc, "comment": "needs work"})
        assert result["status"] == "provisional"
        with app.app_context():
            rec = GovernanceRecord.query.filter_by(bc_id=sample_bc, action="rejected").one()
            assert rec.stage == 0
            assert rec.actor == "mcp"
        assert len(_audit_rows(app, "rejected")) == 1


class TestReviewQueue:
    def test_queue_summary(self, app, sample_bc):
        with app.app_context():
            bc = db.session.get(BiomedicalConcept, sample_bc)
            bc.status = "sme_review"
            db.session.add(IngestionRecord(session_key="s", mapped={"bc_id": "X"}, status="pending"))
            db.session.add(IngestionRecord(session_key="s", mapped={"bc_id": "Y"}, status="approved"))
            db.session.commit()

        result = _dispatch("list_review_queue")
        assert result["sme_review"][0]["bc_id"] == sample_bc
        assert result["cdisc_approval"] == []
        assert result["pending_ingestion_records"] == 1
