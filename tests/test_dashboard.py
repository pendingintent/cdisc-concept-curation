"""Tests for routes/dashboard.py — concurrent API fan-out and local stats."""

from unittest.mock import MagicMock, patch

from extensions import db
from models.bc import BiomedicalConcept

LIBRARY_BCS = [
    {"href": "/mdr/bc/biomedicalconcepts/C64849", "title": "Hemoglobin A1c", "type": "BC"},
    {"href": "/mdr/bc/biomedicalconcepts/C25298", "title": "Systolic BP", "type": "BC"},
]
LIBRARY_SPECS = [
    {"href": "/mdr/specializations/sdtm/datasetspecializations/HBA1C", "title": "HBA1C", "type": "SDTM"},
]


def _mock_client(bcs, specs):
    client = MagicMock()
    client.get_biomedical_concepts.return_value = bcs
    client.get_dataset_specializations.return_value = specs
    return client


class TestDashboardIndex:
    def test_renders_with_api_data(self, client):
        with patch("routes.dashboard.CDISCApiClient") as mock_cls:
            mock_cls.return_value = _mock_client(LIBRARY_BCS, LIBRARY_SPECS)
            resp = client.get("/")
        assert resp.status_code == 200
        assert b"Hemoglobin A1c" in resp.data

    def test_renders_when_api_errors(self, client):
        """API failures are encoded as error dicts — the page must still render."""
        with patch("routes.dashboard.CDISCApiClient") as mock_cls:
            mock_cls.return_value = _mock_client(
                [{"error": "401 Unauthorized"}],
                [{"error": "timeout"}],
            )
            resp = client.get("/")
        assert resp.status_code == 200
        assert b"Hemoglobin A1c" not in resp.data

    def test_renders_with_empty_api_results(self, client):
        with patch("routes.dashboard.CDISCApiClient") as mock_cls:
            mock_cls.return_value = _mock_client([], [])
            resp = client.get("/")
        assert resp.status_code == 200

    def test_local_stats_reflect_db(self, app, client, sample_bc):
        with app.app_context():
            db.session.add(
                BiomedicalConcept(
                    bc_id="C99999",
                    short_name="Published Concept",
                    status="published",
                    submitter="tester",
                )
            )
            db.session.commit()
        with patch("routes.dashboard.CDISCApiClient") as mock_cls:
            mock_cls.return_value = _mock_client([], [])
            resp = client.get("/")
        assert resp.status_code == 200
        # Both local BCs appear in recent submissions
        assert b"Test Concept" in resp.data
        assert b"Published Concept" in resp.data

    def test_both_api_calls_made_concurrently(self, client):
        """Both Library endpoints are requested exactly once per page load."""
        mock = _mock_client(LIBRARY_BCS, LIBRARY_SPECS)
        with patch("routes.dashboard.CDISCApiClient") as mock_cls:
            mock_cls.return_value = mock
            client.get("/")
        assert mock.get_biomedical_concepts.call_count == 1
        assert mock.get_dataset_specializations.call_count == 1
