import threading
import os
import random
from datetime import datetime, timedelta

from flask import render_template, request, jsonify, redirect, url_for, flash, send_file, send_from_directory
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from app.extensions import db, mail
from app.models import User, Report, Document

from app.constants import AGENTS_CONFIG, PRICE_ID_STARTER, PRICE_ID_PRO, PRICE_ID_AGENCY, PLAN_LEVELS
from app.services.usd_rate_service import get_usd_rate
from app.services.guardrails import user_can_access, get_effective_plan, get_trial_days_left, get_recommendations
from app.workers.heavy_worker import heavy_lifting_worker
from app.workers.video_worker import worker_video_tutorial

# ⚠️ estava faltando no seu legacy: isso precisa existir
pending_validations = {}

# seu semaphore global (mantém igual)
processing_semaphore = threading.BoundedSemaphore(value=1)

def enviar_alerta_admin(app, usuario, motivo, input_texto):
    from flask_mail import Message
    msg = Message(
        subject=f"🚨 BLOQUEIO DE USUÁRIO: {usuario.company_name}",
        recipients=['contact@rendey.store'],
        body=f"USUÁRIO: {usuario.email}\nMOTIVO: {motivo}\nTEXTO: {input_texto}"
    )
    try:
        with app.app_context():
            mail.send(msg)
    except Exception as e:
        print(f"Erro ao enviar alerta: {e}")

def register_routes(app):
    # 🔹 erros
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("404.html"), 500

    # 🔹 static uploads (usa app.config['UPLOAD_FOLDER'])
    @app.route('/static/uploads/<path:filename>')
    def serve_uploads_folder(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/download_video/<path:filename>')
    @login_required
    def download_video_route(filename):
        try:
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        except FileNotFoundError:
            flash("Arquivo expirou ou não foi encontrado.", "danger")
            return redirect('/dashboard')

    # ✅ A PARTIR DAQUI você cola suas rotas antigas, mas:
    # - SEM decorators duplicados
    # - workers/imports vêm de app.workers.*
    # - constants vêm de app.constants
    # - helpers (trial, access etc) vêm de app.services.guardrails

    @app.route('/dashboard')
    @login_required
    def dashboard():
        reports = Report.query.filter_by(user_id=current_user.id)\
            .order_by(Report.date_created.desc()).limit(20).all()

        categories = {
            "Marketing": ['instavideo', 'instapost', 'promo', 'localseo'],
            "Operacional": ['sop', 'waste', 'delivery'],
            "Estratégico": ['persona', 'spy', 'audit', 'menu_eng'],
            "RH": ['job_desc', 'interview']
        }

        recomendacoes = get_recommendations(current_user.company_name or "")
        eff_plan = get_effective_plan(current_user)
        days_left = get_trial_days_left(current_user)

        return render_template(
            "dashboard.html",
            categories=categories,
            recomendações=recomendacoes,
            tools=AGENTS_CONFIG,
            reports=reports,
            user=current_user,
            effective_plan=eff_plan,
            days_left=days_left
        )

    # ... continua colando suas rotas daqui pra baixo ...
    # 🔥 IMPORTANTE:
    # Você PRECISA remover uma das rotas /wait/<int:...> duplicadas do legacy.

# ✅ REGISTRA NO IMPORT (se você continuar importando legacy_app no app.py)
from flask import current_app

try:
    # registra uma vez no startup
    register_routes(current_app._get_current_object())
except Exception:
    # quando importar fora de app context (alguns runners), não quebra
    pass
