import logging
import os

import requests
from flask import current_app

from services.api_cache import cached

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"


def _pick_definition(definitions):
    """Return the best definition from a list of {definition, source} dicts.
    Priority: CDISC > NCI > first available > empty string."""
    for source in ("CDISC", "NCI"):
        match = next((d.get("definition", "") for d in definitions if d.get("source") == source), None)
        if match:
            return match
    return next((d.get("definition", "") for d in definitions if d.get("definition")), "")


class NCItApiClient:
    def __init__(self):
        # Honor NCIT_API_BASE_URL from Flask config, falling back to the
        # environment when no app context is active (MCP server, scripts).
        try:
            self.base_url = current_app.config.get("NCIT_API_BASE_URL") or os.environ.get("NCIT_API_BASE_URL", _DEFAULT_BASE_URL)
        except RuntimeError:
            self.base_url = os.environ.get("NCIT_API_BASE_URL", _DEFAULT_BASE_URL)

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def search_concept(self, term, size=10):
        """Search NCIt for concepts matching term. Returns list of matches."""
        try:
            results = self._get("/concept/ncit/search", params={"term": term, "type": "contains", "include": "summary", "pageSize": size})
            concepts = results.get("concepts", [])
            return [
                {
                    "code": c.get("code"),
                    "name": c.get("name"),
                    "preferred_name": c.get("name"),
                    "definition": _pick_definition(c.get("definitions", [])),
                }
                for c in concepts
            ]
        except (requests.RequestException, ValueError) as e:
            logger.error("NCIt search failed for term %r: %s", term, e)
            return [{"error": str(e)}]

    def get_concept(self, ncit_code):
        """Fetch full concept details including synonyms, definitions, parents, and semantic type."""

        def _fetch():
            result = self._get(f"/concept/ncit/{ncit_code}", params={"include": "full"})
            code = result.get("code")
            return {
                "code": code,
                "name": result.get("name"),
                "preferred_name": result.get("name"),
                "definition": _pick_definition(result.get("definitions", [])),
                "definitions": [{"definition": d.get("definition"), "source": d.get("source")} for d in result.get("definitions", [])],
                "synonyms": [s.get("name") for s in result.get("synonyms", []) if s.get("termType") in ("SY", "AB", "PT")],
                "parents": [{"code": p.get("code"), "name": p.get("name")} for p in result.get("parents", [])],
                "children": [{"code": c.get("code"), "name": c.get("name")} for c in result.get("children", [])],
                "semantic_type": [st.get("name") for st in result.get("semanticType", [])],
                "reference": f"https://ncithesaurus.nci.nih.gov/ncitbrowser/ConceptReport.jsp?dictionary=NCI_Thesaurus&code={code}" if code else "",
            }

        try:
            return cached(("ncit_concept", self.base_url, ncit_code), _fetch)
        except (requests.RequestException, ValueError) as e:
            logger.error("NCIt concept fetch failed for %s: %s", ncit_code, e)
            return {"error": str(e)}

    def get_preferred_name(self, ncit_code):
        """Return just the preferred name for an NCIt code."""
        concept = self.get_concept(ncit_code)
        return concept.get("preferred_name") or concept.get("name", "")
