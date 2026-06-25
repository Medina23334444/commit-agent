# src/rag/retriever.py
from rag.vector_store import RepoVectorStore


def get_repo_context_rag(query: str, k: int = 3) -> dict:
    """
    Busca contexto relevante en ChromaDB basado en un query (generalmente el resumen del diff).
    Retorna un diccionario con 'convenciones' (commits) y 'readme' (reglas).
    """
    vector_store = RepoVectorStore()
    retriever = vector_store.as_retriever(k=k)

    resultados = retriever.invoke(query)

    if not resultados:
        return {"convenciones": "", "readme": ""}

    commits_similares = []
    reglas_proyecto = []

    for doc in resultados:
        source_type = doc.metadata.get("source_type", "")

        if source_type == "git_commit":
            mensaje = doc.page_content.split("Message: ")[-1].split("\nAuthor:")[0]
            commits_similares.append(f"- {mensaje}")
        else:
            reglas_proyecto.append(doc.page_content)

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