import os
import gc
import base64
from datetime import datetime, timedelta
from apify_client import ApifyClient
from openai import AzureOpenAI

from app.extensions import db
from app.models import Report, User, Document
from app.constants import AGENTS_CONFIG
from app.services.rag_service import filtrar_melhores_dados_precarregado

def heavy_lifting_worker(app, report_id, tool_type, user_input, file_path, user_id, processing_semaphore, enviar_alerta_admin):
    with processing_semaphore:
        with app.app_context():
            try:
                report = Report.query.get(report_id)
                user = User.query.get(user_id)
                agent = AGENTS_CONFIG.get(tool_type)

                input_check = (user_input or "").lower()
                temas_proibidos = ['futebol', 'brasileirão', 'flamengo', 'corinthians', 'palmeiras', 'quem ganhou', 'política', 'lula', 'bolsonaro']

                if any(w in input_check for w in temas_proibidos):
                    user.warnings += 1
                    if user.warnings >= 3:
                        user.ban_until = datetime.utcnow() + timedelta(hours=12)
                        user.warnings = 0
                        db.session.commit()
                        enviar_alerta_admin(app, user, "BAN 12H - ABUSO", user_input)
                        report.status = "ERROR"
                        report.ai_response = "🚫 CONTA SUSPENSA! Você violou as regras 3 vezes. Bloqueio de 12 horas ativado."
                    else:
                        db.session.commit()
                        report.status = "ERROR"
                        report.ai_response = f"⚠️ ADVERTÊNCIA {user.warnings}/3: Assuntos não profissionais detectados."
                    db.session.commit()
                    return

                if report.status == "ERROR":
                    return
                report.status = "PROCESSING"
                db.session.commit()

                az_client = AzureOpenAI(
                    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
                    api_key=os.getenv("AZURE_API_KEY"),
                    api_version="2024-02-15-preview"
                )

                apify_client = ApifyClient(os.getenv("APIFY_TOKEN")) if os.getenv("APIFY_TOKEN") else None

                docs = Document.query.filter_by(user_id=user_id).all()
                knowledge_context = ""
                if docs:
                    lista_docs = [f"DOC '{d.title}': {d.content[:2000]}" for d in docs]
                    docs_relevantes = filtrar_melhores_dados_precarregado(user_input, lista_docs, top_k=3)
                    knowledge_context = "\n### MEMÓRIA ESTRATÉGICA: ###\n" + "\n".join(docs_relevantes) + "\n"

                system_prompt = f"Você é um especialista em {agent['name']}. {agent['prompt']}\n{knowledge_context}\nResponda em Markdown profissional."
                content_final = user_input

                if agent['type'] == 'scanner_price' and file_path:
                    with open(file_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode('utf-8')

                    msgs_vision = [
                        {"role": "system", "content": "Identifique o produto da imagem. Retorne apenas o nome."},
                        {"role": "user", "content": [{"type": "text", "text": "Que produto é este?"},
                                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}
                    ]
                    resp_vision = az_client.chat.completions.create(model="meu-gpt", messages=msgs_vision, max_tokens=100)
                    produto = resp_vision.choices[0].message.content.strip()

                    precos = "Busca online indisponível no momento."
                    if apify_client:
                        try:
                            run = apify_client.actor("epctex/google-shopping-scraper").call(
                                run_input={"queries": [f"{produto} brasil"], "maxResults": 5},
                                timeout_secs=30
                            )
                            items = apify_client.dataset(run["defaultDatasetId"]).list_items().items
                            if items:
                                precos = "\n".join([f"• {i.get('price')} em {i.get('merchantName')}" for i in items])
                        except:
                            pass

                    content_final = f"PRODUTO IDENTIFICADO: {produto}\nOPÇÕES DE PREÇO NO MERCADO:\n{precos}\n\nAnalise se este preço está competitivo para o meu negócio."

                resp = az_client.chat.completions.create(
                    model="meu-gpt",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": str(content_final)}],
                    max_tokens=2500,
                    timeout=45
                )

                report.ai_response = resp.choices[0].message.content
                report.status = "COMPLETED"
                db.session.commit()

            except Exception as e:
                report = Report.query.get(report_id)
                if report:
                    report.status = "ERROR"
                    report.ai_response = f"Ocorreu um soluço no sistema. Detalhe: {str(e)[:100]}"
                    db.session.commit()
            finally:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
                gc.collect()
