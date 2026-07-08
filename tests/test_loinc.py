"""Tests for services/loinc_api.py and routes/loinc.py."""

import json
from unittest.mock import MagicMock, patch

import requests

from services.loinc_api import LOINC_EF_FIELDS, LoincApiClient

# ---------------------------------------------------------------------------
# Sample NLM response using ef parameter
# response format: [total, [internal_codes], {field: [values...]}, display_data]
# ---------------------------------------------------------------------------

NLM_EF_RESPONSE = [
    2,
    ["4548-4", "17856-6"],
    {
        "LOINC_NUM": ["4548-4", "17856-6"],
        "SHORTNAME": ["HbA1c MFr Bld", "HbA1c MFr Bld HPLC"],
        "LONG_COMMON_NAME": ["Hemoglobin A1c/Hemoglobin.total in Blood", "Hemoglobin A1c/Hemoglobin.total in Blood by HPLC"],
        "RELATEDNAMES2": ["Glycated Hb", "Glycohemoglobin"],
        "PROPERTY": ["MFr", "MFr"],
        "METHOD_TYP": [None, "HPLC"],
        "AnswerLists": [None, None],
        "units": ["%", "%"],
        "datatype": ["NM", "NM"],
        "isCopyrighted": ["N", "N"],
        "containsCopyrighted": ["N", "N"],
        "CONSUMER_NAME": ["Hemoglobin A1c", "Hemoglobin A1c by HPLC"],
        "COMPONENT": ["Hemoglobin A1c", "Hemoglobin A1c"],
        "EXTERNAL_COPYRIGHT_NOTICE": [None, None],
        "EXTERNAL_COPYRIGHT_LINK": [None, None],
    },
    None,
]


# ---------------------------------------------------------------------------
# LoincApiClient.search()
# ---------------------------------------------------------------------------


class TestLoincApiClientSearch:
    def _mock_response(self, data, status=200):
        mock = MagicMock()
        mock.status_code = status
        mock.json.return_value = data
        mock.raise_for_status = MagicMock()
        return mock

    def test_returns_normalized_list(self):
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response(NLM_EF_RESPONSE)
            results = LoincApiClient().search("hba1c")

        assert len(results) == 2
        assert results[0]["LOINC_NUM"] == "4548-4"
        assert results[0]["LONG_COMMON_NAME"] == "Hemoglobin A1c/Hemoglobin.total in Blood"
        assert results[0]["SHORTNAME"] == "HbA1c MFr Bld"
        assert results[0]["units"] == "%"
        assert results[0]["datatype"] == "NM"
        assert results[0]["PROPERTY"] == "MFr"
        assert results[0]["METHOD_TYP"] is None
        assert results[1]["LOINC_NUM"] == "17856-6"
        assert results[1]["METHOD_TYP"] == "HPLC"

    def test_all_ef_fields_present_in_result(self):
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response(NLM_EF_RESPONSE)
            results = LoincApiClient().search("hba1c")

        expected_fields = [
            "LOINC_NUM",
            "SHORTNAME",
            "LONG_COMMON_NAME",
            "RELATEDNAMES2",
            "PROPERTY",
            "METHOD_TYP",
            "AnswerLists",
            "units",
            "datatype",
            "isCopyrighted",
            "containsCopyrighted",
            "CONSUMER_NAME",
            "COMPONENT",
            "EXTERNAL_COPYRIGHT_NOTICE",
            "EXTERNAL_COPYRIGHT_LINK",
        ]
        for field in expected_fields:
            assert field in results[0], f"Missing field: {field}"

    def test_uses_ef_parameter(self):
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response(NLM_EF_RESPONSE)
            LoincApiClient().search("glucose", size=5)

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs["params"]
        assert "ef" in params
        assert "df" not in params
        assert "LOINC_NUM" in params["ef"]
        assert "LONG_COMMON_NAME" in params["ef"]
        assert params["terms"] == "glucose"
        assert params["maxList"] == 5

    def test_ef_fields_constant_contains_all_required_fields(self):
        required = [
            "LOINC_NUM",
            "SHORTNAME",
            "LONG_COMMON_NAME",
            "RELATEDNAMES2",
            "PROPERTY",
            "METHOD_TYP",
            "AnswerLists",
            "units",
            "datatype",
            "isCopyrighted",
            "containsCopyrighted",
            "CONSUMER_NAME",
            "COMPONENT",
            "EXTERNAL_COPYRIGHT_NOTICE",
            "EXTERNAL_COPYRIGHT_LINK",
        ]
        for field in required:
            assert field in LOINC_EF_FIELDS, f"Missing from LOINC_EF_FIELDS: {field}"

    def test_uses_basic_auth_when_env_vars_set(self, monkeypatch):
        monkeypatch.setenv("LOINC_USER", "myuser")
        monkeypatch.setenv("LOINC_PASSWORD", "mypass")
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response([0, [], {}, None])
            LoincApiClient().search("test")

        auth = mock_get.call_args[1].get("auth")
        assert auth == ("myuser", "mypass")

    def test_no_auth_when_env_vars_missing(self, monkeypatch):
        monkeypatch.delenv("LOINC_USER", raising=False)
        monkeypatch.delenv("LOINC_PASSWORD", raising=False)
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response([0, [], {}, None])
            LoincApiClient().search("test")

        auth = mock_get.call_args[1].get("auth")
        assert auth is None

    def test_empty_results(self):
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response([0, [], {}, None])
            results = LoincApiClient().search("zzznomatch")

        assert results == []

    def test_missing_codes_array_returns_empty(self):
        with patch("services.loinc_api.requests.get") as mock_get:
            mock_get.return_value = self._mock_response([0])
            results = LoincApiClient().search("test")

        assert results == []

    def test_network_error_returns_error_entry(self):
        with patch("services.loinc_api.requests.get", side_effect=requests.RequestException("timeout")):
            results = LoincApiClient().search("hba1c")

        assert len(results) == 1
        assert "error" in results[0]
        assert "timeout" in results[0]["error"]


# ---------------------------------------------------------------------------
# GET /loinc/search route
# ---------------------------------------------------------------------------


class TestLoincSearchRoute:
    def test_returns_json_for_ajax(self, client):
        with patch("routes.loinc.LoincApiClient") as MockClient:
            MockClient.return_value.search.return_value = [{"LOINC_NUM": "4548-4", "LONG_COMMON_NAME": "Hemoglobin A1c/Hemoglobin.total in Blood"}]
            r = client.get("/loinc/search?term=hba1c", headers={"Accept": "application/json"})

        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        assert data[0]["LOINC_NUM"] == "4548-4"

    def test_empty_term_returns_empty_list(self, client):
        r = client.get("/loinc/search", headers={"Accept": "application/json"})
        assert r.status_code == 200
        assert json.loads(r.data) == []

    def test_calls_client_with_term(self, client):
        with patch("routes.loinc.LoincApiClient") as MockClient:
            MockClient.return_value.search.return_value = []
            client.get("/loinc/search?term=glucose", headers={"Accept": "application/json"})

        MockClient.return_value.search.assert_called_once_with("glucose", size=10)

    def test_format_json_param_triggers_json_response(self, client):
        with patch("routes.loinc.LoincApiClient") as MockClient:
            MockClient.return_value.search.return_value = []
            r = client.get("/loinc/search?term=hba1c&format=json")

        assert r.status_code == 200
        assert r.content_type.startswith("application/json")
