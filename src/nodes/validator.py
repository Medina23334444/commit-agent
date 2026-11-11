# src/nodes/validator.py
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt
from tools.validation_tools import validate_commit_message


class ValidatorNode:
    """
    Nodo 3.4 — Semantic Validator Node
    """

    MIN_PALABRAS_SIN_DUDA = 5

    def __init__(self, llm):
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        message = state.get("message", "")
        diff    = state.get("diff", "")

        resultado_formato = self._validar_formato(message, diff)
        if resultado_formato != "VALID":
            return self._rechazar(state, resultado_formato)

        if self._necesita_revision_llm(message):
            resultado_semantico = self._validar_semantica(state)
            if resultado_semantico != "APROBADO":
                critica = resultado_semantico.replace("MEJORAR:", "").strip()
                return self._rechazar(state, critica)

        return self._aprobar(state)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _necesita_revision_llm(self, message: str) -> bool:
        """Filtra commits triviales para ahorrar llamadas al LLM."""
        lineas = message.strip().splitlines()
        
        # Si no tiene body, y el header es corto, no revisar
        if len(lineas) == 1:
            return False
            
        # Si tiene body, pero el body no tiene viñetas claras ("Qué cambia:", "Por qué:"), revisar
        NL = chr(10)
        body = NL.join(lineas[1:])
        if "Qué cambia:" not in body or "Por qué:" not in body:
            return True
            
        return False

    def _validar_formato(self, message: str, diff: str) -> str:
        try:
            return validate_commit_message.invoke({
                "message": message,
                "diff":    diff
            })
        except Exception as e:
            print(f"⚠️ Validación de formato falló, dejando pasar sin validar: {e}")
            return "VALID"

    def _validar_semantica(self, state: AgentState) -> str:
        """Validación semántica simulando revisión de un Senior Code Reviewer."""
        try:
            message = state.get("message", "")
            archivos_lista = state.get("archivos", [])
            NL = chr(10)
            archivos = NL.join(f"- {a}" for a in archivos_lista) if archivos_lista else "(No se detectaron archivos)"

            diff_resumido = state.get("diff", "")[:4500]

            system_prompt = load_prompt("validator_system.md")
            
            user_prompt = f"""Evalúa el siguiente mensaje de commit basándote en claridad, trazabilidad y completitud técnica.

Archivos modificados:
{archivos}

Diff de referencia:
{diff_resumido}

Mensaje generado:
{message}

Si el mensaje omite archivos importantes del diff o si su sección 'Por qué' es genérica (ej. 'para mejorar' o 'para optimizar') sin explicar qué regla de negocio o problema técnico motivó el cambio, RECHÁZALO.

Responde ÚNICAMENTE con la palabra "APROBADO" si cumple todo perfectamente.
Si falla, responde "MEJORAR:" seguido de la instrucción exacta de lo que debe corregir el Refinador."""

            response = self.llm.invoke([("system", system_prompt), ("human",  user_prompt)])
            return response.content.strip()
        except Exception as e:
            print(f"⚠️ Validación semántica (LLM) falló: {e}")
            return "APROBADO"

    def _rechazar(self, state: AgentState, critica: str) -> AgentState:
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
        return {
            **state,
            "critica":       None,
            "error_type":    None,
            "error_node":    None,
            "error_message": None,
        }
