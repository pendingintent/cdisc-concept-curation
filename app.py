from flask import Flask
from config import Config
from extensions import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from routes.dashboard import bp as dashboard_bp
    from routes.ingestion import bp as ingestion_bp
    from routes.bc import bp as bc_bp
    from routes.ncit import bp as ncit_bp
    from routes.specializations import bp as specializations_bp
    from routes.governance import bp as governance_bp
    from routes.audit import bp as audit_bp

    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(ingestion_bp, url_prefix='/ingestion')
    app.register_blueprint(bc_bp, url_prefix='/bc')
    app.register_blueprint(ncit_bp, url_prefix='/ncit')
    app.register_blueprint(specializations_bp, url_prefix='/specializations')
    app.register_blueprint(governance_bp, url_prefix='/governance')
    app.register_blueprint(audit_bp, url_prefix='/audit')

    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
