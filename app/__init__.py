import os
import stripe
from flask import Flask, send_from_directory, render_template
from app.config import Config
from app.extensions import init_extensions, login_manager, db
from app.models import User
from app.services.rag_service import preload_rag

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)

    # normaliza DB url postgres
    db_url = app.config["DATABASE_URL"]
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    # upload folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # stripe
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]

    # extensions
    init_extensions(app)

    # user loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # serve uploads
    @app.route("/static/uploads/<path:filename>")
    def serve_uploads_folder(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # error pages
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("404.html"), 500

    # preload rag (retorna função)
    app.filtrar_melhores_dados = preload_rag()

    # registra rotas do legado (vamos criar já já)
    from legacy_app import register_routes
    register_routes(app)

    # cria tabelas
    with app.app_context():
        db.create_all()

    return app
