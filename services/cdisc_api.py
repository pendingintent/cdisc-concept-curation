import os
import requests
from flask import current_app


class CDISCApiClient:
    def __init__(self):
        try:
            self.api_key = current_app.config.get('CDISC_API_KEY') or os.environ.get('CDISC_API_KEY', '')
            self.base_url = current_app.config.get('CDISC_API_BASE_URL', 'https://api.library.cdisc.org/api/cosmos/v2')
        except RuntimeError:
            self.api_key = os.environ.get('CDISC_API_KEY', '')
            self.base_url = 'https://api.library.cdisc.org/api/cosmos/v2'
        self.headers = {
            'api-key': self.api_key,
            'Accept': 'application/json',
        }

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        response = requests.get(url, headers=self.headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_biomedical_concepts(self, page=0, size=50):
        """List BCs from the CDISC Library."""
        try:
            return self._get('/mdr/bc/biomedicalconcepts', params={'page': page, 'size': size})
        except Exception as e:
            return {'error': str(e), 'items': []}

    def get_bc(self, bc_id):
        """Fetch a single BC by ID."""
        try:
            return self._get(f'/mdr/bc/biomedicalconcepts/{bc_id}')
        except Exception as e:
            return {'error': str(e)}

    def search_bcs(self, query, page=0, size=20):
        """Search BCs by name."""
        try:
            return self._get('/mdr/bc/biomedicalconcepts', params={'q': query, 'page': page, 'size': size})
        except Exception as e:
            return {'error': str(e), 'items': []}

    def check_duplicate(self, short_name):
        """Check if a BC with this short_name already exists in the library."""
        try:
            results = self._get('/mdr/bc/biomedicalconcepts', params={'q': short_name, 'size': 10})
            items = results.get('items', [])
            return any(
                item.get('shortName', '').lower() == short_name.lower()
                for item in items
            )
        except Exception:
            return False

    def publish_bc(self, bc_data):
        """POST a new BC to the CDISC Library (requires write permission)."""
        url = f"{self.base_url}/mdr/bc/biomedicalconcepts"
        response = requests.post(url, headers=self.headers, json=bc_data, timeout=15)
        response.raise_for_status()
        return response.json()
