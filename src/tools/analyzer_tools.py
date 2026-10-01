# src/tools/analyzer_tools.py
import re
from langchain_core.tools import tool


def sample_diff_por_archivo(diff: str, limite_total: int = 3000) -> str:
    """
    Recorta un diff preservando representación de TODOS los archivos
    modificados, en vez de cortar ciegamente los primeros N caracteres
    (lo que deja invisibles los archivos que aparecen después del límite
    en diffs multi-archivo).

    Reparte el presupuesto de caracteres equitativamente entre bloques
    'diff --git ...' y toma el inicio de cada uno (donde vive la firma
    de la función/clase tocada, el @@ hunk header, etc. — la señal más
    densa para clasificación heurística).
    """
    if not diff or len(diff) <= limite_total:
        return diff

    bloques = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    bloques = [b for b in bloques if b.strip()]

    if len(bloques) <= 1:
        # Diff de un solo archivo: no hay nada que repartir, corte simple.
        return diff[:limite_total]

    presupuesto_por_bloque = max(limite_total // len(bloques), 200)

    partes = []
    for bloque in bloques:
        if len(bloque) <= presupuesto_por_bloque:
            partes.append(bloque)
        else:
            partes.append(
                bloque[:presupuesto_por_bloque]
                + f"\n... [truncado, archivo continúa: {len(bloque) - presupuesto_por_bloque} chars más]\n"
            )

    return "".join(partes)


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS
# ══════════════════════════════════════════════════════════════════════════════


@tool
def detect_commit_type(diff: str, archivos: str) -> str:
    """
    Detecta el tipo de commit más probable basándose en el diff y archivos modificados.
    Retorna: feat, fix, docs, style, refactor, test, chore, perf, ci, build
    """
    diff_lower = diff.lower()
    archivos_lower = archivos.lower()

    # ── Reglas de clasificación ───────────────────────────────────────────────
    rules = [
        # test
        (
            "test",
            any(x in archivos_lower for x in ["test", "spec"])
            or any(x in diff_lower for x in ["assert", "unittest", "pytest"]),
        ),
        # ci
        (
            "ci",
            any(
                x in archivos_lower
                for x in [".github", "ci.yml", "cd.yml", ".gitlab-ci", "jenkinsfile"]
            ),
        ),
        # build
        (
            "build",
            any(
                x in archivos_lower
                for x in [
                    "requirements",
                    "setup.py",
                    "pyproject",
                    "package.json",
                    "dockerfile",
                    "makefile",
                ]
            ),
        ),
        # docs
        (
            "docs",
            any(
                x in archivos_lower for x in ["readme", ".md", "docs/", "documentation"]
            ),
        ),
        # style
        (
            "style",
            any(
                x in diff_lower
                for x in ["black", "prettier", "eslint", "flake8", "isort"]
            )
            and not any(x in diff_lower for x in ["def ", "class "]),
        ),
        # perf
        (
            "perf",
            any(
                x in diff_lower
                for x in [
                    "cache",
                    "optimize",
                    "performance",
                    "speed",
                    "latency",
                    "async",
                ]
            ),
        ),
        # fix
        (
            "fix",
            any(
                x in diff_lower
                for x in [
                    "fix",
                    "bug",
                    "error",
                    "exception",
                    "traceback",
                    "raise",
                    "try:",
                    "except",
                    "null",
                    "none",
                ]
            ),
        ),
        # feat
        (
            "feat",
            any(
                x in diff_lower
                for x in [
                    "def ",
                    "class ",
                    "return",
                    "new",
                    "add",
                    "create",
                    "implement",
                ]
            ),
        ),
        # refactor
        (
            "refactor",
            any(
                x in diff_lower
                for x in [
                    "rename",
                    "move",
                    "restructure",
                    "cleanup",
                    "simplify",
                    "extract",
                ]
            ),
        ),
    ]

    for tipo, condicion in rules:
        if condicion:
            return tipo

    return "chore"  # fallback


@tool
def detect_scope(archivos: str) -> str:
    """
    Detecta el scope del commit basándose en los archivos modificados.
    Retorna el módulo o carpeta más relevante.
    """
    if not archivos or archivos == "no disponible":
        return ""

    # Extrae carpetas/módulos de las rutas
    scopes = []
    for linea in archivos.splitlines():
        # Elimina el estado (added:, modified:, etc.)
        ruta = linea.split(": ")[-1].strip()
        partes = ruta.replace("\\", "/").split("/")

        if len(partes) > 1:
            # Usa la primera carpeta como scope
            carpeta = partes[0]
            # Ignora carpetas genéricas
            if carpeta not in ["src", "app", ".", ""]:
                scopes.append(carpeta)
            elif len(partes) > 2:
                scopes.append(partes[1])

    if not scopes:
        return ""

    # Retorna el scope más frecuente
    scope_mas_frecuente = max(set(scopes), key=scopes.count)
    return scope_mas_frecuente


@tool
def summarize_changes(diff: str, archivos: str) -> str:
    """
    Genera un resumen estructurado de los cambios para enriquecer el prompt.
    """
    if not diff or diff == "NO_DIFF":
        return "sin cambios"

    # Cuenta estadísticas básicas
    lineas_añadidas = len(
        [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    )
    lineas_eliminadas = len(
        [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    )
    archivos_lista = archivos.splitlines() if archivos else []
    n_archivos = len(archivos_lista)

    # Detecta patrones relevantes
    patrones = []
    diff_lower = diff.lower()

    if "def " in diff_lower or "function " in diff_lower:
        patrones.append("funciones modificadas")
    if "class " in diff_lower:
        patrones.append("clases modificadas")
    if "import " in diff_lower:
        patrones.append("imports actualizados")
    if "test" in diff_lower:
        patrones.append("pruebas incluidas")
    if re.search(r"#.*todo|#.*fixme", diff_lower):
        patrones.append("TODOs/FIXMEs presentes")

    resumen = (
        f"Archivos modificados: {n_archivos}\n"
        f"Líneas añadidas: {lineas_añadidas}\n"
        f"Líneas eliminadas: {lineas_eliminadas}\n"
        f"Patrones detectados: {', '.join(patrones) if patrones else 'ninguno'}"
    )

    return resumen