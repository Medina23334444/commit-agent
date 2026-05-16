# src/tools/validation_tools.py
import re
from langchain_core.tools import tool


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

TIPOS_VALIDOS = {
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "test",
    "chore",
    "perf",
    "ci",
    "build",
}

PATRON_CONVENTIONAL = (
    r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build)(\(.+\))?!?: .{1,72}"
)


PALABRAS_VAGAS = [
    "fix stuff",
    "changes",
    "misc",
    "wip",
    "temp",
    "asdf",
    "aaa",
    "xxx",
    "update code",
    "many improvements",
    "various fixes",
    "minor changes",
    "some fixes",
]

# ══════════════════════════════════════════════════════════════════════════════
# SKILLS
# ══════════════════════════════════════════════════════════════════════════════


@tool
def validate_format(message: str) -> str:
    """
    Valida que el mensaje sigue el formato Conventional Commits.
    Retorna: VALID o INVALID: <razón>
    """
    if not message or not message.strip():
        return "INVALID: mensaje vacío"

    # ✅ siempre trabaja con la primera línea
    primera_linea = message.strip().splitlines()[0]

    if len(primera_linea) > 72:
        return f"INVALID: primera línea demasiado larga ({len(primera_linea)} chars). Máximo 72."

    if not re.match(PATRON_CONVENTIONAL, primera_linea):
        # Diagnóstico específico
        partes = primera_linea.split(":")
        if len(partes) < 2:
            return "INVALID: falta el separador ':' entre tipo y descripción"

        tipo_raw = partes[0].split("(")[0].replace("!", "").strip()
        if tipo_raw not in TIPOS_VALIDOS:
            return f"INVALID: tipo '{tipo_raw}' no es válido. Usa: {', '.join(sorted(TIPOS_VALIDOS))}"

        descripcion = partes[1].strip() if len(partes) > 1 else ""
        if not descripcion:
            return "INVALID: descripción vacía después de ':'"

        return (
            "INVALID: formato incorrecto. Usa <tipo>(<scope opcional>): <descripción>"
        )

    return "VALID"


@tool
def validate_semantic_quality(message: str, diff: str) -> str:
    """
    Valida la calidad semántica del mensaje.
    Detecta vaguedad, inconsistencia con el diff y falta de especificidad.
    Retorna: VALID o INVALID: <razón>
    """
    if not message:
        return "INVALID: mensaje vacío"

    message_lower = message.lower()
    diff_lower = diff.lower() if diff else ""

    # ── Detecta palabras vagas ─────────────────────────────────────────────
    for palabra in PALABRAS_VAGAS:
        patron = rf"\b{palabra}\b"
        if re.search(patron, message_lower):
            return f"INVALID: descripción vaga, usa verbos más precisos y evita '{palabra}' aislada"

    # ── Verifica que la descripción no sea solo el tipo repetido ──────────
    partes = message.split(":")
    descripcion = partes[-1].strip().lower() if partes else ""
    tipo = partes[0].split("(")[0].strip().lower() if partes else ""

    if (
        descripcion == tipo
        or descripcion == f"{tipo} code"
        or descripcion == f"{tipo}s"
    ):
        return f"INVALID: descripción repite el tipo '{tipo}', sé más específico"

    # ── Verifica consistencia básica con el diff ───────────────────────────
    if diff_lower:
        es_feat = "feat" in message_lower
        es_fix = "fix" in message_lower
        tiene_nuevo = any(x in diff_lower for x in ["def ", "class ", "new"])
        tiene_error = any(x in diff_lower for x in ["error", "exception", "bug", "fix"])

        if es_feat and not tiene_nuevo and tiene_error:
            return "INVALID: usas 'feat' pero el diff parece un fix"

        if es_fix and not tiene_error and tiene_nuevo:
            return "INVALID: usas 'fix' pero el diff parece un feat"

    return "VALID"


@tool
def validate_commit_message(message: str, diff: str) -> str:
    """
    Validación completa: formato + calidad semántica.
    Retorna: VALID o INVALID: <razón detallada>
    """
    # Primero valida formato
    formato = validate_format.invoke({"message": message})
    if formato != "VALID":
        return formato

    # Luego valida calidad semántica
    semantica = validate_semantic_quality.invoke({"message": message, "diff": diff})
    if semantica != "VALID":
        return semantica

    return "VALID"
