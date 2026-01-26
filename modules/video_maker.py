import os
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip
from moviepy.config import change_settings

# Configura o ImageMagick no Linux do Hugging Face
change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})

async def _gerar_audio_async(texto, caminho_saida):
    """Gera áudio com voz neural (Interno)"""
    voice = "pt-BR-FranciscaNeural" 
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(caminho_saida)

def criar_video_reels(imagem_path, texto_narracao, texto_legenda, output_path):
    """
    Recebe imagem e textos, retorna o path do vídeo gerado.
    """
    audio_temp = "temp_audio.mp3"
    try:
        print(f"🎬 Iniciando Render: {output_path}...", flush=True)
        
        # 1. Gera Áudio
        asyncio.run(_gerar_audio_async(texto_narracao, audio_temp))
        
        # 2. Carrega Áudio
        audio_clip = AudioFileClip(audio_temp)
        duracao = audio_clip.duration + 1.0
        
        # 3. Trata Imagem (Efeito Zoom/Crop Vertical 9:16)
        # Resize para altura 1920 (HD Vertical) e corta o centro
        clip = ImageClip(imagem_path).set_duration(duracao)
        clip = clip.resize(height=1920)
        clip = clip.crop(x1=0, y1=0, width=1080, height=1920, x_center=540, y_center=960)
        
        # 4. Legenda (Texto Branco com Borda Preta)
        # Tenta usar Arial, se não tiver usa padrão do Linux
        font_check = 'DejaVu-Sans-Bold'
        
        txt_clip = TextClip(texto_legenda, fontsize=60, color='white', font=font_check, 
                            stroke_color='black', stroke_width=3, method='caption', size=(900, None))
        txt_clip = txt_clip.set_pos(('center', 0.8), relative=True).set_duration(duracao)
        
        # 5. Composição
        video = CompositeVideoClip([clip, txt_clip])
        video = video.set_audio(audio_clip)
        
        # 6. Renderização (Ultrafast = Menos CPU)
        video.write_videofile(output_path, fps=24, codec='libx264', preset='ultrafast', audio_codec='aac')
        
        return output_path

    except Exception as e:
        print(f"❌ Erro Video Maker: {e}")
        raise e
    finally:
        # Limpeza
        if os.path.exists(audio_temp):
            os.remove(audio_temp)