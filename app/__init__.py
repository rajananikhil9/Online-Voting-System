
from datetime import datetime

from flask import Flask, render_template

from config import Config
from models import db

from app.routes.student_import import student_import_bp
from app.routes.student_dashboard import student_dashboard_bp
from app.routes.admin_auth import admin_auth_bp
from app.routes.auth import auth_bp
from app.routes.elections import elections_bp
from app.routes.admin import admin_dashboard_bp
from app.routes.voting import voting_bp
from app.routes.results import results_bp


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="../static",
    )

    app.config.from_object(Config)

    db.init_app(app)

    # Register routes
    app.register_blueprint(student_import_bp)
    app.register_blueprint(student_dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(elections_bp)
    app.register_blueprint(admin_dashboard_bp)
    app.register_blueprint(voting_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(admin_auth_bp)

    # Make the current year available to templates
    @app.context_processor
    def inject_current_year():
        return {"current_year": datetime.now().year}

    # Public home page
    @app.route("/")
    def home():
        return render_template("index.html")

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    return app

