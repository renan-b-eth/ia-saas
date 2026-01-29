# app/__init__.py
import os
import stripe
from flask import Flask, send_from_directory, render_template
from app.config import Config
from app.extensions import init_extensions, login_manager, db
from app.models import User

from app.services.rag_service import preload_rag, filtrar_melhores_dados_precarregado


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)

    # --- PRELOAD RAG (só garante que carregou) ---
    preload_rag()

    # --- normaliza DB url postgres ---
    db_url = app.config.get("DATABASE_URL", "sqlite:///saas.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    # --- upload folder ---
    os.makedirs(app.config.get("UPLOAD_FOLDER", "/tmp"), exist_ok=True)

    # --- stripe ---
    stripe.api_key = app.config.get("STRIPE_SECRET_KEY", "")

    # --- extensions ---
    init_extensions(app)

    # --- user loader ---
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- serve uploads ---
    @app.route("/static/uploads/<path:filename>")
    def serve_uploads_folder(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # --- error pages ---
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("404.html"), 500

    # ✅ aqui você expõe a função CERTA pro resto do app
    app.filtrar_melhores_dados = filtrar_melhores_dados_precarregado

    # --- registra rotas do legacy (uma única vez) ---
    from legacy_app import register_routes
    register_routes(app)

    # --- cria tabelas ---
    with app.app_context():
        db.create_all()

    return app


# ✅ ESSA LINHA É O QUE RESOLVE O "Failed to find attribute 'app' in 'app'"
# Gunicorn (app:app) precisa disso:
app = create_app()
