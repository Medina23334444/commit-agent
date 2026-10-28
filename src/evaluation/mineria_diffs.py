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

# 2. Muestra controlada de repositorios
REPOSITORIOS = [
    "angular/angular",
    "vitejs/vite",
    "denoland/deno",
    "semantic-release/semantic-release",
    "commitizen/cz-cli"
]

COMMITS_POR_REPO = int(os.getenv("COMMITS_POR_REPO", "30"))
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "4500"))
MIN_LINEAS_CAMBIO = int(os.getenv("MIN_LINEAS_CAMBIO", "3"))
CUOTA_MAX_POR_TIPO = int(os.getenv("CUOTA_MAX_POR_TIPO", "20"))
# NUEVO: Longitud mínima del mensaje original para evitar mensajes vacíos o muy pobres
MIN_MENSAJE_CHARS = 15 


def clasificar_tipo(mensaje: str) -> str:
    """Clasifica el commit según Conventional Commits, o 'otro' si no aplica."""
    match = re.match(
        r"^(feat|fix|refactor|perf|test|build|ci|style|chore|docs)(\(.+\))?(!)?:\s*.+",
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
    vistos_diff_hash = set()

    descartados_por_tamano = 0
    descartados_por_bots = 0
    descartados_por_idioma = 0
    descartados_administrativos = 0
    descartados_archivos_irrelevantes = 0
    descartados_por_trivial = 0
    descartados_por_duplicado = 0
    descartados_por_cuota = 0
    
    # NUEVOS CONTADORES
    descartados_reverts = 0
    descartados_no_convencional = 0
    descartados_mensaje_corto = 0

    print("Iniciando minería de datos avanzada y limpieza...")

    for repo in REPOSITORIOS:
        print(f"\nProcesando repositorio: {repo}")

        validos_repo = 0
        page = 1
        vistos_shas = set()
        contador_tipo_repo = {}

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

                # NUEVO FILTRO: Mensajes demasiado cortos (ej: "fix")
                if len(mensaje.strip()) < MIN_MENSAJE_CHARS:
                    descartados_mensaje_corto += 1
                    continue

                # Filtro 1: Omitir commits de merge
                if mensaje.startswith("Merge") or mensaje.startswith("pull request"):
                    continue

                # NUEVO FILTRO: Omitir commits de tipo Revert
                if mensaje_lower.startswith("revert"):
                    descartados_reverts += 1
                    continue

                # Filtro 2 MEJORADO: Ignorar bots (Lista expandida)
                bots_conocidos = ["dependabot", "renovate", "snyk", "bot", "github-actions", "snyk-bot"]
                if any(bot in mensaje_lower for bot in bots_conocidos) or commit['commit']['author']['name'].lower().endswith("bot"):
                    descartados_por_bots += 1
                    continue

                # Filtro 3: Eliminar ruido administrativo en el mensaje
                is_release_or_bump = re.match(
                    r'^(?:chore(?:\(.*\))?:\s*)?(release[:(]|bump\b|version\b)', 
                    mensaje_lower
                )
                ruido_textual = ["release note", "changelog", "📝", "docs: update changelog"]
                
                if is_release_or_bump or any(ruido in mensaje_lower for ruido in ruido_textual):
                    descartados_administrativos += 1
                    continue

                # NUEVO FILTRO: Estricto Conventional Commits
                tipo = clasificar_tipo(mensaje)
                if tipo == "otro":
                    descartados_no_convencional += 1
                    continue

                # Control de cuota por tipo
                if contador_tipo_repo.get(tipo, 0) >= CUOTA_MAX_POR_TIPO:
                    descartados_por_cuota += 1
                    continue

                # Extraer el diff crudo
                url_diff = f"https://api.github.com/repos/{repo}/commits/{sha}"
                diff_response = requests.get(url_diff, headers=HEADERS_DIFF)

                if diff_response.status_code == 200:
                    diff_texto = diff_response.text
                    texto_lower = diff_texto.lower()

                    # Filtro 4 MEJORADO: Bloquear locks, historiales y archivos generados (dist/build)
                    rutas_modificadas = re.findall(r'^diff --git a/(\S+)', diff_texto, re.MULTILINE)
                    
                    archivos_basura_exactos = {
                        'Cargo.lock', 'package-lock.json', 'yarn.lock', 
                        'pnpm-lock.yaml', 'uv.lock', 'poetry.lock', 'pyproject.toml'
                    }
                    
                    tiene_basura = any(
                        ruta.split('/')[-1] in archivos_basura_exactos or 
                        'CHANGELOG' in ruta.upper() or
                        '/dist/' in ruta or 
                        '/build/' in ruta or
                        ruta.endswith('.min.js')
                        for ruta in rutas_modificadas
                    )

                    if tiene_basura:
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

                    # Filtro 6: Límite de tamaño 
                    if len(diff_texto) > MAX_DIFF_CHARS:
                        descartados_por_tamano += 1
                        continue

                    # Filtro 7: Descartar diffs triviales
                    lineas_cambio = contar_lineas_cambio(diff_texto)
                    if lineas_cambio < MIN_LINEAS_CAMBIO:
                        descartados_por_trivial += 1
                        continue

                    # Filtro 8: Dedup por contenido del diff
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
                        "diff_len": len(diff_texto),
                        "diff_lineas_cambio": lineas_cambio,
                        "tipo_commit": tipo,
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
        print(f" - Archivos irrelevantes (locks, changelogs, build/dist): {descartados_archivos_irrelevantes}")
        print(f" - Tamaño excedido (> {MAX_DIFF_CHARS} chars): {descartados_por_tamano}")
        print(f" - Triviales (< {MIN_LINEAS_CAMBIO} líneas de cambio): {descartados_por_trivial}")
        print(f" - Duplicados por contenido de diff: {descartados_por_duplicado}")
        print(f" - Descartados por cuota de tipo (máx {CUOTA_MAX_POR_TIPO}/repo): {descartados_por_cuota}")
        print(f" - Autogenerados por bots: {descartados_por_bots}")
        print(f" - Idiomas no admitidos (docs/i18n): {descartados_por_idioma}")
        print(f" - Reverts (generados por git): {descartados_reverts}")
        print(f" - No cumplen formato Conventional Commits: {descartados_no_convencional}")
        print(f" - Mensajes demasiado cortos (< {MIN_MENSAJE_CHARS} chars): {descartados_mensaje_corto}")
        print("\n--- Distribución final por tipo de commit ---")
        print(df["tipo_commit"].value_counts())
    else:
        print("\nNo se pudieron extraer datos.")

if __name__ == "__main__":
    extraer_diffs()