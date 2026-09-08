# src/rag/chunking.py
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

_SKIP_PATTERNS = (
    "merge pull request",
    "merge branch",
    "merge remote-tracking",
)

def _is_meaningful_commit(mensaje: str) -> bool:
    """Filtra commits de merge automático y mensajes vacíos."""
    if not mensaje or not mensaje.strip():
        return False
    lower = mensaje.lower().strip()
    return not any(lower.startswith(p) for p in _SKIP_PATTERNS)


def chunk_commits(commits_raw: list[dict]) -> list[Document]:
    """
    Convierte datos crudos de commits en Documents listos para vectorizar.
    Cada commit es un chunk único e indivisible. Se filtran merges automáticos.
    """
    documents = []
    for commit in commits_raw:
        mensaje = commit.get("mensaje", "").strip()

        if not _is_meaningful_commit(mensaje):
            continue

        content = (
            f"Commit message example:\n"
            f"Message: {mensaje}\n"
            f"Author: {commit.get('autor', 'unknown')}\n"
            f"Date: {commit.get('fecha', 'unknown')}"
        )

        metadata = {
            "hash": commit.get("hash", "unknown"),
            "date": commit.get("fecha", "unknown"),
            "author": commit.get("autor", "unknown"),
            "source_type": "git_commit",
            "mensaje_original": mensaje,  # ← NUEVO: evita parsear el string en retriever.py
        }
        documents.append(Document(page_content=content, metadata=metadata))

    return documents


def chunk_markdown_guidelines(text: str, filename: str) -> list[Document]:
    """
    Fragmenta archivos de guías como CONTRIBUTING.md, README.md, etc.
    chunk_size=512 aprovecha mejor la ventana de nomic-embed-text.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,       # nomic-embed-text soporta 512 tokens
        chunk_overlap=64,     # ~12.5% de overlap para preservar contexto
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    fragmentos = splitter.split_text(text)

    documents = []
    for i, fragmento in enumerate(fragmentos):
        metadata = {
            "source_file": filename,
            "chunk_index": i,
            "source_type": "project_guideline",
        }
        content = f"Project rule/context ({filename}):\n{fragmento}"
        documents.append(Document(page_content=content, metadata=metadata))

    return documents