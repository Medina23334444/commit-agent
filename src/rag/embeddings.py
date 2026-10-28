# src/rag/embeddings.py
from langchain_huggingface import HuggingFaceEmbeddings

# ─ Caché global (se carga una sola vez) ────────────────────────────────────
_embeddings_cache = None

def get_embeddings_model():
    """
    Retorna el modelo de embeddings cacheado globalmente.
    Se inicializa una sola vez en la primera llamada.
    """
    global _embeddings_cache
    
    if _embeddings_cache is None:
        _embeddings_cache = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2", 
            model_kwargs={'device': 'cpu'} 
        )
    
    return _embeddings_cache