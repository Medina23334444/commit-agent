# src/rag/indexing.py
import subprocess
import os
import traceback
from rag.chunking import chunk_commits, chunk_markdown_guidelines
from rag.vector_store import RepoVectorStore


GUIDELINE_FILES = [
    "README.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    ".gitmessage",
]


def fetch_raw_commits(limit: int = 100) -> list[dict]:
    """Extrae el historial de Git como lista de dicts."""
    try:
        cmd = ["git", "log", f"-n{limit}", "--pretty=format:%H|%ad|%an|%s"]
        output = subprocess.check_output(
            cmd, text=True, encoding="utf-8", stderr=subprocess.PIPE
        )

        commits = []
        for line in output.splitlines():
            if not line.strip():
                continue
            partes = line.split("|", 3)
            if len(partes) == 4:
                commits.append({
                    "hash": partes[0],
                    "fecha": partes[1],
                    "autor": partes[2],
                    "mensaje": partes[3],
                })

        return commits

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Git no disponible o no es un repo: {e.stderr.strip()}")
        return []
    except Exception:
        print(f"⚠️  Error inesperado obteniendo historial:\n{traceback.format_exc()}")
        return []


def index_repository(reset: bool = False) -> None:
    """
    Pipeline principal de indexación.

    Args:
        reset: Si True, limpia la colección antes de re-indexar
               (evita duplicados en runs repetidas).
    """
    vector_store = RepoVectorStore()

    if reset:
        print("🗑️  Limpiando índice anterior...")
        vector_store.reset()  # Implementar en RepoVectorStore si no existe

    docs_to_index = []

    print("⏳ Obteniendo historial de Git...")
    raw_commits = fetch_raw_commits(limit=100)
    commit_docs = chunk_commits(raw_commits)
    print(f"   → {len(commit_docs)} commits útiles (de {len(raw_commits)} totales)")
    docs_to_index.extend(commit_docs)

    for filename in GUIDELINE_FILES:
        if os.path.exists(filename):
            print(f"📄 Procesando {filename}...")
            with open(filename, "r", encoding="utf-8") as f:
                guideline_docs = chunk_markdown_guidelines(f.read(), filename)
            print(f"   → {len(guideline_docs)} fragmentos")
            docs_to_index.extend(guideline_docs)

    if docs_to_index:
        print(f"\n📥 Indexando {len(docs_to_index)} fragmentos en ChromaDB por lotes...")
        
        batch_size = 50 
        for i in range(0, len(docs_to_index), batch_size):
            lote = docs_to_index[i:i + batch_size]
            vector_store.add_documents(lote)
            print(f"   → Lote {i // batch_size + 1} indexado ({len(lote)} fragmentos)")
            
        print("✅ Indexación completada.")
    else:
        print("❌ No se encontraron datos para indexar.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Indexa el repositorio en ChromaDB.")
    parser.add_argument(
        "--reset", action="store_true",
        help="Limpia el índice antes de re-indexar (evita duplicados)"
    )
    args = parser.parse_args()
    index_repository(reset=args.reset)