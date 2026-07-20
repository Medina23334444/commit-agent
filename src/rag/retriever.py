# src/rag/retriever.py
from rag.vector_store import get_vector_store


def get_repo_context_rag(query: str, k: int = 3) -> dict:
    """
    Busca contexto relevante en ChromaDB basado en un query (generalmente el resumen del diff).
    Retorna un diccionario con 'convenciones' (commits) y 'readme' (reglas).

    Usa dos búsquedas separadas (filtradas por source_type) para garantizar
    que ambas fuentes de contexto estén representadas, en vez de competir
    por el mismo top-k global.
    """
    vector_store = get_vector_store()

    commit_retriever = vector_store.as_retriever_by_type("git_commit", k=k)
    guideline_retriever = vector_store.as_retriever_by_type("project_guideline", k=k)

    commits_docs = commit_retriever.invoke(query)
    guideline_docs = guideline_retriever.invoke(query)

    commits_similares = [
        f"- {doc.metadata.get('mensaje_original', doc.page_content)}"
        for doc in commits_docs
    ]

    reglas_proyecto = [doc.page_content for doc in guideline_docs]

    convenciones_str = (
        "Ejemplos de commits similares en este repo:\n" + "\n".join(commits_similares)
        if commits_similares else ""
    )

    readme_str = (
        "Reglas detectadas en la documentación:\n" + "\n---\n".join(reglas_proyecto)
        if reglas_proyecto else ""
    )

    return {
        "convenciones": convenciones_str,
        "readme": readme_str
    }