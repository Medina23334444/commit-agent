# src/agent/router.py
from agent.state import AgentState

MAX_REINTENTOS = 3


class Router:
    """
    Controla el flujo del grafo mediante conditional edges.

    Pilares:
    1. Early exits   — aborta si no hay diff o falla la API
    2. Tolerancia    — maneja errores sin romper el grafo
    3. Refinamiento  — bucle controlado con límite de intentos
    """

    @staticmethod
    def after_analyzer(state: AgentState) -> str:
        """
        Salida temprana si:
        - No hay diff (NO_DIFF)
        - Error de git (GIT_ERROR)
        """
        error_type = state.get("error_type")

        if error_type == "NO_DIFF":
            print("ℹ️  No hay cambios para commitear.")
            return "abort"

        if error_type == "GIT_ERROR":
            print(f"❌ Error de git: {state.get('error_message')}")
            return "abort"

        return "continue"

    @staticmethod
    def after_comprehension(state: AgentState) -> str:
        """
        Salida temprana si el comprehension node falla.
        Si falla, igual continuamos con lo que tenemos.
        """
        if state.get("error_type") == "COMPREHENSION_ERROR":
            print(f"⚠️  Comprehension falló: {state.get('error_message')} — continuando sin contexto semántico.")
            return "continue"  # no abortamos, el generator puede trabajar sin esto

        return "continue"

    @staticmethod
    def after_generator(state: AgentState) -> str:
        """
        Salida temprana si:
        - La API falló (API_ERROR)
        - No se generó mensaje
        """
        error_type = state.get("error_type")

        if error_type == "API_ERROR":
            print(f"❌ Error de API: {state.get('error_message')}")
            return "abort"

        if not state.get("message"):
            print("❌ No se generó mensaje.")
            return "abort"

        return "continue"

    @staticmethod
    def after_validator(state: AgentState) -> str:
        """
        Bucle de refinamiento semántico con límite de intentos.

        approved → END
        refine   → RefinerNode
        abort    → END (límite alcanzado)
        """
        error_type = state.get("error_type")
        intentos   = state.get("intentos", 0)

        # ✅ Mensaje aprobado
        if not error_type or error_type == "VALID":
            print(f"✅ Mensaje aprobado en {intentos} intento(s).")
            return "approved"

        # 🛑 Límite de intentos alcanzado
        if intentos >= MAX_REINTENTOS:
            print(f"❌ Límite de {MAX_REINTENTOS} intentos alcanzado. Usando último mensaje generado.")
            return "abort"

        # 🔄 Necesita refinamiento
        print(f"🔄 Refinando mensaje (intento {intentos + 1}/{MAX_REINTENTOS})...")
        return "refine"