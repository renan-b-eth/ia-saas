def preload_rag():
    print("🚀 Pré-carregando motor de inteligência estratégica (all-MiniLM-L6-v2)...", flush=True)
    try:
        from rag_engine import filtrar_melhores_dados
        filtrar_melhores_dados("inicialização", ["contexto de teste"])
        print("✅ Motor de RAG carregado com sucesso na RAM!")
        return filtrar_melhores_dados
    except Exception as e:
        print(f"⚠️ Erro ao pré-carregar motor: {e}")
        def fallback(query, docs, top_k=5):
            return docs[:top_k]
        return fallback
