# app/__init__.py
import os
import stripe
from flask import Flask, render_template

from app.config import Config
from app.extensions import init_extensions, login_manager, db
from app.models import User

from app.services.rag_service import preload_rag, filtrar_melhores_dados_precarregado
from app.services.guardrails import user_can_access


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)

    # --- PRELOAD RAG (só garante que carregou no boot) ---
    preload_rag()

    # --- normaliza DB url postgres ---
    db_url = app.config.get("DATABASE_URL", "sqlite:///saas.db")
    if isinstance(db_url, str) and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    # --- upload folder ---
    upload_folder = app.config.get("UPLOAD_FOLDER", "/tmp")
    app.config["UPLOAD_FOLDER"] = upload_folder
    os.makedirs(upload_folder, exist_ok=True)

    # --- stripe ---
    stripe.api_key = app.config.get("STRIPE_SECRET_KEY", "")

    # --- extensions ---
    init_extensions(app)

    # --- user loader ---
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- error pages ---
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("404.html"), 500

    # ✅ expõe a função RAG pra qualquer módulo/worker usar
    app.filtrar_melhores_dados = filtrar_melhores_dados_precarregado

    # ✅ injeta helper 'access' pro dashboard.html (corrige 'access is undefined')
    @app.context_processor
    def inject_access_helpers():
        def access(user, min_plan):
            return user_can_access(user, (min_plan or "free"))
        return {"access": access}

    # ⚠️ IMPORTANTE:
    # NÃO defina a rota /static/uploads aqui, porque você já define no legacy_app.
    # Se definir nos 2, volta o erro de endpoint duplicado.

    # --- registra rotas do legacy (uma única vez) ---
    from legacy_app import register_routes
    register_routes(app)

    # --- cria tabelas ---
    with app.app_context():
        db.create_all()

    return app


# ✅ necessário pro gunicorn: "gunicorn app:app"
app = create_app()
