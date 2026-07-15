# src/rag/embeddings.py
from langchain_huggingface import HuggingFaceEmbeddings

def get_embeddings_model():
    """
    Inicializa el modelo de embeddings local en CPU (all-MiniLM-L6-v2).
    Esto evita competir por la VRAM de la GPU con el modelo principal (Qwen),
    reduciendo drásticamente la latencia y eliminando cuellos de botella.
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2", 
        model_kwargs={'device': 'cpu'} 
    )