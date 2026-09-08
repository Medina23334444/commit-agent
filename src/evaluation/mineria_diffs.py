import os
import re
import time
import hashlib
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
    "angular/angular",
    "vitejs/vite",
    "denoland/deno",
    "semantic-release/semantic-release",
    "commitizen/cz-cli"
]

COMMITS_POR_REPO = int(os.getenv("COMMITS_POR_REPO", "30"))

# CAMBIO 1: bajado de 8000 a 4500. Por encima de 5000 chars, el pipeline
# del agente falla en ~48% de los casos (context window), y >6000 en ~62%.
# Ver análisis: tasa de ERROR_DE_GENERACION correlaciona con diff_len.
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "4500"))

# CAMBIO 2: mínimo de líneas de cambio reales (+/-) para descartar diffs triviales
MIN_LINEAS_CAMBIO = int(os.getenv("MIN_LINEAS_CAMBIO", "3"))

# CAMBIO 3: cuota máxima por tipo de commit (estratificación), para que
# "fix" no domine el dataset solo por ser el más frecuente cronológicamente.
CUOTA_MAX_POR_TIPO = int(os.getenv("CUOTA_MAX_POR_TIPO", "20"))  # de 50 por repo


def clasificar_tipo(mensaje: str) -> str:
    """Clasifica el commit según Conventional Commits, o 'otro' si no aplica."""
    match = re.match(
        r"^(feat|fix|refactor|perf|test|build|ci|style|chore|docs)(\(.+\))?:",
        mensaje.lower()
    )
    return match.group(1) if match else "otro"


def contar_lineas_cambio(diff_texto: str) -> int:
    """Cuenta líneas +/- reales, ignorando los headers +++ / ---."""
    return sum(
        1 for l in diff_texto.splitlines()
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
    )


def extraer_diffs():
    dataset = []
    vistos_diff_hash = set()  # CAMBIO 4: dedup por contenido, no solo por SHA

    descartados_por_tamano = 0
    descartados_por_bots = 0
    descartados_por_idioma = 0
    descartados_administrativos = 0
    descartados_archivos_irrelevantes = 0
    descartados_por_trivial = 0
    descartados_por_duplicado = 0
    descartados_por_cuota = 0

    print("Iniciando minería de datos avanzada y limpieza...")

    for repo in REPOSITORIOS:
        print(f"\nProcesando repositorio: {repo}")

        validos_repo = 0
        page = 1
        vistos_shas = set()
        contador_tipo_repo = {}  # CAMBIO 3: cuota por tipo, por repo

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

                # Filtro 3: Eliminar ruido administrativo en el mensaje
                ruido_textual = [
                    "release note", "changelog", "bump version", "chore(release",
                    "release(", "📝", "docs:"
                ]
                if any(ruido in mensaje_lower for ruido in ruido_textual):
                    descartados_administrativos += 1
                    continue

                # CAMBIO 3: cuota por tipo — si ya llegamos al máximo de este
                # tipo en este repo, saltamos el commit (así no se llena todo de "fix")
                tipo = clasificar_tipo(mensaje)
                if contador_tipo_repo.get(tipo, 0) >= CUOTA_MAX_POR_TIPO:
                    descartados_por_cuota += 1
                    continue

                # Extraer el diff crudo de la modificación
                url_diff = f"https://api.github.com/repos/{repo}/commits/{sha}"
                diff_response = requests.get(url_diff, headers=HEADERS_DIFF)

                if diff_response.status_code == 200:
                    diff_texto = diff_response.text
                    texto_lower = diff_texto.lower()

                    # Filtro 4: Bloquear archivos de bloqueo/historiales
                    archivos_basura = [
                        "b/uv.lock", "b/poetry.lock", "b/package-lock.json",
                        "b/CHANGELOG.md", "b/docs/en/docs/release-notes.md",
                        "b/pyproject.toml"
                    ]
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

                    # Filtro 6: Límite de tamaño (ahora 4500, ver CAMBIO 1)
                    if len(diff_texto) > MAX_DIFF_CHARS:
                        descartados_por_tamano += 1
                        continue

                    # CAMBIO 2: descartar diffs triviales (whitespace, permisos, etc.)
                    lineas_cambio = contar_lineas_cambio(diff_texto)
                    if lineas_cambio < MIN_LINEAS_CAMBIO:
                        descartados_por_trivial += 1
                        continue

                    # CAMBIO 4: dedup por contenido del diff (no solo SHA)
                    diff_hash = hashlib.md5(diff_texto.encode()).hexdigest()
                    if diff_hash in vistos_diff_hash:
                        descartados_por_duplicado += 1
                        continue
                    vistos_diff_hash.add(diff_hash)

                    dataset.append({
                        "repositorio": repo,
                        "commit_hash": sha,
                        "mensaje_original": mensaje,
                        "diff": diff_texto,
                        "diff_len": len(diff_texto),          # CAMBIO 5: metadata
                        "diff_lineas_cambio": lineas_cambio,   # CAMBIO 5: metadata
                        "tipo_commit": tipo,                   # CAMBIO 5: metadata
                    })
                    validos_repo += 1
                    contador_tipo_repo[tipo] = contador_tipo_repo.get(tipo, 0) + 1
                else:
                    print(f"  [!] Error al obtener diff del commit {sha[:7]}")

                time.sleep(0.5)

            page += 1

        print(f"  -> Extracción de {repo} completada. ({validos_repo}/{COMMITS_POR_REPO} diffs válidos)")
        print(f"     Distribución por tipo: {contador_tipo_repo}")

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
        print(f" - Triviales (< {MIN_LINEAS_CAMBIO} líneas de cambio): {descartados_por_trivial}")
        print(f" - Duplicados por contenido de diff: {descartados_por_duplicado}")
        print(f" - Descartados por cuota de tipo (máx {CUOTA_MAX_POR_TIPO}/repo): {descartados_por_cuota}")
        print(f" - Autogenerados por bots: {descartados_por_bots}")
        print(f" - Idiomas no admitidos (docs/i18n): {descartados_por_idioma}")
        print("\n--- Distribución final por tipo de commit ---")
        print(df["tipo_commit"].value_counts())
    else:
        print("\nNo se pudieron extraer datos.")


if __name__ == "__main__":
    extraer_diffs()