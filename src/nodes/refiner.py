# src/nodes/refiner.py
from agent import state
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt


class RefinerNode:
    """
    Nodo 3.5 — Iterative Semantic Refinement Node

    Responsabilidades:
    - Regenera el mensaje usando la crítica del validator
    - Ajusta tipo y scope si fueron incorrectos
    - Usa historial de intentos para no repetir errores
    - Reintento controlado con contexto enriquecido
    """

    def __init__(self, llm):
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        # ── 1. Construir mensajes con historial ────────────────────────────────
        messages = self._build_messages(state)

        # ── 2. Invocar LLM ────────────────────────────────────────────────────
        try:
            response = self.llm.invoke(messages)
            mensaje = response.content.strip()
            mensaje = self._limpiar_mensaje(mensaje)
            print(f"🔄 Mensaje refinado: {mensaje}")

            # Agrega al historial
            nuevos_messages = [
                HumanMessage(content=f"CRÍTICA: {state.get('critica', '')}"),
                AIMessage(content=mensaje),
            ]

            return {
                **state,
                "message": mensaje,
                "messages": nuevos_messages,
                "error_type": None,
                "error_node": None,
                "error_message": None,
            }

        except Exception as e:
            return {
                **state,
                "error_type": "API_ERROR",
                "error_node": "refiner",
                "error_message": str(e),
            }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _limpiar_mensaje(self, mensaje: str) -> str:
        import re
        import json

        mensaje = mensaje.strip()

        # Elimina bloques de markdown primero
        mensaje = re.sub(r"```[\w]*\n?", "", mensaje)
        mensaje = re.sub(r"```", "", mensaje).strip()

        # Intenta extraer de JSON
        try:
            data = json.loads(mensaje)
            if isinstance(data, dict):
                for key in ["response", "message", "commit", "result"]:
                    if key in data:
                        valor = data[key]
                        # Solo usa si parece un commit válido
                        if re.match(
                            r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build)",
                            valor,
                        ):
                            mensaje = valor
                            break
        except Exception:
            pass

        # Toma la primera línea válida con formato Conventional Commits
        for linea in mensaje.splitlines():
            linea = linea.strip()
            if re.match(
                r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build)", linea
            ):
                return self._truncar_primera_linea(linea)

        # Si no encuentra nada válido retorna vacío para forzar error
        return ""

    def _truncar_primera_linea(self, mensaje: str) -> str:
        lineas = mensaje.strip().splitlines()
        if not lineas:
            return mensaje
        primera = lineas[0]
        if len(primera) <= 72:
            return mensaje

        # Trunca en la última palabra completa que quepa
        truncada = primera[:72].rsplit(" ", 1)[0]

        # Elimina palabras conectoras al final (y, con, de, para, el, la)
        conectores = {"y", "con", "de", "para", "el", "la", "los", "las", "a", "o"}
        palabras = truncada.split()
        while palabras and palabras[-1].lower() in conectores:
            palabras.pop()

        truncada = " ".join(palabras)
        lineas[0] = truncada
        return "\n".join(lineas)

    def _build_messages(self, state: AgentState) -> list:
        """
        Construye mensajes para el LLM incluyendo:
        - System prompt del refiner
        - Historial de intentos fallidos
        - Crítica actual
        - Contexto del diff
        """
        system_prompt = load_prompt("refiner_system.md")

        user_prompt = load_prompt(
            "refiner_user.md",
            message=state.get("message", ""),
            critica=state.get("critica", "no cumple Conventional Commits"),
            intencion=state.get("intencion", "no disponible"),
            tipo_detectado=state.get("tipo_detectado", "no detectado"),
            scope_detectado=state.get("scope_detectado", "no detectado"),
            diff_resumido=state.get("diff", "")[:500],
        )

        messages = [("system", system_prompt)]

        # Inyecta historial de intentos fallidos
        historial = state.get("messages", [])
        if historial:
            messages.append(
                (
                    "system",
                    "Historial de intentos anteriores — no repitas estos errores:",
                )
            )
            messages.extend(historial)

        messages.append(("human", user_prompt))
        return messages
