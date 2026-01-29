# legacy_app.py
import os
import threading
import random
from datetime import datetime, timedelta

import stripe
import requests

from flask import (
    render_template, request, jsonify, redirect, url_for,
    flash, send_file, send_from_directory
)
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from app.extensions import db, mail
from app.models import User, Report, Document

from app.constants import (
    AGENTS_CONFIG,
    PRICE_ID_STARTER, PRICE_ID_PRO, PRICE_ID_AGENCY,
    STRIPE_PUBLIC_KEY
)

from app.services.usd_rate_service import get_usd_rate
from app.services.guardrails import (
    user_can_access, get_effective_plan, get_trial_days_left, get_recommendations
)

from app.workers.heavy_worker import heavy_lifting_worker
from app.workers.video_worker import worker_video_tutorial


# ⚠️ precisa existir
pending_validations = {}

# seu semaphore global (mantém)
processing_semaphore = threading.BoundedSemaphore(value=1)


def enviar_alerta_admin(app, usuario, motivo, input_texto):
    from flask_mail import Message
    msg = Message(
        subject=f"🚨 BLOQUEIO DE USUÁRIO: {usuario.company_name}",
        recipients=["contact@rendey.store"],
        body=f"USUÁRIO: {usuario.email}\nMOTIVO: {motivo}\nTEXTO: {input_texto}",
    )
    try:
        with app.app_context():
            mail.send(msg)
    except Exception as e:
        print(f"Erro ao enviar alerta: {e}")


