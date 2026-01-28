import os
import threading
import gc # Garbage Collector
import time
import json
import stripe 
from datetime import datetime, timedelta
import requests
from flask_mail import Mail, Message
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_talisman import Talisman
import edge_tts
import asyncio

# Imports de Funcionalidades Locais
from modules.video_maker import criar_video_reels
from pypdf import PdfReader 

# --- [OTIMIZAÇÃO CRÍTICA] PRE-LOAD DO MOTOR NA RAM ---
# Isso impede o erro "BertModel LOAD REPORT" dentro do worker que trava o app
async def gerar_audio_edge(texto, path):
    # 'pt-BR-AntonioNeural' é excelente para consultoria
    communicate = edge_tts.Communicate(texto, "pt-BR-AntonioNeural")
    await communicate.save(path)
print("🚀 Pré-carregando motor de inteligência estratégica (all-MiniLM-L6-v2)...", flush=True)
try:
    from rag_engine import filtrar_melhores_dados 
    # Força o carregamento imediato na RAM para não atrasar o worker depois
    filtrar_melhores_dados("inicialização", ["contexto de teste"])
    print("✅ Motor de RAG carregado com sucesso na RAM!")
except Exception as e:
    print(f"⚠️ Erro ao pré-carregar motor: {e}")
    def filtrar_melhores_dados(query, docs, top_k=5): return docs[:top_k]

# --- 1. CONFIGURAÇÕES GERAIS ---
app = Flask(__name__)
@app.route('/static/uploads/<path:filename>')
def serve_uploads_folder(filename):
    # Força o Flask a ler da pasta configurada no UPLOAD_FOLDER (que é /tmp/...)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Use /tmp no Hugging Face pois é o único lugar com permissão de escrita garantida
UPLOAD_FOLDER = '/tmp/uploads' 
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
processing_semaphore = threading.BoundedSemaphore(value=1)
app.secret_key = os.getenv("SECRET_KEY", "segredo_master_renan_saas_2026")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# --- 2. CONFIGURAÇÃO STRIPE (PAGAMENTOS) ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_live_SUA_CHAVE_AQUI")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "pk_live_SUA_CHAVE_AQUI")
PRICE_ID_STARTER = "price_1StrGmL5fMgQY8LOBZiFBLJ9"
PRICE_ID_PRO = "price_1StrHeL5fMgQY8LOCQbOgC71"
PRICE_ID_AGENCY = "price_1StrIWL5fMgQY8LOR75qDWbv"
YOUR_DOMAIN = os.getenv("DOMAIN_URL", "https://renan-b-eth-saas-varejo.hf.space")

# Configurações Mail Namecheap
app.config['MAIL_SERVER'] = 'mail.privateemail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'contact@rendey.store'
app.config['MAIL_PASSWORD'] = '@@Dolarizandose2026'
app.config['MAIL_DEFAULT_SENDER'] = 'contact@rendey.store'
mail = Mail(app)

@app.errorhandler(404)
def page_not_found(e):
    # Retorna o template 404 e o código de status 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    # Opcional: Você pode usar a mesma página ou criar uma 500.html para erros de servidor
    return render_template('404.html'), 500

@app.route('/download_video/<path:filename>')
@login_required
def download_video_route(filename):
    try:
        # Tenta baixar da pasta temporária (/tmp)
        return send_from_directory(
            app.config['UPLOAD_FOLDER'], 
            filename, 
            as_attachment=True
        )
    except FileNotFoundError:
        flash("Arquivo expirou ou não foi encontrado.", "danger")
        return redirect('/dashboard')
    
def enviar_alerta_admin(usuario, motivo, input_texto):
    msg = Message(
        subject=f"🚨 BLOQUEIO DE USUÁRIO: {usuario.company_name}",
        recipients=['contact@rendey.store'],
        body=f"USUÁRIO: {usuario.email}\nMOTIVO: {motivo}\nTEXTO: {input_texto}"
    )
    try:
        with app.app_context(): mail.send(msg)
    except Exception as e: print(f"Erro ao enviar alerta: {e}")

