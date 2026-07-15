# src/nodes/analyzer.py
import os
import re
import subprocess
from agent.state import AgentState
from tools.git_tools import (
    get_git_diff,
    get_repo_context,
    parse_changed_files,
    get_diff_stats
)


class AnalyzerNode:
    """
    Nodo 3.1 — Diff Analyzer Node
    
    Responsabilidades:
    - Obtiene el diff del staging area
    - Parsea archivos modificados
    - Obtiene contexto del repositorio
    - Obtiene estadísticas del diff
    - Sanitiza el diff antes de continuar
    """

    def run(self, state: AgentState) -> AgentState:
        # ── 1. Obtener diff ────────────────────────────────────────────────────
        diff = get_git_diff.invoke({})

        if diff == "NO_DIFF":
            return {
                **state,
                "error_type": "NO_DIFF",
                "error_node": "analyzer",
                "error_message": "No hay cambios en staging. Ejecuta 'git add' primero."
            }

        if diff.startswith("GIT_ERROR"):
            return {
                **state,
                "error_type": "GIT_ERROR",
                "error_node": "analyzer",
                "error_message": diff
            }

        # ── 2. Obtener contexto del repo ───────────────────────────────────────
        contexto_raw = get_repo_context.invoke({})
        rama, historial = self._parse_contexto(contexto_raw)

        # ── 3. Parsear archivos modificados ────────────────────────────────────
        archivos_raw = parse_changed_files.invoke({})
        archivos = self._parse_archivos(archivos_raw)

        # ── 4. Obtener estadísticas ────────────────────────────────────────────
        estadisticas = self._parse_estadisticas(diff)

        return {
            **state,
            "diff": diff,
            "rama": rama,
            "historial": historial,
            "archivos": archivos,
            "estadisticas": estadisticas,
            # Se eliminó la inyección del contexto_repo (RAG) de aquí
            "error_type": None,
            "error_node": None,
            "error_message": None,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _parse_contexto(self, contexto_raw: str) -> tuple[str, list[str]]:
        """Parsea el resultado de get_repo_context en rama e historial."""
        if not contexto_raw or "GIT_ERROR" in contexto_raw:
            return "unknown", []

        lineas  = contexto_raw.splitlines()
        rama    = lineas[0].replace("Rama actual: ", "").strip() if lineas else "unknown"
        historial = [
            l.strip() for l in lineas[2:]
            if l.strip()
        ]
        return rama, historial

    def _parse_archivos(self, archivos_raw: str) -> list[str]:
        """Convierte el output de parse_changed_files en lista."""
        if not archivos_raw or archivos_raw in ("NO_DIFF", "") or "GIT_ERROR" in archivos_raw:
            return []
        return [l.strip() for l in archivos_raw.splitlines() if l.strip()]

    def _parse_estadisticas(self, diff: str) -> dict[str, int]:
        """Calcula estadísticas del diff."""
        lineas      = diff.splitlines()
        added       = len([l for l in lineas if l.startswith("+") and not l.startswith("+++")])
        deleted     = len([l for l in lineas if l.startswith("-") and not l.startswith("---")])
        files       = len([l for l in lineas if l.startswith("diff --git")])
        return {
            "added":   added,
            "deleted": deleted,
            "files":   files,
            "net":     added - deleted
        }