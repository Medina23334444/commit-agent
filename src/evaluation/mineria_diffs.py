import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

# 1. Cargar variables de entorno de forma segura
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise ValueError("Error: GITHUB_TOKEN no encontrado. Verifica tu archivo .env")

HEADERS_JSON = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
HEADERS_DIFF = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3.diff"
}

# 2. Muestra controlada de repositorios (Licencias permisivas)
REPOSITORIOS = [
    "langchain-ai/langgraph",
    "ollama/ollama",
    "tiangolo/fastapi",
    "vuejs/core",
    "zaproxy/zaproxy"
]

COMMITS_POR_REPO = int(os.getenv("COMMITS_POR_REPO", "50"))
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "8000"))

def extraer_diffs():
    dataset = []
    descartados_por_tamano = 0
    descartados_por_bots = 0
    descartados_por_idioma = 0
    descartados_administrativos = 0
    descartados_archivos_irrelevantes = 0

    print("Iniciando minería de datos avanzada y limpieza...")

    for repo in REPOSITORIOS:
        print(f"\nProcesando repositorio: {repo}")

        validos_repo = 0
        page = 1
        vistos_shas = set()

        while validos_repo < COMMITS_POR_REPO:
            url_commits = (
                f"https://api.github.com/repos/{repo}/commits"
                f"?per_page=100&page={page}"
            )
            response = requests.get(url_commits, headers=HEADERS_JSON)

            if response.status_code != 200:
                print(f"  [!] Error al obtener commits (página {page}): Código {response.status_code}")
                break

            commits = response.json()
            if not commits:
                print(f"  [i] Se acabó el historial de commits en la página {page}.")
                break

            for commit in commits:
                if validos_repo >= COMMITS_POR_REPO:
                    break

                sha = commit['sha']
                if sha in vistos_shas:
                    continue
                vistos_shas.add(sha)

                mensaje = commit['commit']['message']
                mensaje_lower = mensaje.lower()

                # Filtro 1: Omitir commits de merge
                if mensaje.startswith("Merge"):
                    continue

                # Filtro 2: Ignorar bots
                if "dependabot" in mensaje_lower or "renovate" in mensaje_lower:
                    descartados_por_bots += 1
                    continue
                
                # 🔥 Filtro 3 (NUEVO): Eliminar ruido administrativo en el mensaje
                # Atrapa: bumps de versión, chore(release), release notes, changelogs y commits exclusivos de docs
                ruido_textual = [
                    "release note", "changelog", "bump version", "chore(release",
                    "release(", "📝", "docs:"
                ]
                if any(ruido in mensaje_lower for ruido in ruido_textual):
                    descartados_administrativos += 1
                    # print(f"  [~] Descartado {sha[:7]} por ser ruido administrativo: {mensaje.splitlines()[0]}")
                    continue

                # Extraer el diff crudo de la modificación
                url_diff = f"https://api.github.com/repos/{repo}/commits/{sha}"
                diff_response = requests.get(url_diff, headers=HEADERS_DIFF)

                if diff_response.status_code == 200:
                    diff_texto = diff_response.text
                    texto_lower = diff_texto.lower()

                    # 🔥 Filtro 4 (NUEVO): Bloquear commits que consisten primariamente en archivos de bloqueo o historiales
                    archivos_basura = [
                        "b/uv.lock", "b/poetry.lock", "b/package-lock.json", 
                        "b/CHANGELOG.md", "b/docs/en/docs/release-notes.md", 
                        "b/pyproject.toml"
                    ]
                    # Si el diff contiene modificaciones a estos archivos, es probable que no sea lógica estructural
                    if any(archivo in diff_texto for archivo in archivos_basura):
                        descartados_archivos_irrelevantes += 1
                        continue

                    # Filtro 5: Restringir documentación a Inglés y Español
                    if "docs/" in texto_lower:
                        if not ("docs/en/" in texto_lower or "docs/es/" in texto_lower):
                            descartados_por_idioma += 1
                            continue
                    elif "locale/" in texto_lower or "i18n/" in texto_lower:
                        descartados_por_idioma += 1
                        continue

                    # Filtro 6: Límite de tamaño para proteger la inferencia local
                    if len(diff_texto) > MAX_DIFF_CHARS:
                        descartados_por_tamano += 1
                    else:
                        dataset.append({
                            "repositorio": repo,
                            "commit_hash": sha,
                            "mensaje_original": mensaje,
                            "diff": diff_texto
                        })
                        validos_repo += 1
                else:
                    print(f"  [!] Error al obtener diff del commit {sha[:7]}")

                # Pausa táctica para no saturar la API
                time.sleep(0.5)

            page += 1

        print(f"  -> Extracción de {repo} completada. ({validos_repo}/{COMMITS_POR_REPO} diffs válidos)")

    # 3. Exportar resultados
    if dataset:
        df = pd.DataFrame(dataset)
        nombre_archivo = "dataset_diffs_limpios.csv"
        df.to_csv(nombre_archivo, index=False, encoding='utf-8')
        print(f"\n¡Extracción finalizada exitosamente! Se guardaron {len(df)} registros en '{nombre_archivo}'.")
        print("\n--- Resumen de Limpieza (Descartes) ---")
        print(f" - Administrativos / Releases: {descartados_administrativos}")
        print(f" - Archivos irrelevantes (locks, changelogs): {descartados_archivos_irrelevantes}")
        print(f" - Tamaño excedido (> {MAX_DIFF_CHARS} chars): {descartados_por_tamano}")
        print(f" - Autogenerados por bots: {descartados_por_bots}")
        print(f" - Idiomas no admitidos (docs/i18n): {descartados_por_idioma}")
    else:
        print("\nNo se pudieron extraer datos.")

if __name__ == "__main__":
    extraer_diffs()