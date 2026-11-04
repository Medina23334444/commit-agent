# src/nodes/comprehension.py
from langchain_core.messages import HumanMessage, SystemMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt
from tools.analyzer_tools import (
    detect_commit_type,
    detect_scope,
    summarize_changes,
    sample_diff_por_archivo,
)
from rag.retriever import get_repo_context_rag


class ComprehensionNode:
    """
    Nodo 3.2 — Comprehension Node (Análisis de Intención Semántica)

    Responsabilidades:
    - Clasifica el tipo de commit (heurística, sin LLM)
    - Identifica módulos afectados / scope (heurística, sin LLM)
    - Genera resumen estructurado del diff (heurística, sin LLM)
    - Infiere la intención ("por qué") real del cambio (1 llamada LLM)
    - Recupera contexto semántico histórico (RAG)

    NOTA: se restauró la llamada LLM a _inferir_intencion. Se había sacado
    para pasar de 3 a 2 llamadas por corrida, reutilizando `resumen` (el
    "qué", heurístico) como si fuera la "intención" (el "por qué"). Eso
    dejaba al generador sin ningún "por qué" razonado de verdad -- solo
    con el "qué" duplicado bajo otro nombre, lo que probablemente pesaba
    en la métrica de Rationality. Si `self.llm` no está disponible o la
    llamada falla, cae de nuevo a `resumen` como antes (mismo
    comportamiento de fallback, no rompe la resiliencia del pipeline).
    """

    def __init__(self, llm=None):
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

        # ── 5. Inferir intención real del "por qué" (1 llamada LLM) ─────────────
        intencion = self._inferir_intencion(diff, archivos, tipo_detectado, resumen)

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
                "diff":     sample_diff_por_archivo(diff, limite_total=3000),
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
                "diff":     sample_diff_por_archivo(diff, limite_total=3000),
                "archivos": archivos
            })
        except Exception:
            return "sin resumen disponible"

    def _inferir_intencion(self, diff: str, archivos: str, tipo_detectado: str, resumen: str) -> str:
        """
        Llama al LLM para inferir el PORQUÉ real del cambio, en una sola
        oración corta, distinto del resumen heurístico del QUÉ.
        Si no hay LLM disponible o la llamada falla, cae a `resumen`
        (mismo comportamiento que antes de restaurar esta llamada).
        """
        if self.llm is None:
            return resumen
        try:
            system_prompt = load_prompt("comprehension_system.md")
            user_prompt = load_prompt(
                "comprehension_user.md",
                tipo_detectado=tipo_detectado,
                archivos=archivos,
                resumen=resumen,
                diff_resumido=sample_diff_por_archivo(diff, limite_total=2000),
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            respuesta = self.llm.invoke(messages)
            texto = respuesta.content.strip()
            return texto if texto else resumen
        except Exception:
            return resumen