# --- 3. CONFIGURAÇÃO BANCO DE DADOS E UPLOADS ---
database_url = os.getenv("DATABASE_URL", "sqlite:///saas.db")
if database_url.startswith("postgres://"): 
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True, "pool_recycle": 300}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
Talisman(app, content_security_policy=None, force_https=False)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 4. MODELOS DO BANCO DE DADOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(150))
    maps_url = db.Column(db.String(500))
    plan_tier = db.Column(db.String(50), default='free') 
    stripe_customer_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    avatar_url = db.Column(db.String(500), default='/static/default-avatar.png')
    warnings = db.Column(db.Integer, default=0)
    ban_until = db.Column(db.DateTime, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tool_name = db.Column(db.String(100))
    tool_description = db.Column(db.Text)
    tool_url = db.Column(db.String(500)) 
    input_data = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    status = db.Column(db.String(20), default="PENDING")
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    file_type = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def worker_video_tutorial(app_obj, report_id, user_id):
    """
    WORKER V5 (LINK HTML DIRETO + FIX PERMISSION):
    - Gera o vídeo usando pasta temporária correta (/tmp).
    - Salva na memória.
    - Retorna um HTML PRONTO com botão de download (funciona em qualquer layout).
    """
    with app_obj.app_context():
        from moviepy.editor import ImageClip, AudioFileClip
        from openai import OpenAI
        import edge_tts
        import asyncio
        import requests
        import os
        import datetime
        
        def log_status(msg):
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🎬 [VIDEO-WORKER] {msg}", flush=True)

        try:
            log_status(f"🚀 INICIANDO VÍDEO PARA REPORT: {report_id}")
            report = Report.query.get(report_id)
            
            # 1. Roteiro (Gera o texto)
            api_key = os.getenv("NVIDIA_API_KEY")
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
            prompt_sistema = "Você é um Diretor de Marketing. Crie um roteiro curto (max 40s) para vídeo viral. Responda APENAS o texto falado."
            texto_base = report.input_data if report.input_data else report.tool_description
            
            completion = client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": f"Roteiro sobre: {texto_base}"}],
                temperature=0.7, max_tokens=800
            )
            roteiro = completion.choices[0].message.content.strip()
            log_status("📝 Roteiro gerado.")

            # 2. Áudio (Cria o som)
            upload_folder = app_obj.config['UPLOAD_FOLDER']
            audio_path = os.path.join(upload_folder, f"audio_{report_id}.mp3")
            asyncio.run(edge_tts.Communicate(roteiro, "pt-BR-AntonioNeural").save(audio_path))

            # 3. Renderização de Vídeo (COM O FIX DE PERMISSÃO)
            video_filename = f"video_viral_{report_id}.mp4"
            video_path_final = os.path.join(upload_folder, video_filename)
            foto_base = os.path.join(upload_folder, "consultor_base.jpg")
            
            # IMPORTANTE: Caminho explícito para o temp de áudio na pasta /tmp
            temp_audio_path = os.path.join(upload_folder, f"temp_audio_{report_id}.m4a")

            if not os.path.exists(foto_base):
                 r = requests.get("https://raw.githubusercontent.com/renan-b-eth/rendey-assets/main/consultor.jpg")
                 with open(foto_base, 'wb') as f: f.write(r.content)

            log_status("🎬 Renderizando MP4...")
            audio_clip = AudioFileClip(audio_path)
            duration = max(5, audio_clip.duration)
            final_clip = ImageClip(foto_base).set_duration(duration).set_audio(audio_clip).set_fps(24)
            
            final_clip.write_videofile(
                video_path_final, 
                codec='libx264', 
                audio_codec='aac', 
                preset='ultrafast', 
                ffmpeg_params=['-pix_fmt', 'yuv420p'], 
                
                # FIX CRÍTICO MANTIDO AQUI:
                temp_audiofile=temp_audio_path, 
                remove_temp=True, 
                logger=None
            )

            # 4. Salvar na Memória (Knowledge Base)
            try:
                new_doc = Document(
                    user_id=user_id,
                    title=f"🎬 Vídeo Gerado (#{report_id})",
                    content=f"Roteiro:\n{roteiro}\n\nArquivo: {video_filename}",
                    file_type='video_script'
                )
                db.session.add(new_doc)
                db.session.commit()
            except: pass

            # --- 5. A SOLUÇÃO: HTML GERADO NO BACKEND ---
            # Isso cria o botão direto na resposta, sem depender do frontend interpretar códigos
            botao_html = f"""
            <div style="background:#111827; padding:40px; border-radius:24px; text-align:center; border:1px solid #374151; margin-top:20px;">
                <div style="font-size: 50px; margin-bottom: 20px;">🎥</div>
                <h2 style="color:#fff; margin-bottom:10px; font-family:sans-serif;">Vídeo Renderizado com Sucesso!</h2>
                <p style="color:#9CA3AF; margin-bottom:30px; font-family:sans-serif;">Seu viral está pronto. Clique no botão abaixo para baixar o arquivo MP4.</p>
                
                <a href="/download_video/{video_filename}" target="_blank" 
                   style="background: linear-gradient(to right, #2563EB, #4F46E5); color:white; padding:18px 40px; text-decoration:none; border-radius:12px; font-weight:bold; font-size:18px; display:inline-block; box-shadow: 0 10px 25px -5px rgba(59, 130, 246, 0.5);">
                   ⬇️ BAIXAR VÍDEO AGORA
                </a>
                
                <hr style="border-color:#374151; margin:40px 0;">
                
                <div style="text-align:left; color:#D1D5DB; background:#1F2937; padding:20px; border-radius:12px; border:1px solid #374151;">
                    <strong style="color:#60A5FA; text-transform:uppercase; font-size:12px; letter-spacing:1px;">Roteiro Gerado:</strong><br><br>
                    <em style="line-height:1.6;">"{roteiro}"</em>
                </div>
            </div>
            """
            
            report.ai_response = botao_html
            report.status = "COMPLETED"
            db.session.commit()
            log_status("🏆 SUCESSO! HTML ENVIADO.")

        except Exception as e:
            log_status(f"💥 ERRO: {str(e)}")
            report.status = "ERROR"
            report.ai_response = f"Erro técnico: {str(e)}"
            db.session.commit()
# --- 6. HIERARQUIA DE PLANOS ---
PLAN_LEVELS = {'free': 0, 'starter': 1, 'pro': 2, 'agency': 3}
# --- [NOVO] LÓGICA DO TRIAL (14 DIAS) ---

def get_recommendations(company_name):
    # Lógica simples de palavras-chave para nichos
    name = company_name.lower()
    if any(x in name for x in ['pizzaria', 'restaurante', 'hamburgueria', 'café', 'doce']):
        return ['menu_eng', 'waste', 'delivery', 'instavideo']
    elif any(x in name for x in ['loja', 'roupa', 'fashion', 'boutique', 'calcado']):
        return ['persona', 'instapost', 'spy', 'visual_merch']
    elif any(x in name for x in ['barbearia', 'salão', 'estetica']):
        return ['upsell', 'localseo', 'review_reply', 'instavideo']
    return ['instavideo', 'promo', 'persona'] # Padrão

def get_effective_plan(user):
    """
    Calcula o plano REAL do usuário.
    1. Se for o Admin (renanacademic21) -> Agency
    2. Se tiver pago (starter/pro/agency) -> Retorna o plano pago
    3. Se for 'free' e conta criada há menos de 14 dias -> Retorna 'pro' (Trial)
    4. Se for 'free' e conta criada há mais de 14 dias -> Retorna 'free' (Bloqueado)
    """
    # Backdoor do Chefe
    if user.email == "renanacademic21@gmail.com": 
        return 'agency'
    
    # Se já é pagante, respeita o plano
    if user.plan_tier in ['starter', 'pro', 'agency']:
        return user.plan_tier
    
    # Lógica do Trial
    if user.created_at:
        dias_de_vida = (datetime.utcnow() - user.created_at).days
        if dias_de_vida < 14:
            return 'pro' # Liberado temporariamente para viciar o usuário
            
    return 'free' # Trial expirou, bloqueia recursos avançados

