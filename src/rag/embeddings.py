#src/rag/embeddings.py
from langchain_community.embeddings import OllamaEmbeddings

def get_embeddings_model():
    """Inicializa el modelo de embeddings local a través de Ollama."""
    return OllamaEmbeddings(
        model="nomic-embed-text",
    )


