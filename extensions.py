import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Enable WAL + a busy timeout on every SQLite connection.

    Required because two writer processes share instance/cdisc_curation.db
    (the Flask app and the MCP server); without WAL the second writer hits
    'database is locked'. WAL is persistent per database file; in-memory
    test databases silently keep their 'memory' journal mode.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()