def get_trial_days_left(user):
    """Retorna quantos dias faltam para acabar o trial"""
    # Se já pagou, não tem trial
    if user.plan_tier != 'free': return 0
    # Se não tem data (conta muito antiga ou bug), assume 0
    if not user.created_at: return 0
    
    dias = (datetime.utcnow() - user.created_at).days
    restante = 14 - dias
    return max(0, restante)

def user_can_access(user, tool_min_plan):
    """
    Verifica se o usuário tem nível suficiente para usar a ferramenta.
    Agora usa o 'plano efetivo' (considerando o trial) e não apenas o do banco.
    """
    effective_plan = get_effective_plan(user)
    u_level = PLAN_LEVELS.get(effective_plan, 0)
    t_level = PLAN_LEVELS.get(tool_min_plan, 0) # Se não tiver min_plan, assume 0 (free)
    return u_level >= t_level

def get_usd_rate():
    """Busca a cotação atual do dólar via API pública"""
    try:
        response = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL")
        data = response.json()
        return float(data['USDBRL']['bid'])
    except Exception as e:
        print(f"Erro ao buscar câmbio: {e}")
        return 5.50  # Valor de segurança caso a API falhe

# LISTA COMPLETA DE AGENTES (Não removi nenhum!)
AGENTS_CONFIG = {
    # --- PLANO AGENCY ---
    'instavideo': {
        'name': 'Gerador de Reels Viral', 
        'icon': '🎬', 
        'type': 'video', 
        'prompt': 'Crie um roteiro de vídeo curto, dinâmico e com ganchos virais para Instagram/TikTok.',
        'min_plan': 'agency',
        'example_input': 'Promoção de Queima de Estoque de Inverno: Todas as jaquetas com 50% OFF, apenas neste fim de semana.'
    },
    
    # --- PLANO PRO ---
    'scanner': {
        'name': 'Scanner de Preços (Foto)', 
        'icon': '📸', 
        'type': 'scanner_price', 
        'prompt': 'Analise a foto, identifique o produto exato e busque preços online.',
        'min_plan': 'pro',
        'example_input': '(Envie a foto do produto) Identifique este vinho e me diga se o preço que estou pagando (R$ 80,00) está justo.'
    },
    'price': {
        'name': 'Caçador de Preços (Busca)', 
        'icon': '💰', 
        'type': 'shopping', 
        'prompt': 'Faça um ranking de preços online para este produto no mercado brasileiro.',
        'min_plan': 'pro',
        'example_input': 'iPhone 15 Pro Max 256GB Titânio Natural'
    },
    'stock': {
        'name': 'Gestor de Estoque (Foto)', 
        'icon': '📦', 
        'type': 'image', 
        'prompt': 'Analise a foto da prateleira, estime a quantidade de itens e sugira reposição baseada em organização visual.',
        'min_plan': 'pro',
        'example_input': '(Envie a foto da prateleira) Conte quantas latas de refrigerante existem e se parecem organizadas.'
    },
    'spy': {
        'name': 'Espião de Concorrente', 
        'icon': '🕵️', 
        'type': 'url_input', 
        'prompt': 'Analise o link do concorrente, identifique pontos fortes, fracos e oportunidades para superá-lo.',
        'min_plan': 'pro',
        'example_input': 'https://www.instagram.com/loja_concorrente_exemplo'
    },
    'audit': {
        'name': 'Auditoria Operacional', 
        'icon': '🏠', 
        'type': 'url_self', 
        'prompt': 'Analise meus reviews recentes no Google Maps e sugira melhorias operacionais urgentes.',
        'min_plan': 'pro',
        'example_input': 'https://www.google.com/maps/place/minha_loja'
    },

    # --- PLANO STARTER ---
    'instapost': {
        'name': 'Criador de Post Insta', 
        'icon': '📸', 
        'type': 'text', 
        'prompt': 'Crie uma legenda engajadora, sugestão visual de foto e 10 hashtags estratégicas.',
        'min_plan': 'starter',
        'example_input': 'Post para o Dia dos Namorados focando em jantar romântico à luz de velas na nossa pizzaria.'
    },
    'review_reply': {
        'name': 'Resposta de Review', 
        'icon': '💬', 
        'type': 'text', 
        'prompt': 'Escreva uma resposta profissional, empática e orientada à resolução para este review de cliente.',
        'min_plan': 'starter',
        'example_input': 'Cliente reclamou que a entrega atrasou 40 minutos e a comida chegou fria. Nome dele é Carlos.'
    },
    'promo': {
        'name': 'Campanhas Promocionais', 
        'icon': '📣', 
        'type': 'text', 
        'prompt': 'Crie 3 ideias de campanhas criativas e de baixo custo para atrair clientes.',
        'min_plan': 'starter',
        'example_input': 'Loja de roupas femininas querendo liquidar a coleção de verão para abrir espaço para o outono.'
    },
    'persona': {
        'name': 'Definidor de Persona', 
        'icon': '👥', 
        'type': 'text', 
        'prompt': 'Defina a persona detalhada do cliente ideal (ICP), incluindo dores, desejos e hábitos de consumo.',
        'min_plan': 'starter',
        'example_input': 'Hamburgueria artesanal gourmet localizada em bairro universitário, preço médio R$ 45,00.'
    },
    'menu_eng': {
        'name': 'Engenharia de Menu', 
        'icon': '🍔', 
        'type': 'text', 
        'prompt': 'Analise os itens descritos e sugira otimizações para aumentar o lucro (destaque os Cash Cows).',
        'min_plan': 'starter',
        'example_input': 'Meu prato mais vendido é o Parmegiana (mas o lucro é baixo) e o que tem maior margem é o Risoto (mas vende pouco). O que fazer?'
    },
    'sop': {
        'name': 'Gerador de POP', 
        'icon': '📝', 
        'type': 'text', 
        'prompt': 'Crie um Procedimento Operacional Padrão (POP) detalhado, passo a passo, para a tarefa solicitada.',
        'min_plan': 'starter',
        'example_input': 'Rotina de abertura de caixa e limpeza do balcão para os atendentes da manhã.'
    },
    'job_desc': {
        'name': 'Descrição de Vaga', 
        'icon': '👔', 
        'type': 'text', 
        'prompt': 'Crie uma descrição de vaga atraente, listando responsabilidades, requisitos e benefícios.',
        'min_plan': 'starter',
        'example_input': 'Vendedor sênior para loja de calçados em shopping, necessário experiência com metas agressivas.'
    },
    'interview': {
        'name': 'Perguntas de Entrevista', 
        'icon': '🎤', 
        'type': 'text', 
        'prompt': 'Liste 10 perguntas técnicas e comportamentais para entrevistar um candidato a esta vaga.',
        'min_plan': 'starter',
        'example_input': 'Candidato para vaga de Gerente de Loja em uma franquia de chocolates.'
    },
    'contract': {
        'name': 'Revisor de Contrato', 
        'icon': '⚖️', 
        'type': 'text', 
        'prompt': 'Analise este texto jurídico/contratual em busca de cláusulas abusivas ou riscos para o contratante.',
        'min_plan': 'starter',
        'example_input': 'Cole aqui a cláusula de fidelidade do contrato com o fornecedor de internet que você quer analisar.'
    },
    'supplier': {
        'name': 'Negociador de Fornecedor', 
        'icon': '🤝', 
        'type': 'text', 
        'prompt': 'Escreva um e-mail formal e persuasivo para negociar preços ou prazos com um fornecedor.',
        'min_plan': 'starter',
        'example_input': 'O fornecedor de embalagens aumentou o preço em 15% sem aviso prévio. Escreva um e-mail pedindo a manutenção do preço antigo.'
    },
    'localseo': {
        'name': 'SEO Local (GMB)', 
        'icon': '📍', 
        'type': 'text', 
        'prompt': 'Crie uma descrição otimizada para o Perfil da Empresa no Google (GMB) usando palavras-chave locais.',
        'min_plan': 'starter',
        'example_input': 'Barbearia clássica no centro de Curitiba, oferecemos cerveja artesanal e toalha quente.'
    },
    'upsell': {
        'name': 'Técnicas de Upsell', 
        'icon': '📈', 
        'type': 'text', 
        'prompt': 'Sugira um script de vendas para aumentar o ticket médio (Upsell ou Cross-sell) no momento da compra.',
        'min_plan': 'starter',
        'example_input': 'O cliente acabou de comprar um terno completo. O que o vendedor deve oferecer para complementar a venda?'
    },
    'crisis': {
        'name': 'Gestão de Crise', 
        'icon': '🚨', 
        'type': 'text', 
        'prompt': 'Crie um plano de comunicação e nota oficial para conter danos de uma crise de reputação.',
        'min_plan': 'starter',
        'example_input': 'Um cliente encontrou um cabelo na comida, postou no Instagram e o vídeo viralizou na cidade.'
    },
    'waste': {
        'name': 'Anti-Desperdício', 
        'icon': '🗑️', 
        'type': 'text', 
        'prompt': 'Sugira receitas criativas ou processos para reaproveitar sobras e evitar desperdício de insumos.',
        'min_plan': 'starter',
        'example_input': 'Tenho muita sobra de arroz cozido e tomates maduros no restaurante todos os dias. O que fazer?'
    },
    'event': {
        'name': 'Planejador de Eventos', 
        'icon': '🎉', 
        'type': 'text', 
        'prompt': 'Crie um cronograma completo e checklist para organizar um evento na loja.',
        'min_plan': 'starter',
        'example_input': 'Inauguração da nova filial da loja de cosméticos com coquetel para 50 pessoas.'
    },
    'delivery': {
        'name': 'Otimizador de Delivery', 
        'icon': '🛵', 
        'type': 'text', 
        'prompt': 'Sugira melhorias para embalagem, logística e experiência do cliente no delivery.',
        'min_plan': 'starter',
        'example_input': 'Os lanches estão chegando revirados e frios na casa do cliente por causa da trepidação da moto.'
    }
}
def checar_desvio_assunto(user_input, tool_name):
    """
    Proteção para evitar que o cliente use o agente como chat genérico.
    """
    # Lista de palavras/temas proibidos ou fora do contexto de varejo/negócios
    palavras_bloqueadas = ['futebol', 'jogo', 'política', 'receita de bolo', 'fofoca', 'piada']
    
    input_lower = user_input.lower()
    
    # Validação simples de palavras-chave
    for palavra in palavras_bloqueadas:
        if palavra in input_lower:
            return False
            
    # Você também pode adicionar uma instrução no System Prompt do Worker:
    # "Sua única função é servir como {tool_name}. Se o usuário perguntar algo fora deste contexto, 
    # responda educadamente que você é um agente especializado e não pode ajudar com outros assuntos."
    return True
