import requests


class NCItApiClient:
    BASE_URL = 'https://api-evsrest.nci.nih.gov/api/v1'

    def _get(self, path, params=None):
        url = f"{self.BASE_URL}{path}"
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def search_concept(self, term, size=10):
        """Search NCIt for concepts matching term. Returns list of matches."""
        try:
            results = self._get(
                '/concept/ncit/search',
                params={'term': term, 'type': 'contains', 'include': 'minimal', 'pageSize': size}
            )
            concepts = results.get('concepts', [])
            return [
                {
                    'code': c.get('code'),
                    'name': c.get('name'),
                    'definition': next(
                        (d.get('definition') for d in c.get('definitions', []) if d.get('source') == 'NCI'),
                        c.get('name')
                    ),
                }
                for c in concepts
            ]
        except Exception as e:
            return [{'error': str(e)}]

    def get_concept(self, ncit_code):
        """Fetch full concept details including synonyms."""
        try:
            result = self._get(f'/concept/ncit/{ncit_code}', params={'include': 'full'})
            return {
                'code': result.get('code'),
                'name': result.get('name'),
                'definition': next(
                    (d.get('definition') for d in result.get('definitions', []) if d.get('source') == 'NCI'),
                    ''
                ),
                'synonyms': [
                    s.get('name') for s in result.get('synonyms', [])
                    if s.get('termType') in ('SY', 'AB', 'PT')
                ],
                'preferred_name': result.get('name'),
            }
        except Exception as e:
            return {'error': str(e)}

    def get_preferred_name(self, ncit_code):
        """Return just the preferred name for an NCIt code."""
        concept = self.get_concept(ncit_code)
        return concept.get('preferred_name') or concept.get('name', '')
