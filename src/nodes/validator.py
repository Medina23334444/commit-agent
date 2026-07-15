# src/nodes/validator.py
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt
from tools.validation_tools import validate_commit_message


class ValidatorNode:
    """
    Nodo 3.4 — Semantic Validator Node

    Responsabilidades:
    - Valida formato Conventional Commits con Regex
    - Valida calidad semántica con LLM
    - Detecta ambigüedad o vaguedad
    - Aplica reglas de validación
    - Genera crítica específica para el refiner
    """

    def __init__(self, llm):
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        message = state.get("message", "")
        diff    = state.get("diff", "")

        # ── 1. Validación estructural con Regex ────────────────────────────────
        resultado_formato = self._validar_formato(message, diff)
        if resultado_formato != "VALID":
            return self._rechazar(state, resultado_formato)

        # ── 2. Validación semántica con LLM ────────────────────────────────────
        resultado_semantico = self._validar_semantica(state)
        if resultado_semantico != "APROBADO":
            critica = resultado_semantico.replace("MEJORAR:", "").strip()
            return self._rechazar(state, critica)

        # ── 3. Aprobado ────────────────────────────────────────────────────────
        return self._aprobar(state)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _validar_formato(self, message: str, diff: str) -> str:
        """Validación estructural usando validation_tools."""
        try:
            return validate_commit_message.invoke({
                "message": message,
                "diff":    diff
            })
        except Exception:
            return "VALID"  # si falla la tool, deja pasar al LLM

    def _validar_semantica(self, state: AgentState) -> str:
        """Validación semántica usando LLM."""
        try:
            system_prompt = load_prompt("validator_system.md")
            user_prompt   = load_prompt(
                "validator_user.md",
                message      = state.get("message", ""),
                intencion    = state.get("intencion", "no disponible"),
                diff_resumido = state.get("diff", "")[:500]
            )

            response = self.llm.invoke([
                ("system", system_prompt),
                ("human",  user_prompt)
            ])
            return response.content.strip()

        except Exception:
            return "APROBADO"  # si falla el LLM, deja pasar

    def _rechazar(self, state: AgentState, critica: str) -> AgentState:
        """Rechaza el mensaje e incrementa intentos."""
        intentos = state.get("intentos", 0) + 1

        return {
            **state,
            "critica":     critica,
            "intentos":    intentos,
            "error_type":  "INVALID",
            "error_node":  "validator",
            "error_message": critica,
            "messages": [
                AIMessage(content=state.get("message", "")),
                HumanMessage(content=f"RECHAZADO: {critica}")
            ]
        }

    def _aprobar(self, state: AgentState) -> AgentState:
        """Aprueba el mensaje."""
        return {
            **state,
            "critica":       None,
            "error_type":    None,
            "error_node":    None,
            "error_message": None,
        }