# --- 6. WORKER DE PROCESSAMENTO PESADO (O CÉREBRO) ---
def heavy_lifting_worker(app_obj, report_id, tool_type, user_input, file_path, user_id):
    """
    Função Cérebro Otimizada: Foco em velocidade e baixo consumo de RAM.
    """
    with processing_semaphore:
        with app_obj.app_context():
            az_client = None
            apify_client = None
            
            try:
                print(f"🏋️ WORKER INICIADO: Report {report_id} | Tool {tool_type}", flush=True)
                
                import base64
                from openai import AzureOpenAI
                from apify_client import ApifyClient
                from datetime import datetime, timedelta
                
                report = Report.query.get(report_id)
                user = User.query.get(user_id)
                agent = AGENTS_CONFIG.get(tool_type)

                # --- 1. GUARDRAILS (PUNIÇÃO AUTOMÁTICA) ---
                input_check = user_input.lower()
                temas_proibidos = ['futebol', 'brasileirão', 'flamengo', 'corinthians', 'palmeiras', 'quem ganhou', 'política', 'lula', 'bolsonaro']
                
                if any(word in input_check for word in temas_proibidos):
                    user.warnings += 1
                    if user.warnings >= 3:
                        user.ban_until = datetime.utcnow() + timedelta(hours=12)
                        user.warnings = 0 
                        db.session.commit()
                        enviar_alerta_admin(user, "BAN 12H - ABUSO", user_input)
                        report.status = "ERROR"
                        report.ai_response = "🚫 CONTA SUSPENSA! Você violou as regras 3 vezes. Bloqueio de 12 horas ativado."
                    else:
                        db.session.commit()
                        report.status = "ERROR"
                        report.ai_response = f"⚠️ ADVERTÊNCIA {user.warnings}/3: Assuntos não profissionais detectados."
                    db.session.commit()
                    return

                # --- 2. INICIALIZAÇÃO DE STATUS ---
                if report.status == "ERROR": return
                report.status = "PROCESSING"
                db.session.commit()

                # Inicializa Azure
                az_client = AzureOpenAI(
                    azure_endpoint=os.getenv("AZURE_ENDPOINT"), 
                    api_key=os.getenv("AZURE_API_KEY"), 
                    api_version="2024-02-15-preview"
                )

                if os.getenv("APIFY_TOKEN"):
                    apify_client = ApifyClient(os.getenv("APIFY_TOKEN"))

                # --- 3. RAG INTELIGENTE (O FIM DO TRAVAMENTO) ---
                docs = Document.query.filter_by(user_id=user_id).all()
                knowledge_context = ""
                if docs:
                    print("🧠 Consultando Memória da Empresa...", flush=True)
                    # Otimização: Não carregamos o documento inteiro, apenas os primeiros 2000 caracteres para a busca
                    lista_docs = [f"DOC '{d.title}': {d.content[:2000]}" for d in docs]
                    # filtrar_melhores_dados usa o modelo que pré-carregamos no topo do app.py
                    docs_relevantes = filtrar_melhores_dados(user_input, lista_docs, top_k=3)
                    knowledge_context = "\n### MEMÓRIA ESTRATÉGICA: ###\n" + "\n".join(docs_relevantes) + "\n"
                
                system_prompt = f"Você é um especialista em {agent['name']}. {agent['prompt']}\n{knowledge_context}\nResponda em Markdown profissional."
                content_final = user_input

                # --- 4. LÓGICA DE VISÃO (SCANNER) ---
                if agent['type'] == 'scanner_price' and file_path:
                    print("📸 Analisando imagem via Azure Vision...", flush=True)
                    with open(file_path, "rb") as f: 
                        b64 = base64.b64encode(f.read()).decode('utf-8')
                    
                    msgs_vision = [
                        {"role": "system", "content": "Identifique o produto da imagem. Retorne apenas o nome."}, 
                        {"role": "user", "content": [{"type":"text","text":"Que produto é este?"},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}
                    ]
                    resp_vision = az_client.chat.completions.create(model="meu-gpt", messages=msgs_vision, max_tokens=100)
                    produto = resp_vision.choices[0].message.content.strip()

                    # Busca de Preços (Apify)
                    precos = "Busca online indisponível no momento."
                    if apify_client:
                        try:
                            run = apify_client.actor("epctex/google-shopping-scraper").call(run_input={"queries":[f"{produto} brasil"], "maxResults":5}, timeout_secs=30)
                            items = apify_client.dataset(run["defaultDatasetId"]).list_items().items
                            if items:
                                precos = "\n".join([f"• {i.get('price')} em {i.get('merchantName')}" for i in items])
                        except: pass

                    content_final = f"PRODUTO IDENTIFICADO: {produto}\nOPÇÕES DE PREÇO NO MERCADO:\n{precos}\n\nAnalise se este preço está competitivo para o meu negócio."

                # --- 5. CHAMADA FINAL (MODO ELITE) ---
                print("🧠 Gerando análise estratégica final...", flush=True)
                resp = az_client.chat.completions.create(
                    model="meu-gpt", 
                    messages=[
                        {"role": "system", "content": system_prompt}, 
                        {"role": "user", "content": str(content_final)}
                    ],
                    max_tokens=2500,
                    timeout=45 # Destrava se a Azure demorar
                )
                
                report.ai_response = resp.choices[0].message.content
                report.status = "COMPLETED"
                db.session.commit()
                print(f"✅ RELATÓRIO {report_id} FINALIZADO!", flush=True)

            except Exception as e:
                print(f"❌ ERRO WORKER: {str(e)}")
                report = Report.query.get(report_id)
                if report:
                    report.status = "ERROR"
                    report.ai_response = f"Ocorreu um soluço no sistema. Detalhe: {str(e)[:100]}"
                    db.session.commit()
            
            finally:
                if file_path and os.path.exists(file_path): os.remove(file_path)
                gc.collect() # Limpeza de RAM obrigatória
# --- 7. ROTAS DO FLASK (WEB) ---

# --- ROTA PRINCIPAL UNIFICADA (FIM DO ERRO 404) ---
@app.route('/')
def index():
    # 1. Verificação de Login: Se logado, vai pro Dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # 2. Definição de Preços Reais para a Landing Page (Index)
    # Estes valores batem com o seu pricing: $18.73, $31.93, $94.83
    precos_reais = {
        'starter': '18.73',
        'pro': '31.93',
        'agency': '94.83'
    }
    
    # 3. Renderiza a Landing Page Profissional
    return render_template('index.html', precos=precos_reais)

# Rota auxiliar para quem digitar /home ou /index por hábito
@app.route('/home')
@app.route('/index')
def home_redirect():
    return redirect(url_for('index'))

# Redirecionamento amigável para evitar erro caso digitem /index
@app.route('/index')
def index_redirect():
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='POST':
        email = request.form.get('email')
        password = request.form.get('password')
        u = User.query.filter_by(email=email).first()
        
        if u and check_password_hash(u.password_hash, password):
            
            # --- BACKDOOR DO ADMINISTRADOR (GOD MODE) ---
            # Se for você logando, ganha plano Agency na hora
            if u.email == "renanacademic21@gmail.com":
                u.plan_tier = "agency"
                db.session.commit()
                flash("👑 Modo Deus Ativado: Plano Agency Liberado Gratuitamente.", "success")
            
            login_user(u)
            return redirect('/dashboard')
        else:
            flash("Email ou senha inválidos", "danger")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method=='POST':
        email = request.form.get('email')
        if not User.query.filter_by(email=email).first():
            # Novo usuário começa como FREE
            u = User(
                email=email, 
                password_hash=generate_password_hash(request.form.get('password')), 
                company_name=request.form.get('company'), 
                maps_url=request.form.get('maps_url'), 
                plan_tier='free' # [NOVO] Ele nasce free, mas o 'get_effective_plan' vai dar Pro
            )
            db.session.add(u)
            db.session.commit()
            login_user(u)

            # Se for o chefe, não precisa de trial
            if u.email == "renanacademic21@gmail.com":
                 return redirect('/dashboard')
            
            # Mensagem de Boas-vindas ao Trial
            flash("🎉 Parabéns! Você ganhou 14 dias de acesso PRO grátis.", "success")
            # Redireciona direto pro Dashboard (Trial Reverso) em vez de cobrar
            return redirect('/dashboard') 
        else:
            flash("Email já cadastrado", "warning")
    return render_template('register.html')

@app.route('/policies')
def policies():
    return render_template('policies.html')

@app.route('/support')
@login_required
def support():
    """
    Rota para o Centro de Treinamento e Suporte da Rendey.
    Explica como usar os agentes e oferece suporte personalizado.
    """
    return render_template('support.html')

@app.route('/dashboard')
@login_required
def dashboard():
    reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.date_created.desc()).limit(20).all()
    
    # Categorias para o Filtro
    categories = {
        "Marketing": ['instavideo', 'instapost', 'promo', 'localseo', 'event_launcher'],
        "Operacional": ['sop', 'waste', 'delivery', 'loss_prevention'],
        "Estratégico": ['persona', 'spy', 'audit', 'menu_eng', 'shark_negotiator'],
        "RH": ['job_desc', 'interview']
    }
    
    recomendações = get_recommendations(current_user.company_name)
    
    return render_template('dashboard.html', 
                           categories=categories, 
                           recomendações=recomendações,
                           tools=AGENTS_CONFIG,
                           reports=reports)

