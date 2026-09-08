# src/nodes/validator.py
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt
from tools.validation_tools import validate_commit_message


class ValidatorNode:
    """
    Nodo 3.4 — Semantic Validator Node

    Responsabilidades:
    - Valida formato Conventional Commits + calidad semántica heurística
      (regex, sin LLM) vía validate_commit_message
    - Solo si el mensaje es un caso límite, hace una segunda pasada semántica
      con LLM para desempatar
    - Genera crítica específica para el refiner

    NOTA DE OPTIMIZACIÓN:
    Antes se llamaba al LLM siempre, en cada validación, incluso cuando
    validate_commit_message (regex + reglas de vaguedad) ya era concluyente.
    Ahora el LLM solo se invoca en casos ambiguos (ver _necesita_revision_llm),
    ahorrando ~1-1.5s en el camino feliz (mensaje claro y bien formado).
    """

    # Umbral: si la descripción tiene menos palabras que esto, es "corta"
    # y se considera caso límite digno de una segunda opinión del LLM.
    MIN_PALABRAS_SIN_DUDA = 5

    def __init__(self, llm):
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        message = state.get("message", "")
        diff    = state.get("diff", "")

        # ── 1. Validación estructural + semántica heurística (regex) ───────────
        resultado_formato = self._validar_formato(message, diff)
        if resultado_formato != "VALID":
            return self._rechazar(state, resultado_formato)

        # ── 2. Validación semántica con LLM — SOLO si es un caso límite ────────
        if self._necesita_revision_llm(message):
            resultado_semantico = self._validar_semantica(state)
            if resultado_semantico != "APROBADO":
                critica = resultado_semantico.replace("MEJORAR:", "").strip()
                return self._rechazar(state, critica)

        # ── 3. Aprobado ────────────────────────────────────────────────────────
        return self._aprobar(state)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _necesita_revision_llm(self, message: str) -> bool:
        """
        Decide si el mensaje amerita una segunda pasada semántica con LLM.

        Se considera caso límite (necesita LLM) si:
        - La descripción tiene pocas palabras (riesgo de vaguedad que el
          regex de validate_commit_message no haya detectado).
        - El mensaje tiene body con cambios secundarios (más superficie
          para inconsistencias que vale la pena que revise el LLM).

        Si el mensaje es claro, con descripción de longitud normal y sin
        body, se confía en la validación heurística y se ahorra la llamada.
        """
        primera_linea = message.strip().splitlines()[0] if message.strip() else ""

        # Extrae la descripción después de ":"
        partes = primera_linea.split(":", 1)
        descripcion = partes[1].strip() if len(partes) > 1 else ""
        n_palabras = len(descripcion.split())

        tiene_body = len(message.strip().splitlines()) > 1

        return n_palabras < self.MIN_PALABRAS_SIN_DUDA or tiene_body

    def _validar_formato(self, message: str, diff: str) -> str:
        """Validación estructural + semántica heurística usando validation_tools."""
        try:
            return validate_commit_message.invoke({
                "message": message,
                "diff":    diff
            })
        except Exception as e:
            print(f"⚠️ Validación de formato falló, dejando pasar sin validar: {e}")
            return "VALID"  # fail-open registrado: si falla la tool, deja pasar al LLM

    def _validar_semantica(self, state: AgentState) -> str:
        """Validación semántica usando LLM (solo para casos límite)."""
        try:
            # El límite de contexto que ve el validador depende de si el
            # mensaje tiene body: solo ahí necesita verificar cobertura de
            # múltiples archivos/cambios contra el diff completo. Para el
            # caso "descripción corta sin body" (cambios triviales de 1
            # línea) no vale la pena pagar el token extra.
            message = state.get("message", "")
            tiene_body = len(message.strip().splitlines()) > 1
            limite = 4500 if tiene_body else 500

            system_prompt = load_prompt("validator_system.md")
            user_prompt   = load_prompt(
                "validator_user.md",
                message      = message,
                intencion    = state.get("intencion", "no disponible"),
                diff_resumido = state.get("diff", "")[:limite]
            )

            response = self.llm.invoke([
                ("system", system_prompt),
                ("human",  user_prompt)
            ])
            return response.content.strip()

        except Exception as e:
            print(f"⚠️ Validación semántica (LLM) falló, dejando pasar sin validar: {e}")
            return "APROBADO"  # fail-open registrado: si falla el LLM, deja pasar

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