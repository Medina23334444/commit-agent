import os
from langchain_chroma import Chroma
from rag.embeddings import get_embeddings_model

PERSIST_DIRECTORY = os.path.join(os.getcwd(), "chroma")

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
        """Retorna el motor de búsqueda configurado para traer los k mejores resultados (sin filtro)."""
        return self.db.as_retriever(search_kwargs={"k": k})

    def as_retriever_by_type(self, source_type: str, k: int = 3):
        """
        Retorna un retriever filtrado por source_type ('git_commit' o 'project_guideline').
        Garantiza que cada tipo de contexto se busque de forma independiente,
        en vez de competir por el mismo top-k global.
        """
        return self.db.as_retriever(
            search_kwargs={"k": k, "filter": {"source_type": source_type}}
        )

    def reset(self):
        """Borra todos los documentos de la colección actual para evitar duplicados."""
        try:
            self.db.delete_collection()
            self.db = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=PERSIST_DIRECTORY
            )
        except Exception as e:
            print(f"⚠️ Nota: No se pudo limpiar la colección (puede que sea nueva). {e}")


def get_vector_store() -> RepoVectorStore:
    """
    Retorna la instancia de RepoVectorStore cacheada globalmente.
    Se inicializa una sola vez en la primera llamada.

    IMPORTANTE: tanto indexing.py como retriever.py deben usar esta factory
    para evitar tener dos instancias de Chroma desincronizadas sobre el mismo
    persist_directory.
    """
    global _vector_store_cache

    if _vector_store_cache is None:
        _vector_store_cache = RepoVectorStore()

    return _vector_store_cache