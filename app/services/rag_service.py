print("🚀 Pré-carregando motor de inteligência estratégica (all-MiniLM-L6-v2)...", flush=True)

try:
    from rag_engine import filtrar_melhores_dados as _filtrar
    _filtrar("inicialização", ["contexto de teste"])
    print("✅ Motor de RAG carregado com sucesso na RAM!")
except Exception as e:
    print(f"⚠️ Erro ao pré-carregar motor: {e}")
    _filtrar = None

def filtrar_melhores_dados_precarregado(query, docs, top_k=5):
    if _filtrar is None:
        return docs[:top_k]
    return _filtrar(query, docs, top_k=top_k)
