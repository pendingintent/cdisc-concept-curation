import time
import requests

_ncit_cache = {}
_NCIT_TTL = 300  # serve fresh data for 5 minutes
_NCIT_STALE_TTL = 3600  # serve stale data for up to 1 hour while refresh fails


class NCItApiClient:
    BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"

    def _get(self, path, params=None):
        url = f"{self.BASE_URL}{path}"
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def search_concept(self, term, size=10):
        """Search NCIt for concepts matching term. Returns list of matches."""
        try:
            results = self._get("/concept/ncit/search", params={"term": term, "type": "contains", "include": "minimal", "pageSize": size})
            concepts = results.get("concepts", [])
            return [
                {
                    "code": c.get("code"),
                    "name": c.get("name"),
                    "definition": next((d.get("definition") for d in c.get("definitions", []) if d.get("source") == "NCI"), c.get("name")),
                }
                for c in concepts
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_concept(self, ncit_code):
        """Fetch full concept details including synonyms, definitions, parents, and semantic type."""
        cache_key = ("concept", ncit_code)
        now = time.time()
        entry = _ncit_cache.get(cache_key)
        if entry and now - entry[0] < _NCIT_TTL:
            return entry[1]

        try:
            result = self._get(f"/concept/ncit/{ncit_code}", params={"include": "full"})
            data = {
                "code": result.get("code"),
                "name": result.get("name"),
                "preferred_name": result.get("name"),
                "definition": next((d.get("definition") for d in result.get("definitions", []) if d.get("source") == "NCI"), ""),
                "definitions": [{"definition": d.get("definition"), "source": d.get("source")} for d in result.get("definitions", [])],
                "synonyms": [s.get("name") for s in result.get("synonyms", []) if s.get("termType") in ("SY", "AB", "PT")],
                "parents": [{"code": p.get("code"), "name": p.get("name")} for p in result.get("parents", [])],
                "semantic_type": [st.get("name") for st in result.get("semanticType", [])],
            }
            _ncit_cache[cache_key] = (now, data)
            return data
        except Exception as e:
            return {"error": str(e)}

    def get_preferred_name(self, ncit_code):
        """Return just the preferred name for an NCIt code."""
        concept = self.get_concept(ncit_code)
        return concept.get("preferred_name") or concept.get("name", "")
