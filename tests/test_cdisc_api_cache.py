"""Tests for the stale-tolerant in-memory cache in services/cdisc_api.py."""

import time

import pytest

import services.cdisc_api as cdisc_api
from services.cdisc_api import CDISCApiClient, _cached


class TestCachedHelper:
    def setup_method(self):
        cdisc_api._cache.clear()

    def test_first_call_fetches_and_stores(self):
        calls = []

        def fn():
            calls.append(1)
            return ["data"]

        assert _cached("k", fn) == ["data"]
        assert len(calls) == 1
        assert "k" in cdisc_api._cache

    def test_fresh_entry_served_without_refetch(self):
        calls = []

        def fn():
            calls.append(1)
            return ["data"]

        _cached("k", fn)
        assert _cached("k", fn) == ["data"]
        assert len(calls) == 1  # second call served from cache

    def test_stale_entry_refreshes_successfully(self):
        cdisc_api._cache["k"] = (time.time() - cdisc_api._CACHE_TTL - 10, ["old"])
        assert _cached("k", lambda: ["new"]) == ["new"]
        assert cdisc_api._cache["k"][1] == ["new"]

    def test_stale_entry_served_when_refresh_fails(self):
        cdisc_api._cache["k"] = (time.time() - cdisc_api._CACHE_TTL - 10, ["old"])

        def failing():
            raise ConnectionError("boom")

        assert _cached("k", failing) == ["old"]

    def test_expired_entry_raises_when_refresh_fails(self):
        cdisc_api._cache["k"] = (time.time() - cdisc_api._CACHE_STALE_TTL - 10, ["old"])

        def failing():
            raise ConnectionError("boom")

        with pytest.raises(ConnectionError):
            _cached("k", failing)

    def test_no_entry_raises_when_fetch_fails(self):
        def failing():
            raise ConnectionError("boom")

        with pytest.raises(ConnectionError):
            _cached("missing", failing)


class TestClientCacheKeys:
    def setup_method(self):
        cdisc_api._cache.clear()

    def test_cache_key_excludes_raw_api_key(self, app):
        with app.app_context():
            client = CDISCApiClient()
        key = client._cache_key("biomedical_concepts")
        assert client.api_key not in key or client.api_key == ""
        assert key[2] == "biomedical_concepts"

    def test_get_biomedical_concepts_error_encoded_not_raised(self, app, monkeypatch):
        """API failure is captured as [{'error': ...}] and cached, not raised."""
        import requests

        def boom(*args, **kwargs):
            raise requests.ConnectionError("no network")

        monkeypatch.setattr(cdisc_api.requests, "get", boom)
        with app.app_context():
            result = CDISCApiClient().get_biomedical_concepts()
        assert len(result) == 1
        assert "error" in result[0]

    def test_error_result_replaced_after_ttl(self, app, monkeypatch):
        """A cached error list refreshes to real data once the TTL passes."""
        import requests

        with app.app_context():
            client = CDISCApiClient()

        def boom(*args, **kwargs):
            raise requests.ConnectionError("no network")

        monkeypatch.setattr(cdisc_api.requests, "get", boom)
        with app.app_context():
            assert "error" in CDISCApiClient().get_biomedical_concepts()[0]

        # Age the entry past the fresh TTL, then make the API succeed
        key = client._cache_key("biomedical_concepts")
        ts, data = cdisc_api._cache[key]
        cdisc_api._cache[key] = (ts - cdisc_api._CACHE_TTL - 10, data)

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"_links": {"biomedicalConcepts": [{"href": "/x", "title": "X"}]}}

        monkeypatch.setattr(cdisc_api.requests, "get", lambda *a, **kw: FakeResp())
        with app.app_context():
            result = CDISCApiClient().get_biomedical_concepts()
        assert result == [{"href": "/x", "title": "X"}]


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


PACKAGES_PAYLOAD = {
    "_links": {
        "packages": [
            {"href": "/mdr/ct/packages/adamct-2025-09-26", "title": "ADaM CT", "type": "Terminology"},
            {"href": "/mdr/ct/packages/sdtmct-2024-09-27", "title": "SDTM CT 2024-09-27", "type": "Terminology"},
            {"href": "/mdr/ct/packages/sdtmct-2025-09-26", "title": "SDTM CT 2025-09-26", "type": "Terminology"},
        ]
    }
}

CODELIST_PAYLOAD = {
    "conceptId": "C66734",
    "name": "SDTM Domain Abbreviation",
    "terms": [
        {"conceptId": "C49562", "submissionValue": "AE", "preferredTerm": "Adverse Event Domain"},
        {"conceptId": "C66741", "submissionValue": "VS", "preferredTerm": "Vital Signs Domain"},
    ],
}


class TestGetCtPackages:
    def setup_method(self):
        cdisc_api._cache.clear()

    def test_returns_package_links(self, app, monkeypatch):
        monkeypatch.setattr(cdisc_api.requests, "get", lambda *a, **kw: _FakeResp(PACKAGES_PAYLOAD))
        with app.app_context():
            result = CDISCApiClient().get_ct_packages()
        assert len(result) == 3
        assert result[0]["href"] == "/mdr/ct/packages/adamct-2025-09-26"

    def test_error_encoded_not_raised(self, app, monkeypatch):
        import requests

        def boom(*a, **kw):
            raise requests.ConnectionError("no network")

        monkeypatch.setattr(cdisc_api.requests, "get", boom)
        with app.app_context():
            result = CDISCApiClient().get_ct_packages()
        assert "error" in result[0]


class TestGetSdtmDomainCodes:
    def setup_method(self):
        cdisc_api._cache.clear()

    def test_uses_most_recent_sdtm_package(self, app, monkeypatch):
        requested_urls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            requested_urls.append(url)
            if url.endswith("/mdr/ct/packages"):
                return _FakeResp(PACKAGES_PAYLOAD)
            return _FakeResp(CODELIST_PAYLOAD)

        monkeypatch.setattr(cdisc_api.requests, "get", fake_get)
        with app.app_context():
            result = CDISCApiClient().get_sdtm_domain_codes()

        assert any(u.endswith("/mdr/ct/packages/sdtmct-2025-09-26/codelists/C66734") for u in requested_urls)
        assert result == [
            {"code": "AE", "label": "Adverse Event Domain"},
            {"code": "VS", "label": "Vital Signs Domain"},
        ]

    def test_no_sdtm_package_found_returns_error(self, app, monkeypatch):
        empty_payload = {"_links": {"packages": [{"href": "/mdr/ct/packages/adamct-2025-09-26", "title": "ADaM CT"}]}}
        monkeypatch.setattr(cdisc_api.requests, "get", lambda *a, **kw: _FakeResp(empty_payload))
        with app.app_context():
            result = CDISCApiClient().get_sdtm_domain_codes()
        assert "error" in result[0]

    def test_network_failure_encoded_not_raised(self, app, monkeypatch):
        import requests

        def boom(*a, **kw):
            raise requests.ConnectionError("no network")

        monkeypatch.setattr(cdisc_api.requests, "get", boom)
        with app.app_context():
            result = CDISCApiClient().get_sdtm_domain_codes()
        assert "error" in result[0]