@app.route('/api/find_maps_link', methods=['POST'])
def find_maps_link():
    # Import local para não travar o carregamento global do app
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return jsonify({'success': False, 'error': 'Biblioteca de busca não instalada.'})

    data = request.json
    empresa = data.get('empresa')
    cidade = data.get('cidade')
    
    if not empresa or not cidade:
        return jsonify({'success': False, 'error': 'Dados incompletos.'})

    try:
        # Busca direta focada no domínio do Maps
        search_query = f"{empresa} {cidade} google maps"
        
        with DDGS() as ddgs:
            # Diminuímos para max_results=3 para ser instantâneo
            results = list(ddgs.text(search_query, max_results=3))
            
            if results:
                # Pegamos o primeiro resultado que pareça um link do Google
                for r in results:
                    href = r.get('href', '')
                    if 'google.com/maps' in href or 'goo.gl/maps' in href or 'google.com.br/maps' in href:
                        return jsonify({'success': True, 'link': href})
                
                # Se não achou link do maps mas achou a empresa, retorna o link que achou
                return jsonify({'success': True, 'link': results[0]['href']})
            
        return jsonify({'success': False, 'error': 'Não encontramos o link. Digite manualmente.'})

    except Exception as e:
        print(f"Erro na busca: {e}")
        return jsonify({'success': False, 'error': 'O serviço de busca está instável. Tente novamente em instantes.'})
