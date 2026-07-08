"""Tests for NCIt service extensions and the /ncit/concept/<code> route."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.ncit_api import NCItApiClient

# ---------------------------------------------------------------------------
# Sample EVS full-concept response
# ---------------------------------------------------------------------------

EVS_FULL_CONCEPT = {
    "code": "C64849",
    "name": "Hemoglobin A1c Measurement",
    "definitions": [
        {"definition": "A quantitative measurement of HbA1c.", "source": "NCI"},
        {"definition": "Other source def.", "source": "OTHER"},
    ],
    "synonyms": [
        {"name": "HbA1c", "termType": "SY", "source": "NCI"},
        {"name": "Glycated Hemoglobin", "termType": "SY", "source": "CDISC"},
        {"name": "A1C", "termType": "AB", "source": "NCI"},
        {"name": "Hemoglobin A1c Measurement", "termType": "PT", "source": "NCI"},
        {"name": "Internal Code", "termType": "CODE", "source": "NCI"},
    ],
    "parents": [
        {"code": "C17721", "name": "Laboratory Test"},
        {"code": "C45398", "name": "Glucose Measurement"},
    ],
    "semanticType": [
        {"name": "Laboratory Procedure"},
    ],
}


# ---------------------------------------------------------------------------
# NCItApiClient.get_concept() — extended fields
# ---------------------------------------------------------------------------


class TestNcitGetConceptExtended:
    def setup_method(self):
        import services.ncit_api

        services.ncit_api._ncit_cache.clear()

    def _mock_get(self, data):
        mock = MagicMock()
        mock.json.return_value = data
        mock.raise_for_status = MagicMock()
        return mock

    def test_returns_parents(self):
        with patch("services.ncit_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_get(EVS_FULL_CONCEPT)
            result = NCItApiClient().get_concept("C64849")

        assert result["parents"] == [
            {"code": "C17721", "name": "Laboratory Test"},
            {"code": "C45398", "name": "Glucose Measurement"},
        ]

    def test_returns_semantic_type(self):
        with patch("services.ncit_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_get(EVS_FULL_CONCEPT)
            result = NCItApiClient().get_concept("C64849")

        assert result["semantic_type"] == ["Laboratory Procedure"]

    def test_returns_source_synonyms(self):
        with patch("services.ncit_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_get(EVS_FULL_CONCEPT)
            result = NCItApiClient().get_concept("C64849")

        # SY, AB, PT terms — CODE excluded
        assert "HbA1c" in result["synonyms"]
        assert "A1C" in result["synonyms"]
        assert "Hemoglobin A1c Measurement" in result["synonyms"]
        assert "Internal Code" not in result["synonyms"]

    def test_returns_all_definitions(self):
        with patch("services.ncit_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_get(EVS_FULL_CONCEPT)
            result = NCItApiClient().get_concept("C64849")

        assert "definitions" in result
        assert isinstance(result["definitions"], list)
        assert any(d["definition"] == "A quantitative measurement of HbA1c." for d in result["definitions"])

    def test_empty_parents_returns_empty_list(self):
        data = dict(EVS_FULL_CONCEPT, parents=[])
        with patch("services.ncit_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_get(data)
            result = NCItApiClient().get_concept("C64849")

        assert result["parents"] == []

    def test_missing_semantic_type_returns_empty_list(self):
        data = {k: v for k, v in EVS_FULL_CONCEPT.items() if k != "semanticType"}
        with patch("services.ncit_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_get(data)
            result = NCItApiClient().get_concept("C64849")

        assert result["semantic_type"] == []

    def test_error_returns_error_dict(self):
        with patch("services.ncit_api.requests.get", side_effect=requests.RequestException("timeout")):
            result = NCItApiClient().get_concept("C64849")

        assert "error" in result


# ---------------------------------------------------------------------------
# GET /ncit/concept/<code> route
# ---------------------------------------------------------------------------

CONCEPT_RESULT = {
    "code": "C64849",
    "name": "Hemoglobin A1c Measurement",
    "preferred_name": "Hemoglobin A1c Measurement",
    "definition": "A quantitative measurement of HbA1c.",
    "definitions": [{"definition": "A quantitative measurement of HbA1c.", "source": "NCI"}],
    "synonyms": ["HbA1c", "A1C"],
    "parents": [{"code": "C17721", "name": "Laboratory Test"}],
    "semantic_type": ["Laboratory Procedure"],
}


class TestNcitConceptRoute:
    def test_returns_json(self, client):
        with patch("routes.ncit.NCItApiClient") as MockClient:
            MockClient.return_value.get_concept.return_value = CONCEPT_RESULT
            r = client.get("/ncit/concept/C64849", headers={"Accept": "application/json"})

        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["code"] == "C64849"
        assert data["preferred_name"] == "Hemoglobin A1c Measurement"
        assert "parents" in data
        assert "semantic_type" in data

    def test_calls_get_concept_with_code(self, client):
        with patch("routes.ncit.NCItApiClient") as MockClient:
            MockClient.return_value.get_concept.return_value = CONCEPT_RESULT
            client.get("/ncit/concept/C64849")

        MockClient.return_value.get_concept.assert_called_once_with("C64849")

    def test_error_from_service_returns_500(self, client):
        with patch("routes.ncit.NCItApiClient") as MockClient:
            MockClient.return_value.get_concept.return_value = {"error": "Not found"}
            r = client.get("/ncit/concept/CXXXXX")

        assert r.status_code == 404
