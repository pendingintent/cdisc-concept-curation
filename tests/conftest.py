import pytest
from app import create_app
from extensions import db as _db
from models.bc import BiomedicalConcept, DataElementConcept
from models.governance import GovernanceRecord
from models.audit import AuditLog
from models.ingestion import IngestionRecord


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    CDISC_API_KEY = ''
    CDISC_API_BASE_URL = 'https://api.library.cdisc.org/api/cosmos/v2'
    NCIT_API_BASE_URL = 'https://api-evsrest.nci.nih.gov/api/v1'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    WTF_CSRF_ENABLED = False


@pytest.fixture(scope='session')
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


@pytest.fixture()
def sample_bc(app):
    """A minimal BiomedicalConcept persisted to the test DB."""
    with app.app_context():
        bc = BiomedicalConcept(
            bc_id='C12345',
            short_name='Test Concept',
            definition='A test BC definition.',
            ncit_code='C12345',
            status='provisional',
            submitter='tester',
        )
        _db.session.add(bc)
        _db.session.commit()
        return bc.bc_id  # return PK so tests can re-query within their own context
