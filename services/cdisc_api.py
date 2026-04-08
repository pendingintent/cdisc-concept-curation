import hashlib
import os
import time
import requests
from flask import current_app

# In-memory cache: {key: (timestamp, data)}
# Entries are never evicted — stale data is served while a refresh is attempted,
# so a timeout never blocks the request with an empty response.
_cache = {}
_CACHE_TTL = 300        # serve fresh data for 5 minutes
_CACHE_STALE_TTL = 3600  # serve stale data for up to 1 hour while refresh fails


def _cached(cache_key, fn):
    """Return cached data if fresh. If stale, attempt a refresh but fall back
    to the stale entry rather than propagating an error or blocking indefinitely."""
    now = time.time()
    entry = _cache.get(cache_key)

    if entry and now - entry[0] < _CACHE_TTL:
        return entry[1]  # fresh — serve immediately

    # Attempt a refresh
    try:
        data = fn()
        _cache[cache_key] = (now, data)
        return data
    except Exception:
        if entry and now - entry[0] < _CACHE_STALE_TTL:
            # Serve stale rather than an error
            return entry[1]
        raise  # genuinely no data at all — let caller handle


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

    def get_specialization(self, href):
        """Fetch a single dataset specialization by its href path."""
        try:
            return self._get(href)
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
