# src/rag/vector_store.py
import os
from langchain_chroma import Chroma
from rag.embeddings import get_embeddings_model

PERSIST_DIRECTORY = os.path.join(os.getcwd(), "chroma")

# ─ Caché global del vector store (se carga una sola vez) ──────────────────
_vector_store_cache = None


class RepoVectorStore:
    def __init__(self):
        self.embeddings = get_embeddings_model()
        self.collection_name = "commit_history"

        self.db = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=PERSIST_DIRECTORY
        )

    def add_documents(self, documents):
        """Añade documentos fragmentados a la base de datos."""
        self.db.add_documents(documents)

    def as_retriever(self, k=3):
        """Retorna el motor de búsqueda configurado para traer los k mejores resultados."""
        return self.db.as_retriever(search_kwargs={"k": k})

    def reset(self):
        """Borra todos los documentos de la colección actual para evitar duplicados."""
        try:
            # Elimina los datos de la colección si ya existen
            self.db.delete_collection()
            # Vuelve a inicializar la base de datos limpia
            self.db = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=PERSIST_DIRECTORY
            )
        except Exception as e:
            print(f"⚠️ Nota: No se pudo limpiar la colección (puede que sea nueva). {e}")


def get_vector_store():
    """
    Retorna la instancia de RepoVectorStore cacheada globalmente.
    Se inicializa una sola vez en la primera llamada.
    """
    global _vector_store_cache
    
    if _vector_store_cache is None:
        _vector_store_cache = RepoVectorStore()
    
    return _vector_store_cache