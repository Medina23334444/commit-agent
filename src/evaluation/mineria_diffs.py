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

# Límite de commits a extraer por repositorio
COMMITS_POR_REPO = 50

def extraer_diffs():
    dataset = []

    print("Iniciando minería de datos...")
    
    for repo in REPOSITORIOS:
        print(f"\nProcesando repositorio: {repo}")
        url_commits = f"https://api.github.com/repos/{repo}/commits?per_page={COMMITS_POR_REPO}"
        
        response = requests.get(url_commits, headers=HEADERS_JSON)
        
        if response.status_code != 200:
            print(f"  [!] Error al obtener commits: Código {response.status_code}")
            continue

        commits = response.json()

        for commit in commits:
            sha = commit['sha']
            mensaje = commit['commit']['message']
            
            # Filtro: omitir commits de merge para mantener diffs aislados y limpios
            if mensaje.startswith("Merge"):
                continue

            # Extraer el diff crudo de la modificación
            url_diff = f"https://api.github.com/repos/{repo}/commits/{sha}"
            diff_response = requests.get(url_diff, headers=HEADERS_DIFF)
            
            if diff_response.status_code == 200:
                dataset.append({
                    "repositorio": repo,
                    "commit_hash": sha,
                    "mensaje_original": mensaje,
                    "diff": diff_response.text
                })
            else:
                print(f"  [!] Error al obtener diff del commit {sha[:7]}")
            
            # Pausa táctica para no saturar los límites de la API
            time.sleep(0.5)
            
        print(f"  -> Extracción de {repo} completada.")

    # 3. Exportar resultados a CSV
    if dataset:
        df = pd.DataFrame(dataset)
        nombre_archivo = "dataset_diffs_historicos.csv"
        df.to_csv(nombre_archivo, index=False, encoding='utf-8')
        print(f"\n¡Extracción finalizada exitosamente! Se guardaron {len(df)} registros en '{nombre_archivo}'.")
    else:
        print("\nNo se pudieron extraer datos.")

if __name__ == "__main__":
    extraer_diffs()