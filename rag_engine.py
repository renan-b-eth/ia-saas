from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import json

# Carregamos o modelo uma única vez para a RAM (Singleton)
# Este modelo tem apenas ~80MB, super leve e rápido.
print("⚡ A carregar modelo de IA Local (RAG)...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Modelo carregado na RAM!")

def filtrar_melhores_dados(query_utilizador, lista_dados, top_k=5):
    """
    1. Recebe a pergunta do utilizador e uma lista de textos (ex: produtos, posts).
    2. Usa IA Local para encontrar os itens mais relevantes semanticamente.
    3. Retorna apenas os 'top_k' melhores para enviar ao GPT.
    """
    
    # Se a lista for pequena, não vale a pena filtrar, devolve tudo
    if len(lista_dados) <= top_k:
        return lista_dados

    # 1. Transformar os dados em texto simples se forem JSON/Dict
    textos = []
    for item in lista_dados:
        if isinstance(item, dict):
            # Concatena valores importantes do dicionário
            textos.append(str(item)) 
        else:
            textos.append(str(item))

    # 2. Criar Embeddings (Vetores) para a Query e para os Dados
    # Como tens 16GB de RAM, isto acontece em milissegundos.
    embeddings_dados = model.encode(textos)
    embedding_query = model.encode([query_utilizador])

    # 3. Calcular a similaridade (Cosseno)
    similaridades = cosine_similarity(embedding_query, embeddings_dados)[0]

    # 4. Ordenar e pegar os índices dos melhores
    # (argsort devolve os índices do menor para o maior, por isso o [::-1])
    indices_melhores = similaridades.argsort()[::-1][:top_k]

    # 5. Recuperar os objetos originais
    resultados_finais = [lista_dados[i] for i in indices_melhores]
    
    return resultados_finais