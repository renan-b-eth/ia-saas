from TTS.api import TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")

tts.tts_to_file(text="Olá Renan! Esse áudio está sendo gerado localmente.", 
               speaker_wav="caminho/da/sua/voz.wav", 
               language="pt", 
               file_path="output.wav")