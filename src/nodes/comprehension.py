# src/nodes/comprehension.py
from agent.state import AgentState
from tools.analyzer_tools import (
    detect_commit_type,
    detect_scope,
    summarize_changes
)
from rag.retriever import get_repo_context_rag


class ComprehensionNode:
    """
    Nodo 3.2 — Comprehension Node (Análisis de Intención Semántica)

    Responsabilidades:
    - Clasifica el tipo de commit (heurística, sin LLM)
    - Identifica módulos afectados / scope (heurística, sin LLM)
    - Genera resumen estructurado del diff (heurística, sin LLM)
    - Recupera contexto semántico histórico (RAG)

    NOTA DE OPTIMIZACIÓN:
    Antes este nodo hacía una llamada LLM adicional (_inferir_intencion) solo
    para describir el "por qué" del cambio en una oración. Esa llamada era
    redundante: el generator ya recibe el diff completo y su system prompt
    le pide priorizar la intención por sobre el "cómo". Se eliminó esa llamada
    y se reutiliza `resumen` (ya calculado sin LLM) como campo de "intención"
    para generator/validator. Esto reduce de 3 a 2 las invocaciones al LLM
    por corrida exitosa.
    """

    def __init__(self, llm=None):
        # Se mantiene el parámetro por compatibilidad con CommitGraph,
        # pero ya no se usa un LLM en este nodo.
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        diff     = state.get("diff", "")
        archivos = self._archivos_a_str(state.get("archivos", []))

        # ── 1. Detectar tipo de commit ─────────────────────────────────────────
        tipo_detectado = self._detectar_tipo(diff, archivos)

        # ── 2. Detectar scope ──────────────────────────────────────────────────
        scope_detectado = self._detectar_scope(archivos)

        # ── 3. Generar resumen semántico (heurístico, sin LLM) ─────────────────
        resumen = self._resumir_cambios(diff, archivos)

        # ── 4. Búsqueda RAG (Semántica Inteligente) ─────────────────────────────
        contexto_rag = get_repo_context_rag(query=resumen, k=3)

        # ── 5. "Intención" reutiliza el resumen — ya no hay llamada LLM aquí ────
        intencion = resumen

        return {
            **state,
            "tipo_detectado":  tipo_detectado,
            "scope_detectado": scope_detectado,
            "resumen":         resumen,
            "intencion":       intencion,
            "contexto_repo":   contexto_rag,
            "error_type":      None,
            "error_node":      None,
            "error_message":   None,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _archivos_a_str(self, archivos: list) -> str:
        """Convierte lista de archivos a string para las tools."""
        if not archivos:
            return ""
        return "\n".join(archivos)

    def _detectar_tipo(self, diff: str, archivos: str) -> str:
        """Usa la skill detect_commit_type para clasificar el cambio."""
        try:
            return detect_commit_type.invoke({
                "diff":     diff[:3000],
                "archivos": archivos
            })
        except Exception:
            return "chore"

    def _detectar_scope(self, archivos: str) -> str:
        """Usa la skill detect_scope para identificar el módulo afectado."""
        try:
            return detect_scope.invoke({"archivos": archivos})
        except Exception:
            return ""

    def _resumir_cambios(self, diff: str, archivos: str) -> str:
        """Usa la skill summarize_changes para generar resumen estructurado."""
        try:
            return summarize_changes.invoke({
                "diff":     diff[:3000],
                "archivos": archivos
            })
        except Exception:
            return "sin resumen disponible"