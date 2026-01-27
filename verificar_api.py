from gradio_client import Client

try:
    client = Client("manavisrani07/gradio-lipsync-wav2lip")
    print("\n🔍 Vasculhando os segredos da API...")
    client.view_api() # Isso vai imprimir a documentação oculta no seu terminal
except Exception as e:
    print(f"❌ Erro ao conectar: {e}")