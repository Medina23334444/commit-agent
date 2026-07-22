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

# Límite de commits a extraer por repositorio (configurable en .env)
COMMITS_POR_REPO = int(os.getenv("COMMITS_POR_REPO", "50"))

# Límite de tamaño del diff en caracteres. Diffs más grandes que esto
# se descartan (no entran al dataset) porque en la práctica el LLM local
# (qwen2.5-coder:7b) no logra generar un mensaje válido con diffs tan largos.
# (configurable en .env)
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "15000"))


def extraer_diffs():
    dataset = []
    descartados_por_tamano = 0

    print("Iniciando minería de datos...")

    for repo in REPOSITORIOS:
        print(f"\nProcesando repositorio: {repo}")

        validos_repo = 0
        page = 1
        vistos_shas = set()

        # Sigue paginando hasta juntar COMMITS_POR_REPO diffs VÁLIDOS
        # (no se "gasta" el cupo en commits descartados por tamaño).
        # Corta también si GitHub deja de devolver commits (fin de historial).
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

                # Filtro: omitir commits de merge para mantener diffs aislados y limpios
                if mensaje.startswith("Merge"):
                    continue

                # Extraer el diff crudo de la modificación
                url_diff = f"https://api.github.com/repos/{repo}/commits/{sha}"
                diff_response = requests.get(url_diff, headers=HEADERS_DIFF)

                if diff_response.status_code == 200:
                    diff_texto = diff_response.text

                    # Filtro de tamaño: si supera MAX_DIFF_CHARS, se descarta
                    # y se sigue buscando (no cuenta para el cupo del repo).
                    if len(diff_texto) > MAX_DIFF_CHARS:
                        descartados_por_tamano += 1
                        print(f"  [~] Descartado {sha[:7]} por tamaño de diff "
                              f"({len(diff_texto)} chars > {MAX_DIFF_CHARS})")
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

                # Pausa táctica para no saturar los límites de la API
                time.sleep(0.5)

            page += 1

        print(f"  -> Extracción de {repo} completada. ({validos_repo}/{COMMITS_POR_REPO} diffs válidos)")

    # 3. Exportar resultados a CSV
    if dataset:
        df = pd.DataFrame(dataset)
        nombre_archivo = "dataset_diffs_historicos.csv"
        df.to_csv(nombre_archivo, index=False, encoding='utf-8')
        print(f"\n¡Extracción finalizada exitosamente! Se guardaron {len(df)} registros en '{nombre_archivo}'.")
        print(f"Se descartaron {descartados_por_tamano} commits por superar {MAX_DIFF_CHARS} caracteres de diff.")
    else:
        print("\nNo se pudieron extraer datos.")


if __name__ == "__main__":
    extraer_diffs()