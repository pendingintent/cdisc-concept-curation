import logging
import os

from flask import Flask

from config import Config
from extensions import db, migrate


def _configure_logging():
    """Attach a handler to the app's logger namespace once.

    Configures the root logger only if nothing else has (pytest, gunicorn,
    and the MCP server may install their own handlers first).
    """
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def create_app(config_class=Config):
    _configure_logging()
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from routes.audit import bp as audit_bp
    from routes.bc import bp as bc_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.governance import bp as governance_bp
    from routes.ingestion import bp as ingestion_bp
    from routes.loinc import bp as loinc_bp
    from routes.ncit import bp as ncit_bp
    from routes.ncit_alignment import bp as ncit_alignment_bp
    from routes.notes import bp as notes_bp
    from routes.specializations import bp as specializations_bp

    app.register_blueprint(dashboard_bp, url_prefix="/")
    app.register_blueprint(ingestion_bp, url_prefix="/ingestion")
    app.register_blueprint(bc_bp, url_prefix="/bc")
    app.register_blueprint(ncit_bp, url_prefix="/ncit")
    app.register_blueprint(ncit_alignment_bp, url_prefix="/ncit-alignment")
    app.register_blueprint(loinc_bp, url_prefix="/loinc")
    app.register_blueprint(specializations_bp, url_prefix="/specializations")
    app.register_blueprint(governance_bp, url_prefix="/governance")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(notes_bp, url_prefix="/notes")

    return app


if __name__ == "__main__":
    from db_bootstrap import ensure_db

    app = create_app()
    ensure_db(app)
    # Dev-friendly default; set FLASK_DEBUG=0 to disable the debugger/reloader
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=app.config["PORT"])
