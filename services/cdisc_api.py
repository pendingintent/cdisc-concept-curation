import hashlib
import os
import time
import requests
from flask import current_app

# Simple in-memory cache: {(base_url, api_key_digest, endpoint): (timestamp, data)}
_cache = {}
_CACHE_TTL = 300  # 5 minutes


def _cached(cache_key, fn):
    now = time.time()
    if cache_key in _cache and now - _cache[cache_key][0] < _CACHE_TTL:
        return _cache[cache_key][1]
    data = fn()
    _cache[cache_key] = (now, data)
    return data


class CDISCApiClient:
    def __init__(self):
        try:
            self.api_key = current_app.config.get("CDISC_API_KEY") or os.environ.get("CDISC_API_KEY", "")
            self.base_url = current_app.config.get(
                "CDISC_API_BASE_URL",
                "https://api.library.cdisc.org/api/cosmos/v2",
            )
        except RuntimeError:
            self.api_key = os.environ.get("CDISC_API_KEY", "")
            self.base_url = "https://api.library.cdisc.org/api/cosmos/v2"
        self.headers = {
            "api-key": self.api_key,
            "Accept": "application/json",
        }
        # Stable, non-secret digest of the api_key for use in cache keys
        self._key_digest = hashlib.sha256(self.api_key.encode()).hexdigest()[:8]

    def _cache_key(self, endpoint):
        return (self.base_url, self._key_digest, endpoint)

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        response = requests.get(url, headers=self.headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_biomedical_concepts(self):
        """
        List all BCs from the CDISC Library.
        Returns list of {href, title, type} link objects (~1127 items).
        Response shape:
            {name, label, _links: {biomedicalConcepts: [{href, ...}]}}
        """

        def _fetch():
            try:
                data = self._get("/mdr/bc/biomedicalconcepts")
                return data.get("_links", {}).get("biomedicalConcepts", [])
            except Exception as e:
                return [{"error": str(e)}]

        return _cached(self._cache_key("biomedical_concepts"), _fetch)

    def get_bc(self, concept_id):
        """Fetch a single BC by conceptId."""
        try:
            return self._get(f"/mdr/bc/biomedicalconcepts/{concept_id}")
        except Exception as e:
            return {"error": str(e)}

    def get_dataset_specializations(self):
        """
        List all dataset specializations from the CDISC Library.
        Returns list of {href, title, type} link objects (~1123 items).
        Response shape:
            {name, label, _links: {datasetSpecializations: {...}}}
        """

        def _fetch():
            try:
                data = self._get("/mdr/specializations/datasetspecializations")
                sdtm = data.get("_links", {}).get("datasetSpecializations", {}).get("sdtm", [])
                return sdtm
            except Exception as e:
                return [{"error": str(e)}]

        return _cached(self._cache_key("dataset_specializations"), _fetch)

    def check_duplicate(self, short_name):
        """
        Check if a BC with this short_name already exists in the library.
        """
        try:
            bcs = self.get_biomedical_concepts()
            return any(bc.get("title", "").lower() == short_name.lower() for bc in bcs)
        except Exception:
            return False

    def publish_bc(self, bc_data):
        """POST a new BC to the CDISC Library (requires write permission)."""
        url = f"{self.base_url}/mdr/bc/biomedicalconcepts"
        response = requests.post(url, headers=self.headers, json=bc_data, timeout=10)
        response.raise_for_status()
        return response.json()