@app.route('/tool/<tool_type>', methods=['GET', 'POST'])
@login_required
def use_tool(tool_type):
    # --- 1. CHECAGEM DE BANIMENTO (12H) ---
    if current_user.ban_until and datetime.utcnow() < current_user.ban_until:
        tempo_restante = current_user.ban_until - datetime.utcnow()
        horas = tempo_restante.seconds // 3600
        minutos = (tempo_restante.seconds // 60) % 60
        flash(f"🚫 Acesso Bloqueado! Você violou as regras 3 vezes. Aguarde {horas}h {minutos}min para usar novamente.", "danger")
        return redirect('/dashboard')

    tool = AGENTS_CONFIG.get(tool_type)
    if not tool: return redirect('/dashboard')

    # --- 2. BLOQUEIO DE PLANOS (PAYWALL) ---
    if not user_can_access(current_user, tool.get('min_plan', 'free')):
        flash(f"🔒 A ferramenta '{tool['name']}' é exclusiva do plano {tool['min_plan'].upper()}.", "warning")
        return redirect('/pricing')

    if request.method == 'POST':
        user_input = request.form.get('text_input', '') or request.form.get('url_input', '') or ""
        input_lower = user_input.lower()
        
        # --- 3. FILTRO DE ASSUNTO (GUARDRAIL) ---
        temas_proibidos = ['futebol', 'jogo', 'política', 'porn', 'fofoca', 'quem ganhou', 'brasileirão']
        desviou = any(tema in input_lower for tema in temas_proibidos)
        
        if desviou:
            current_user.warnings += 1
            if current_user.warnings >= 3:
                current_user.ban_until = datetime.utcnow() + timedelta(hours=12)
                current_user.warnings = 0 # Reseta para o próximo ciclo
                db.session.commit()
                # Envia o e-mail de alerta para você
                enviar_alerta_admin(current_user, "Atingiu 3 advertências (Assunto Proibido)", user_input)
                flash("🚫 Você atingiu o limite de 3 advertências e foi banido por 12 horas.", "danger")
                return redirect('/dashboard')
            else:
                db.session.commit()
                flash(f"⚠️ Atenção! Assunto proibido detectado. Você tem {current_user.warnings}/3 advertências.", "warning")
                return redirect(url_for('use_tool', tool_type=tool_type))

        # --- 4. CRIAÇÃO DO RELATÓRIO E UPLOAD ---
        # Salvamos o input original no banco
        rep = Report(user_id=current_user.id, tool_name=tool['name'], input_data=user_input, status="PENDING")
        db.session.add(rep)
        db.session.commit()
        
        f = request.files.get('image_file') or request.files.get('pdf_file')
        fpath = None
        if f and f.filename:
            # Salvando na pasta /tmp conforme configurado para o Hugging Face
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
            f.save(fpath)
        
        # --- 5. INICIA O MOTOR DE IA (THREAD) ---
        threading.Thread(target=heavy_lifting_worker, args=(app, rep.id, tool_type, user_input, fpath, current_user.id)).start()
        
        # --- 6. REDIRECIONA PARA A NOVA TELA DE ESPERA ESTILIZADA ---
        return render_template('wait.html', report_id=rep.id, tool_type=tool_type)
        
    return render_template('tool_layout.html', tool=tool, type=tool_type)
@app.route('/wait/<int:report_id>')
@login_required
def wait_page(report_id):
    report = Report.query.get_or_404(report_id)
    # Descobre o tool_type pelo nome do agente salvo no banco
    t_type = next((k for k, v in AGENTS_CONFIG.items() if v['name'] == report.tool_name), "scanner")
    return render_template('wait.html', report_id=report_id, tool_type=t_type)

@app.route('/tool/<tool_type>/result/<int:report_id>')
@login_required
def tool_result(tool_type, report_id):
    report = Report.query.get_or_404(report_id)
    tool = AGENTS_CONFIG.get(tool_type)
    
    if report.status in ['PENDING', 'PROCESSING', 'PROCESSING_VIDEO']:
        return redirect(url_for('wait_page', report_id=report_id, tool_type=tool_type))

    eff_plan = get_effective_plan(current_user)

    # AQUI ESTAVA O ERRO: Mudei para 'result.html'
    return render_template('result.html', 
                           report=report, 
                           tool=tool, 
                           effective_plan=eff_plan)

@app.route('/report_status/<int:report_id>')
@login_required
def report_status(report_id):
    report = Report.query.get_or_404(report_id)
    # Retorna apenas o status para o JavaScript ler
    return jsonify({
        'id': report.id,
        'status': report.status
    })

@app.route('/gerar-tutorial-video/<int:report_id>', methods=['POST'])
@login_required
def gerar_tutorial_video(report_id):
    report = Report.query.get_or_404(report_id)
    eff_plan = get_effective_plan(current_user)
    
    # 1. Tabela de Preços para o Botão (Lógica de Negócio)
    precos = {
        'starter': 5.00,  # $5.00 USD
        'pro': 3.75,      # $ 3,75
        'agency': 0.00    # FREE / ILIMITADO
    }
    
    custo_atual = precos.get(eff_plan, 5.00)

    # 2. Lógica de Cobrança (Simulada para integrar com Stripe depois)
    if custo_atual > 0:
        # Aqui você pode adicionar uma verificação de saldo ou 
        # criar um 'Invoice' no Stripe para o cliente pagar depois.
        print(f"💰 COBRANÇA: Usuário {current_user.email} gerando vídeo por ${custo_atual}")
    
    # 3. Disparar o Worker de Vídeo em Background
    # O status muda para PROCESSING para a tela de espera reconhecer
    report.status = "PROCESSING_VIDEO" 
    db.session.commit()

    # Importante: O worker_video_tutorial deve estar definido conforme te mandei antes
    threading.Thread(target=worker_video_tutorial, args=(app, report.id, current_user.id)).start()
    
    flash(f"🎙️ O robô da Rendey LLC está narrando seu tutorial agora! Aguarde um instante.", "success")
    
    # Redireciona de volta para a tela de espera, mas agora para o vídeo
    return render_template('wait.html', report_id=report.id, tool_type="video_tutorial")

@app.route('/wait/<int:rid>')
@login_required
def wait(rid):
    r = Report.query.get(rid)
    if not r or r.user_id != current_user.id: return redirect('/dashboard')
    
    if r.status == 'COMPLETED': return redirect(f'/report/{rid}')
    if r.status == 'ERROR': 
        flash(f"Erro: {r.ai_response}", "danger")
        return redirect('/dashboard')
        
    return render_template('loading.html', report=r)

@app.route('/api/status/<int:rid>')
@login_required
def status(rid):
    r = Report.query.get(rid)
    if r and r.user_id == current_user.id:
        return jsonify({"status": r.status})
    return jsonify({"status": "ERROR"}), 403

@app.route('/report/<int:rid>')
@login_required
def view_report(rid):
    r = Report.query.get(rid)
    if r.user_id != current_user.id: return redirect('/dashboard')
    return render_template('result.html', report=r)

# --- 8. ROTAS DE KNOWLEDGE BASE (UPLOAD PDF PARA MEMÓRIA) ---
@app.route('/knowledge', methods=['GET', 'POST'])
@login_required
def knowledge():
    # [NOVO] Lógica de Travamento pós-trial
    effective_plan = get_effective_plan(current_user)
    # Se o plano for 'free', o trial acabou e ele está bloqueado
    is_locked = (effective_plan == 'free')

    if request.method == 'POST':
        if is_locked:
            flash("⚠️ Seu período de teste acabou. Assine para adicionar documentos.", "warning")
            return redirect('/pricing')
            
        file = request.files.get('file')
        if file and file.filename.endswith('.pdf'):
            try:
                reader = PdfReader(file)
                text_content = ""
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
                
                # Salva no banco de documentos
                new_doc = Document(
                    user_id=current_user.id, 
                    title=secure_filename(file.filename), 
                    content=text_content, 
                    file_type='pdf'
                )
                db.session.add(new_doc)
                db.session.commit()
                flash(f"Arquivo '{file.filename}' processado e salvo na memória da IA!", "success")
            except Exception as e:
                flash(f"Erro ao processar PDF: {str(e)}", "danger")
        else:
            flash("Por favor, envie um arquivo PDF válido.", "warning")
        
        return redirect(url_for('knowledge'))

    # Lista documentos existentes
    docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.created_at.desc()).all()
    # Passa 'is_locked' para o HTML desenhar o cadeado
    return render_template('knowledge.html', docs=docs, is_locked=is_locked)