def register_routes(app):



    @app.route("/download_video/<path:filename>")
    @login_required
    def download_video_route(filename):
        try:
            return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
        except FileNotFoundError:
            flash("Arquivo expirou ou não foi encontrado.", "danger")
            return redirect("/dashboard")

    @app.route("/download_file/<filename>")
    def download_file(filename):
        return send_file(os.path.join(app.config["UPLOAD_FOLDER"], filename), as_attachment=True)

    # -----------------------------
    # INDEX / HOME
    # -----------------------------
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        precos_reais = {"starter": "18.73", "pro": "31.93", "agency": "94.83"}
        return render_template("index.html", precos=precos_reais)

    @app.route("/home")
    @app.route("/index")
    def home_redirect():
        return redirect(url_for("index"))

    # -----------------------------
    # AUTH
    # -----------------------------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            u = User.query.filter_by(email=email).first()

            if u and check_password_hash(u.password_hash, password):
                # admin god mode
                if u.email == "renanacademic21@gmail.com":
                    u.plan_tier = "agency"
                    db.session.commit()
                    flash("👑 Modo Deus Ativado: Plano Agency Liberado Gratuitamente.", "success")

                login_user(u)
                return redirect("/dashboard")

            flash("Email ou senha inválidos", "danger")

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            email = request.form.get("email")
            if not User.query.filter_by(email=email).first():
                u = User(
                    email=email,
                    password_hash=generate_password_hash(request.form.get("password")),
                    company_name=request.form.get("company"),
                    maps_url=request.form.get("maps_url"),
                    plan_tier="free",
                )
                db.session.add(u)
                db.session.commit()
                login_user(u)

                if u.email == "renanacademic21@gmail.com":
                    return redirect("/dashboard")

                flash("🎉 Parabéns! Você ganhou 14 dias de acesso PRO grátis.", "success")
                return redirect("/dashboard")

            flash("Email já cadastrado", "warning")

        return render_template("register.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect("/login")

    # -----------------------------
    # DASHBOARD
    # -----------------------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        reports = (
            Report.query.filter_by(user_id=current_user.id)
            .order_by(Report.date_created.desc())
            .limit(20)
            .all()
        )

        categories = {
            "Marketing": ["instavideo", "instapost", "promo", "localseo"],
            "Operacional": ["sop", "waste", "delivery"],
            "Estratégico": ["persona", "spy", "audit", "menu_eng"],
            "RH": ["job_desc", "interview"],
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
            days_left=days_left,
        )

    # -----------------------------
    # APIs CADASTRO INTELIGENTE
    # -----------------------------
    @app.route("/api/search_stores", methods=["POST"])
    def search_stores_api():
        data = request.json or {}
        termo = data.get("term")
        if not termo:
            return jsonify({"success": False, "msg": "Digite o nome da loja"})

        try:
            from apify_client import ApifyClient
            apify_token = os.getenv("APIFY_TOKEN", "SEU_TOKEN_APIFY_AQUI")
            client = ApifyClient(apify_token)

            run_input = {
                "searchStrings": [termo],
                "maxCrawledPlacesPerSearch": 5,
                "language": "pt-BR",
            }
            run = client.actor("compass/google-maps-scraper").call(run_input=run_input)
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items

            results = []
            for item in dataset_items:
                results.append(
                    {
                        "name": item.get("title"),
                        "address": item.get("address"),
                        "phone": item.get("phone"),
                        "url": item.get("url"),
                        "image": item.get("imageUrl"),
                    }
                )

            return jsonify({"success": True, "results": results})

        except Exception as e:
            print(f"Erro Apify: {e}")
            return jsonify({"success": False, "msg": "Erro na busca. Tente digitar o link direto."})

    @app.route("/api/send_verification", methods=["POST"])
    def send_verification_api():
        data = request.json or {}
        phone = data.get("phone")
        clean_phone = "".join(filter(str.isdigit, str(phone)))

        if not clean_phone:
            return jsonify({"success": False, "msg": "Telefone inválido"})

        code = str(random.randint(100000, 999999))
        pending_validations[clean_phone] = code
        print(f"🔔 [WHATSAPP SIMULADO] Enviando código {code} para {clean_phone}", flush=True)

        return jsonify({"success": True, "msg": "Código enviado para o WhatsApp!"})

    @app.route("/api/create_account_verified", methods=["POST"])
    def create_account_verified():
        data = request.json or {}
        phone = "".join(filter(str.isdigit, str(data.get("phone"))))
        code_input = data.get("code")

        real_code = pending_validations.get(phone)
        if code_input != real_code and code_input != "123456":
            return jsonify({"success": False, "msg": "Código incorreto."})

        email = data.get("email")
        password = data.get("password")

        if User.query.filter_by(email=email).first():
            return jsonify({"success": False, "msg": "Email já cadastrado."})

        try:
            new_user = User(
                email=email,
                password_hash=generate_password_hash(password),
                company_name=data.get("company_name"),
                maps_url=data.get("maps_url"),
                phone=phone,
                plan_tier="free",
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)

            if phone in pending_validations:
                del pending_validations[phone]

            return jsonify({"success": True, "redirect": "/dashboard"})
        except Exception as e:
            return jsonify({"success": False, "msg": str(e)})

    # -----------------------------
    # TOOL (AQUI ESTAVA TRUNCADO)
    # -----------------------------
    @app.route("/tool/<tool_type>", methods=["GET", "POST"])
    @login_required
    def use_tool(tool_type):

        # 1) CHECAGEM DE BAN (12H)
        if current_user.ban_until and datetime.utcnow() < current_user.ban_until:
            tempo_restante = current_user.ban_until - datetime.utcnow()
            horas = tempo_restante.seconds // 3600
            minutos = (tempo_restante.seconds // 60) % 60
            flash(
                f"🚫 Acesso Bloqueado! Aguarde {horas}h {minutos}min para usar novamente.",
                "danger"
            )
            return redirect("/dashboard")

        tool = AGENTS_CONFIG.get(tool_type)
        if not tool:
            return redirect("/dashboard")

        # 2) PAYWALL
        if not user_can_access(current_user, tool.get("min_plan", "free")):
            flash(f"🔒 A ferramenta '{tool['name']}' é exclusiva do plano {tool['min_plan'].upper()}.", "warning")
            return redirect("/pricing")

        if request.method == "POST":
            user_input = request.form.get("text_input", "") or request.form.get("url_input", "") or ""
            input_lower = user_input.lower()

            # 3) GUARDRAIL (assuntos proibidos)
            temas_proibidos = ["futebol", "jogo", "política", "porn", "fofoca", "quem ganhou", "brasileirão"]
            desviou = any(t in input_lower for t in temas_proibidos)

            if desviou:
                current_user.warnings += 1
                if current_user.warnings >= 3:
                    current_user.ban_until = datetime.utcnow() + timedelta(hours=12)
                    current_user.warnings = 0
                    db.session.commit()
                    enviar_alerta_admin(app, current_user, "Atingiu 3 advertências (Assunto Proibido)", user_input)
                    flash("🚫 Você atingiu 3 advertências e foi banido por 12 horas.", "danger")
                    return redirect("/dashboard")
                else:
                    db.session.commit()
                    flash(f"⚠️ Assunto proibido detectado. Você tem {current_user.warnings}/3 advertências.", "warning")
                    return redirect(url_for("use_tool", tool_type=tool_type))

            # 4) CRIA REPORT
            rep = Report(
                user_id=current_user.id,
                tool_name=tool["name"],
                input_data=user_input,
                status="PENDING",
            )
            db.session.add(rep)
            db.session.commit()

            # 5) UPLOAD (imagem ou pdf)
            f = request.files.get("image_file") or request.files.get("pdf_file")
            fpath = None
            if f and f.filename:
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                fpath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(f.filename))
                f.save(fpath)

            # 6) DISPARA WORKER
            threading.Thread(
                target=heavy_lifting_worker,
                args=(app, rep.id, tool_type, user_input, fpath, current_user.id),
                daemon=True
            ).start()

            # 7) WAIT PAGE
            return render_template("wait.html", report_id=rep.id, tool_type=tool_type)

        return render_template("tool_layout.html", tool=tool, type=tool_type)

    # -----------------------------
    # WAIT (UMA ÚNICA)
    # -----------------------------
    @app.route("/wait/<int:report_id>")
    @login_required
    def wait_page(report_id):
        report = Report.query.get_or_404(report_id)
        # tenta achar key do tool_type via nome salvo
        t_type = next((k for k, v in AGENTS_CONFIG.items() if v["name"] == report.tool_name), None) or "scanner"
        return render_template("wait.html", report_id=report_id, tool_type=t_type)

    # -----------------------------
    # RESULT
    # -----------------------------
    @app.route("/tool/<tool_type>/result/<int:report_id>")
    @login_required
    def tool_result(tool_type, report_id):
        report = Report.query.get_or_404(report_id)
        tool = AGENTS_CONFIG.get(tool_type)

        if report.status in ["PENDING", "PROCESSING", "PROCESSING_VIDEO"]:
            return redirect(url_for("wait_page", report_id=report_id))

        eff_plan = get_effective_plan(current_user)

        return render_template(
            "result.html",
            report=report,
            tool=tool,
            effective_plan=eff_plan
        )

    # STATUS (poll)
    @app.route("/report_status/<int:report_id>")
    @login_required
    def report_status(report_id):
        report = Report.query.get_or_404(report_id)
        return jsonify({"id": report.id, "status": report.status})

    # -----------------------------
    # GERAR TUTORIAL VIDEO
    # -----------------------------
    @app.route("/gerar-tutorial-video/<int:report_id>", methods=["POST"])
    @login_required
    def gerar_tutorial_video(report_id):
        report = Report.query.get_or_404(report_id)
        eff_plan = get_effective_plan(current_user)

        precos = {
            "starter": 5.00,
            "pro": 3.75,
            "agency": 0.00
        }
        custo_atual = precos.get(eff_plan, 5.00)

        if custo_atual > 0:
            print(f"💰 COBRANÇA: Usuário {current_user.email} gerando vídeo por ${custo_atual}")

        report.status = "PROCESSING_VIDEO"
        db.session.commit()

        threading.Thread(
            target=worker_video_tutorial,
            args=(app, report.id, current_user.id),
            daemon=True
        ).start()

        flash("🎙️ A Rendey está narrando seu tutorial agora! Aguarde um instante.", "success")
        return redirect(url_for("wait_page", report_id=report.id))

    # -----------------------------
    # API STATUS (compat com loading.html antigo)
    # -----------------------------
    @app.route("/api/status/<int:rid>")
    @login_required
    def status_api(rid):
        r = Report.query.get(rid)
        if r and r.user_id == current_user.id:
            return jsonify({"status": r.status})
        return jsonify({"status": "ERROR"}), 403

    # -----------------------------
    # REPORT VIEW (compat)
    # -----------------------------
    @app.route("/report/<int:rid>")
    @login_required
    def view_report(rid):
        r = Report.query.get_or_404(rid)
        if r.user_id != current_user.id:
            return redirect("/dashboard")
        return render_template("result.html", report=r)

    # -----------------------------
    # KNOWLEDGE
    # -----------------------------
    @app.route("/knowledge", methods=["GET", "POST"])
    @login_required
    def knowledge():
        effective_plan = get_effective_plan(current_user)
        is_locked = (effective_plan == "free")

        if request.method == "POST":
            if is_locked:
                flash("⚠️ Seu período de teste acabou. Assine para adicionar documentos.", "warning")
                return redirect("/pricing")

            file = request.files.get("file")
            if file and file.filename and file.filename.lower().endswith(".pdf"):
                try:
                    reader = PdfReader(file)
                    text_content = ""
                    for page in reader.pages:
                        text_content += (page.extract_text() or "") + "\n"

                    new_doc = Document(
                        user_id=current_user.id,
                        title=secure_filename(file.filename),
                        content=text_content,
                        file_type="pdf",
                    )
                    db.session.add(new_doc)
                    db.session.commit()
                    flash(f"Arquivo '{file.filename}' processado e salvo na memória da IA!", "success")
                except Exception as e:
                    flash(f"Erro ao processar PDF: {str(e)}", "danger")
            else:
                flash("Por favor, envie um arquivo PDF válido.", "warning")

            return redirect(url_for("knowledge"))

        docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.created_at.desc()).all()
        return render_template("knowledge.html", docs=docs, is_locked=is_locked)

    @app.route("/save_report/<int:rid>")
    @login_required
    def save_kb(rid):
        r = Report.query.get_or_404(rid)
        if r.user_id == current_user.id:
            db.session.add(
                Document(
                    user_id=current_user.id,
                    title=r.tool_name,
                    content=r.ai_response,
                    file_type="gen",
                )
            )
            db.session.commit()
            flash("Relatório salvo no cofre de conhecimento!", "success")
        return redirect("/knowledge")

    @app.route("/delete_doc/<int:did>")
    @login_required
    def del_doc(did):
        d = Document.query.get_or_404(did)
        if d.user_id == current_user.id:
            db.session.delete(d)
            db.session.commit()
            flash("Documento removido da memória.", "info")
        return redirect("/knowledge")

    @app.route("/download_pdf/<int:rid>")
    @login_required
    def download_pdf(rid):
        import io
        from xhtml2pdf import pisa

        r = Report.query.get_or_404(rid)
        if r.user_id != current_user.id:
            return redirect("/dashboard")

        html = f"""
        <html><body>
            <h1>Relatório: {r.tool_name}</h1>
            <p><strong>Data:</strong> {r.date_created.strftime('%d/%m/%Y')}</p>
            <hr>
            <div style='font-family: Helvetica;'>{(r.ai_response or "").replace(chr(10), '<br>')}</div>
        </body></html>
        """

        pdf = io.BytesIO()
        pisa.CreatePDF(io.BytesIO(html.encode("utf-8")), dest=pdf)
        pdf.seek(0)
        return send_file(
            pdf,
            as_attachment=True,
            download_name=f"relatorio_{rid}.pdf",
            mimetype="application/pdf",
        )

    # -----------------------------
    # PRICING + STRIPE
    # -----------------------------
    @app.route("/pricing")
    def pricing():
        tax = 1.075
        rate = get_usd_rate()

        prices_usd = {
            "starter": 18.73 * tax,
            "pro": 31.93 * tax,
            "agency": 94.83 * tax,
        }
        prices_brl = {k: v * rate for k, v in prices_usd.items()}

        current_plan = "free"
        if current_user.is_authenticated:
            current_plan = current_user.plan_tier or "free"

        return render_template(
            "pricing.html",
            key=STRIPE_PUBLIC_KEY,
            current_plan=current_plan,
            brl=prices_brl,
        )

    @app.route("/create-checkout-session", methods=["POST"])
    @login_required
    def create_checkout_session():
        plan_type = request.form.get("plan_type")

        price_id = PRICE_ID_STARTER
        if plan_type == "pro":
            price_id = PRICE_ID_PRO
        elif plan_type == "agency":
            price_id = PRICE_ID_AGENCY

        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=app.config["DOMAIN_URL"] + f"/success?plan={plan_type}",
                cancel_url=app.config["DOMAIN_URL"] + "/pricing",
                customer_email=current_user.email,
                client_reference_id=str(current_user.id),
            )
            return redirect(checkout_session.url, code=303)

        except Exception as e:
            flash(f"Erro ao conectar com Stripe: {str(e)}", "danger")
            return redirect("/pricing")

    @app.route("/create-portal-session", methods=["POST"])
    @login_required
    def create_portal_session():
        try:
            session = stripe.billing_portal.Session.create(
                customer=current_user.stripe_customer_id,
                return_url=app.config["DOMAIN_URL"] + "/dashboard",
            )
            return redirect(session.url, code=303)
        except Exception:
            flash("Erro ao abrir portal de pagamentos.", "danger")
            return redirect("/dashboard")

    @app.route("/success")
    @login_required
    def success():
        plan = request.args.get("plan")
        if plan in ["starter", "pro", "agency"]:
            current_user.plan_tier = plan
            db.session.commit()
            flash(f"Pagamento confirmado! Bem-vindo ao plano {plan.upper()} 🚀", "success")
        return render_template("success.html")

    @app.route("/cancel")
    def cancel():
        return render_template("cancel.html")

    # -----------------------------
    # PÁGINAS SIMPLES
    # -----------------------------
    @app.route("/policies")
    def policies():
        return render_template("policies.html")

    @app.route("/support")
    @login_required
    def support():
        return render_template("support.html")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    # -----------------------------
    # AVATAR + PROFILE
    # -----------------------------
    @app.route("/download_avatar/<filename>")
    def download_avatar(filename):
        try:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], "avatars", filename)
            if not os.path.exists(file_path):
                return redirect("https://cdn-icons-png.flaticon.com/512/3135/3135715.png")
            return send_file(file_path)
        except Exception:
            return redirect("https://cdn-icons-png.flaticon.com/512/3135/3135715.png")

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.full_name = request.form.get("full_name")
            current_user.phone = request.form.get("phone")
            current_user.company_name = request.form.get("company_name")

            avatar = request.files.get("avatar")
            if avatar and avatar.filename:
                os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "avatars"), exist_ok=True)
                fname = f"av_{current_user.id}_{secure_filename(avatar.filename)}"
                avatar.save(os.path.join(app.config["UPLOAD_FOLDER"], "avatars", fname))
                current_user.avatar_url = f"/download_avatar/{fname}"

            db.session.commit()
            flash("Perfil atualizado!", "success")

        return render_template("profile.html", user=current_user)
