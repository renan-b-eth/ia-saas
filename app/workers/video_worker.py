import os
import asyncio
import requests
import datetime
from app.extensions import db
from app.models import Report, Document


def worker_video_tutorial(app, report_id, user_id):
    """
    Mesmo worker do seu legacy (HTML com botão de download).
    """
    with app.app_context():
        from moviepy.editor import ImageClip, AudioFileClip
        from openai import OpenAI
        import edge_tts

        def log_status(msg):
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🎬 [VIDEO-WORKER] {msg}", flush=True)

        try:
            log_status(f"🚀 INICIANDO VÍDEO PARA REPORT: {report_id}")
            report = Report.query.get(report_id)
            if not report:
                return

            api_key = os.getenv("NVIDIA_API_KEY")
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)

            prompt_sistema = (
                "Você é um Diretor de Marketing. Crie um roteiro curto (max 40s) para vídeo viral. "
                "Responda APENAS o texto falado."
            )
            texto_base = report.input_data if report.input_data else (report.tool_description or "")

            completion = client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"Roteiro sobre: {texto_base}"},
                ],
                temperature=0.7,
                max_tokens=800,
            )
            roteiro = completion.choices[0].message.content.strip()
            log_status("📝 Roteiro gerado.")

            upload_folder = app.config["UPLOAD_FOLDER"]
            audio_path = os.path.join(upload_folder, f"audio_{report_id}.mp3")
            asyncio.run(edge_tts.Communicate(roteiro, "pt-BR-AntonioNeural").save(audio_path))

            video_filename = f"video_viral_{report_id}.mp4"
            video_path_final = os.path.join(upload_folder, video_filename)
            foto_base = os.path.join(upload_folder, "consultor_base.jpg")
            temp_audio_path = os.path.join(upload_folder, f"temp_audio_{report_id}.m4a")

            if not os.path.exists(foto_base):
                r = requests.get("https://raw.githubusercontent.com/renan-b-eth/rendey-assets/main/consultor.jpg", timeout=20)
                with open(foto_base, "wb") as f:
                    f.write(r.content)

            log_status("🎬 Renderizando MP4...")
            audio_clip = AudioFileClip(audio_path)
            duration = max(5, audio_clip.duration)

            final_clip = ImageClip(foto_base).set_duration(duration).set_audio(audio_clip).set_fps(24)
            final_clip.write_videofile(
                video_path_final,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                ffmpeg_params=["-pix_fmt", "yuv420p"],
                temp_audiofile=temp_audio_path,
                remove_temp=True,
                logger=None,
            )

            try:
                new_doc = Document(
                    user_id=user_id,
                    title=f"🎬 Vídeo Gerado (#{report_id})",
                    content=f"Roteiro:\n{roteiro}\n\nArquivo: {video_filename}",
                    file_type="video_script",
                )
                db.session.add(new_doc)
                db.session.commit()
            except Exception:
                pass

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
            report = Report.query.get(report_id)
            if report:
                report.status = "ERROR"
                report.ai_response = f"Erro técnico: {str(e)}"
                db.session.commit()
