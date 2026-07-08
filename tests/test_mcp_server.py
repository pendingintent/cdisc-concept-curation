"""Tests for the MCP server (mcp_server/server.py).

Calls _dispatch directly (no stdio transport) with the shared in-memory
test app injected, mirroring the soa-workbench test pattern.
"""

from unittest.mock import patch

import pytest

import mcp_server.server as mcp_srv
from extensions import db
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
        for tool in mcp_srv._TOOLS:
            assert tool.name in {
                "list_bcs",
                "get_bc",
                "search_ncit",
                "get_ncit_concept",
                "search_loinc",
                "search_cdisc_library",
                "get_library_bc",
                "list_review_queue",
            }


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
