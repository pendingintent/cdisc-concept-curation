import hashlib
import logging
import os
import time
import requests
from flask import current_app

logger = logging.getLogger(__name__)

# In-memory cache: {key: (timestamp, data)}
# Entries are never evicted — stale data is served while a refresh is attempted,
# so a timeout never blocks the request with an empty response.
_cache = {}
_CACHE_TTL = 300  # serve fresh data for 5 minutes
_CACHE_STALE_TTL = 3600  # serve stale data for up to 1 hour while refresh fails


def _cached(cache_key, fn):
    """Return cached data if fresh. If stale, attempt a refresh but fall back
    to the stale entry rather than propagating an error or blocking indefinitely."""
    now = time.time()
    entry = _cache.get(cache_key)

    if entry and now - entry[0] < _CACHE_TTL:
        return entry[1]  # fresh — serve immediately

    # Attempt a refresh. Broad catch is intentional: this is a resilience
    # seam and any refresh failure must fall back to stale data.
    try:
        data = fn()
        _cache[cache_key] = (now, data)
        return data
    except Exception:
        if entry and now - entry[0] < _CACHE_STALE_TTL:
            logger.warning("Cache refresh failed for %s; serving stale entry", cache_key, exc_info=True)
            return entry[1]
        logger.error("Cache refresh failed for %s with no stale fallback", cache_key, exc_info=True)
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
            except (requests.RequestException, ValueError) as e:
                logger.error("CDISC Library BC list fetch failed (%s): %s", self.base_url, e)
                return [{"error": str(e)}]

        return _cached(self._cache_key("biomedical_concepts"), _fetch)

    def get_bc(self, concept_id):
        """Fetch a single BC by conceptId."""
        try:
            return self._get(f"/mdr/bc/biomedicalconcepts/{concept_id}")
        except (requests.RequestException, ValueError) as e:
            logger.error("CDISC Library BC fetch failed for %s: %s", concept_id, e)
            return {"error": str(e)}

    def get_specialization(self, href):
        """Fetch a single dataset specialization by its href path."""
        try:
            return self._get(href)
        except (requests.RequestException, ValueError) as e:
            logger.error("CDISC Library specialization fetch failed for %s: %s", href, e)
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
                links = data.get("_links", {}).get("datasetSpecializations", [])
                # API returns either a flat list or a domain-keyed dict (sdtm/cdash/…)
                if isinstance(links, list):
                    return links
                return [item for v in links.values() if isinstance(v, list) for item in v]
            except (requests.RequestException, ValueError) as e:
                logger.error("CDISC Library specialization list fetch failed (%s): %s", self.base_url, e)
                return [{"error": str(e)}]

        return _cached(self._cache_key("dataset_specializations"), _fetch)

    def check_duplicate(self, short_name):
        """
        Check if a BC with this short_name already exists in the library.
        """
        try:
            bcs = self.get_biomedical_concepts()
            return any(bc.get("title", "").lower() == short_name.lower() for bc in bcs)
        except (requests.RequestException, ValueError) as e:
            logger.error("CDISC Library duplicate check failed for %r: %s", short_name, e)
            return False

    def publish_bc(self, bc_data):
        """POST a new BC to the CDISC Library (requires write permission)."""
        url = f"{self.base_url}/mdr/bc/biomedicalconcepts"
        response = requests.post(url, headers=self.headers, json=bc_data, timeout=10)
        response.raise_for_status()
        return response.json()
