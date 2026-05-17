# src/tools/git_tools.py
import os
import re
import subprocess
from langchain_core.tools import tool


def _get_cwd() -> str:
    return os.getcwd()


def _run_git(cmd: list[str]) -> str:
    """Ejecuta un comando git en el directorio actual."""
    cwd = _get_cwd()
    return subprocess.check_output(
        cmd, stderr=subprocess.STDOUT, cwd=cwd, env={**os.environ, "GIT_PAGER": ""}
    ).decode("utf-8", errors="ignore")


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS
# ══════════════════════════════════════════════════════════════════════════════


@tool
def get_git_diff() -> str:
    """Obtiene el diff del staging area. Sanitiza secrets automáticamente."""
    try:
        cwd = _get_cwd()
        result = subprocess.check_output(
            [
                "git",
                "diff",
                "--cached",
                "--",
                ".",
                # Archivos de configuración sensibles
                ":!.env*",
                ":!*.env",
                ":!*secret*",
                ":!*token*",
                ":!*credential*",
                ":!*password*",
                # Archivos binarios
                ":!*.png",
                ":!*.jpg",
                ":!*.jpeg",
                ":!*.gif",
                ":!*.pdf",
                ":!*.zip",
                ":!*.exe",
                ":!*.bin",
                ":!*.ico",
                # Archivos generados
                ":!*.lock",
                ":!*.pyc",
                ":!*.log",
                ":!*.tmp",
                ":!*.bak",
                ":!*.cache",
                # Carpetas generadas
                ":!dist/*",
                ":!build/*",
                ":!node_modules/*",
                ":!*/__pycache__/*",
                ":!*.egg-info/*",
            ],
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env={**os.environ, "GIT_PAGER": ""},
        )

        diff = result.decode("utf-8", errors="ignore")

        if not diff.strip():
            return "NO_DIFF"

        # Sanitiza secrets
        clean = re.sub(
            r"(AIza[0-9A-Za-z\-_]{35}|"
            r"sk-[a-zA-Z0-9]{32,}|"
            r"password\s*=\s*\S+|"
            r"secret\s*=\s*\S+|"
            r"token\s*=\s*\S+|"
            r"api_key\s*=\s*\S+)",
            "REDACTED_SECRET",
            diff,
            flags=re.IGNORECASE,
        )

        return clean[:15000] if len(clean) > 15000 else clean

    except Exception as e:
        return f"GIT_ERROR: {e}"


@tool
def get_repo_context() -> str:
    """Obtiene rama actual e historial de los últimos 5 commits."""
    try:
        rama = _run_git(["git", "branch", "--show-current"]).strip()
        historial = _run_git(["git", "log", "--oneline", "-5"]).strip()
        return f"Rama actual: {rama}\nHistorial reciente:\n{historial}"
    except Exception as e:
        return f"GIT_ERROR: {e}"


@tool
def parse_changed_files() -> str:
    """Parsea los archivos modificados con su estado (added, modified, deleted)."""
    try:
        output = _run_git(["git", "diff", "--cached", "--name-status"])
        if not output.strip():
            return "NO_DIFF"

        estados_map = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}

        archivos = []
        for line in output.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                estado = parts[0]
                archivo = parts[1]
                archivos.append(f"{estados_map.get(estado, estado)}: {archivo}")

        return "\n".join(archivos)
    except Exception as e:
        return f"GIT_ERROR: {e}"


@tool
def get_diff_stats() -> str:
    """Obtiene estadísticas del diff: archivos cambiados, líneas añadidas y eliminadas."""
    try:
        output = _run_git(["git", "diff", "--cached", "--stat"])
        return output.strip() if output.strip() else "sin estadísticas"
    except Exception as e:
        return f"GIT_ERROR: {e}"


@tool
def execute_git_commit(message: str) -> str:
    """Ejecuta el commit con el mensaje generado."""
    try:
        cwd = _get_cwd()
        result = subprocess.run(
            ["git", "commit", "-m", message], cwd=cwd, capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"OK: {result.stdout.strip()}"
        return f"ERROR: {result.stderr.strip()}"
    except Exception as e:
        return f"GIT_ERROR: {e}"
