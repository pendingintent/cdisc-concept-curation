import hashlib
import logging
import os

import requests
from flask import current_app

from services.api_cache import CACHE_STALE_TTL as _CACHE_STALE_TTL  # noqa: F401
from services.api_cache import CACHE_TTL as _CACHE_TTL  # noqa: F401
from services.api_cache import _cache, cached  # noqa: F401  (_cache re-exported for tests)

logger = logging.getLogger(__name__)

# Backward-compatible alias — the shared implementation lives in
# services/api_cache.py and is used by all three API clients.
_cached = cached


def _config_value(name, default=""):
    """Read a config value from the Flask app when a context is active,
    falling back to the environment (the MCP server and scripts run
    without a request context)."""
    try:
        return current_app.config.get(name) or os.environ.get(name, default)
    except RuntimeError:
        return os.environ.get(name, default)


class CDISCApiClient:
    def __init__(self):
        self.api_key = _config_value("CDISC_API_KEY")
        self.subscription_key = _config_value("CDISC_SUBSCRIPTION_KEY")
        self.base_url = _config_value("CDISC_API_BASE_URL", "https://api.library.cdisc.org/api/cosmos/v2")
        # Auth parity with soa-workbench: prefer the subscription key with
        # its Ocp header, fall back to the classic api-key header.
        if self.subscription_key:
            auth_header = {"Ocp-Apim-Subscription-Key": self.subscription_key}
            key_material = self.subscription_key
        else:
            auth_header = {"api-key": self.api_key}
            key_material = self.api_key
        self.headers = {**auth_header, "Accept": "application/json"}
        # Stable, non-secret digest of the active key for use in cache keys
        self._key_digest = hashlib.sha256(key_material.encode()).hexdigest()[:8]

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
