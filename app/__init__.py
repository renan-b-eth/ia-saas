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

    # Preload do RAG no boot (não retorna função, só aquece a RAM)
    preload_rag()

    # Normaliza postgres URL (HF/Heroku style)
    db_url = app.config.get("DATABASE_URL", "sqlite:///saas.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    # Upload folder (HF escreve só em /tmp)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Stripe
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]

    # Extensions
    init_extensions(app)

    # Login loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Serve uploads via rota (compat com seu frontend)
    @app.route("/static/uploads/<path:filename>")
    def serve_uploads_folder(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # Error pages
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("404.html"), 500

    # Disponibiliza o filtro do RAG no app (workers usam isso)
    app.filtrar_melhores_dados = filtrar_melhores_dados_precarregado

    # Registra legado (todas as rotas)
    from legacy_app import register_routes
    register_routes(app)

    return app
