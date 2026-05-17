# src/nodes/comprehension.py
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt
from tools.analyzer_tools import (
    detect_commit_type,
    detect_scope,
    summarize_changes
)


class ComprehensionNode:
    """
    Nodo 3.2 — Comprehension Node (Análisis de Intención Semántica)

    Responsabilidades:
    - Detecta la intención del cambio
    - Clasifica el tipo de commit
    - Identifica módulos afectados (scope)
    - Genera resumen semántico del diff
    - Extrae el 'por qué' del cambio
    """

    def __init__(self, llm):
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        diff     = state.get("diff", "")
        archivos = self._archivos_a_str(state.get("archivos", []))

        # ── 1. Detectar tipo de commit ─────────────────────────────────────────
        tipo_detectado = self._detectar_tipo(diff, archivos)

        # ── 2. Detectar scope ──────────────────────────────────────────────────
        scope_detectado = self._detectar_scope(archivos)

        # ── 3. Generar resumen semántico ───────────────────────────────────────
        resumen = self._resumir_cambios(diff, archivos)

        # ── 4. Inferir intención con LLM ───────────────────────────────────────
        intencion = self._inferir_intencion(diff, archivos, tipo_detectado, resumen)

        return {
            **state,
            "tipo_detectado":  tipo_detectado,
            "scope_detectado": scope_detectado,
            "resumen":         resumen,
            "intencion":       intencion,
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

    def _inferir_intencion(
        self,
        diff:           str,
        archivos:       str,
        tipo_detectado: str,
        resumen:        str
    ) -> str:
        try:
            # ✅ CARGA DE PROMPTS DESDE ARCHIVOS EXTERNOS
            system_prompt = load_prompt("comprehension_system.md")
            user_prompt   = load_prompt(
                "comprehension_user.md",
                tipo_detectado=tipo_detectado,
                archivos=archivos,
                resumen=resumen,
                diff_resumido=diff[:2000] # Control de contexto para tu modelo local
            )

            response = self.llm.invoke([
                ("system", system_prompt),
                ("human",  user_prompt)
            ])
            return response.content.strip()
        except Exception as e:
            print(f"⚠️ Error en LLM Comprehension: {e}")
            return "intención no disponible"