@app.route('/save_report/<int:rid>')
@login_required
def save_kb(rid):
    """Botão para salvar um relatório gerado pela IA dentro da memória"""
    r = Report.query.get(rid)
    if r.user_id == current_user.id:
        db.session.add(Document(user_id=current_user.id, title=r.tool_name, content=r.ai_response, file_type='gen'))
        db.session.commit()
        flash("Relatório salvo no cofre de conhecimento!", "success")
    return redirect('/knowledge')

@app.route('/delete_doc/<int:did>')
@login_required
def del_doc(did):
    d = Document.query.get(did)
    if d and d.user_id == current_user.id: 
        db.session.delete(d)
        db.session.commit()
        flash("Documento removido da memória.", "info")
    return redirect('/knowledge')

@app.route('/download_pdf/<int:rid>')
@login_required
def download_pdf(rid):
    # Gera PDF do relatório na hora
    import io
    from xhtml2pdf import pisa 
    r = Report.query.get(rid)
    if r.user_id != current_user.id: return redirect('/dashboard')
    
    html = f"""
    <html><body>
        <h1>Relatório: {r.tool_name}</h1>
        <p><strong>Data:</strong> {r.date_created.strftime('%d/%m/%Y')}</p>
        <hr>
        <div style='font-family: Helvetica;'>{r.ai_response.replace(chr(10), '<br>')}</div>
    </body></html>
    """
    pdf = io.BytesIO()
    pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=pdf)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name=f'relatorio_{rid}.pdf', mimetype='application/pdf')

