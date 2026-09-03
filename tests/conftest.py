import pytest

from app import create_app
from config import Config
from extensions import db as _db
from models.alignment import AlignmentJob  # noqa: F401
from models.audit import AuditLog  # noqa: F401  (registers table metadata)
from models.bc import BiomedicalConcept, DataElementConcept  # noqa: F401
from models.governance import GovernanceRecord  # noqa: F401
from models.ingestion import IngestionRecord  # noqa: F401
from models.note import Note  # noqa: F401
from models.specialization import DatasetSpecialization  # noqa: F401


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"
    CDISC_API_KEY = ""
    CDISC_SUBSCRIPTION_KEY = ""
    CDISC_API_BASE_URL = "https://api.library.cdisc.org/api/cosmos/v2"
    NCIT_API_BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    WTF_CSRF_ENABLED = False
    ALIGNMENT_SUBMODULE_DIR = Config.ALIGNMENT_SUBMODULE_DIR


@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Reset the database before each test."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield
        _db.session.remove()


@pytest.fixture(autouse=True)
def clear_api_cache():
    """Reset the shared external-API cache so tests never see each other's
    (or a failure's) cached responses."""
    from services import api_cache

    api_cache._cache.clear()
    yield


@pytest.fixture()
def sample_bc(app):
    """A minimal BiomedicalConcept persisted to the test DB."""
    with app.app_context():
        bc = BiomedicalConcept(
            bc_id="C12345",
            short_name="Test Concept",
            definition="A test BC definition.",
            ncit_code="C12345",
            status="provisional",
            submitter="tester",
        )
        _db.session.add(bc)
        _db.session.commit()
        return bc.bc_id  # return PK so tests can re-query within their own context


@pytest.fixture()
def sample_spec(app, sample_bc):
    """A minimal DatasetSpecialization persisted to the test DB, linked to sample_bc."""
    with app.app_context():
        spec = DatasetSpecialization(
            vlm_group_id="C12345.SDTM",
            bc_id=sample_bc,
            domain="VS",
            short_name="Test Spec",
            status="provisional",
        )
        _db.session.add(spec)
        _db.session.commit()
        return spec.vlm_group_id  # return PK so tests can re-query within their own context