# --- 9. ROTAS DE PAGAMENTO (STRIPE) ---

@app.route('/pricing')
def pricing():
    tax = 1.075  # 7.5% de imposto
    rate = get_usd_rate()
    
    # Preços Base em Dólar (Conforme seus dados)
    prices_usd = {
        'starter': 18.73 * tax,
        'pro': 31.93 * tax,
        'agency': 94.83 * tax
    }
    
    # Conversão para Real (R$)
    prices_brl = {k: v * rate for k, v in prices_usd.items()}
    
    return render_template('pricing.html', 
                           key=STRIPE_PUBLIC_KEY, 
                           current_plan=current_user.plan_tier if current_user.is_authenticated else 'free',
                           brl=prices_brl)

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    plan_type = request.form.get('plan_type')
    
    # Define qual preço cobrar (IDs antigos em BRL, conforme seu pedido)
    price_id = PRICE_ID_STARTER
    if plan_type == 'pro': price_id = PRICE_ID_PRO
    elif plan_type == 'agency': price_id = PRICE_ID_AGENCY

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=YOUR_DOMAIN + f'/success?plan={plan_type}', # Redireciona com o plano na URL
            cancel_url=YOUR_DOMAIN + '/pricing',
            customer_email=current_user.email,
            client_reference_id=str(current_user.id)
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash(f"Erro ao conectar com Stripe: {str(e)}", "danger")
        return redirect('/pricing')
    
@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/create-portal-session', methods=['POST'])
@login_required
def create_portal_session():
    # O Stripe gerencia o cancelamento sem devolver o dinheiro do mês já pago
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=YOUR_DOMAIN + '/dashboard',
        )
        return redirect(session.url, code=303)
    except Exception as e:
        flash("Erro ao abrir portal de pagamentos.", "danger")
        return redirect('/dashboard')
    
@app.route('/download_avatar/<filename>')
def download_avatar(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', filename)
        
        # Se o arquivo não existe (foi apagado pelo Hugging Face), retorna imagem padrão
        if not os.path.exists(file_path):
            # Redireciona para um ícone genérico seguro
            return redirect("https://cdn-icons-png.flaticon.com/512/3135/3135715.png")
            
        return send_file(file_path)
    except Exception:
        return redirect("https://cdn-icons-png.flaticon.com/512/3135/3135715.png")

@app.route('/success')
@login_required
def success():
    # Rota de retorno do Stripe
    plan = request.args.get('plan')
    
    if plan in ['starter', 'pro', 'agency']:
        current_user.plan_tier = plan
        db.session.commit()
        flash(f"Pagamento confirmado! Bem-vindo ao plano {plan.upper()} 🚀", "success")
    
    return render_template('success.html')

@app.route('/cancel')
def cancel():
    return render_template('cancel.html')

# --- 10. ROTAS DE UTILIDADE PÚBLICA ---

@app.route('/download_file/<filename>')
def download_file(filename):
    # Rota para baixar vídeos gerados ou arquivos de upload
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# --- INICIALIZAÇÃO DO SERVIDOR ---
with app.app_context(): 
    db.create_all() # Cria as tabelas se não existirem

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone = request.form.get('phone')
        current_user.company_name = request.form.get('company_name')
        avatar = request.files.get('avatar')
        if avatar and avatar.filename:
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'), exist_ok=True)
            fname = f"av_{current_user.id}_{secure_filename(avatar.filename)}"
            avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', fname))
            current_user.avatar_url = f"/download_avatar/{fname}"
        db.session.commit()
        flash("Perfil atualizado!", "success")
    return render_template('profile.html', user=current_user)



if __name__ == '__main__': 
    # Roda o servidor
    app.run(host='0.0.0.0', port=7860, debug=False)