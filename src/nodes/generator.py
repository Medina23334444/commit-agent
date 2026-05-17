# src/nodes/generator.py
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import AgentState
from utils.prompt_loader import load_prompt
from prompts.formatting import PromptFormatter


class GeneratorNode:
    """
    Nodo 3.3 — Prompt-Orchestrated Commit Generation Node

    Responsabilidades:
    - Construye prompt dinámico con todo el contexto disponible
    - Inyecta contexto RAG si está disponible
    - Genera mensaje semántico siguiendo Conventional Commits
    - Incluye historial de intentos fallidos para mejorar convergencia
    """

    def __init__(self, llm):
        self.llm = llm
        self.formatter = PromptFormatter()

    def run(self, state: AgentState) -> AgentState:
        # ── 1. Construir user prompt dinámico ─────────────────────────────────
        user_prompt = self.formatter.build_user_prompt(state)

        # ── 2. Construir mensajes con historial de intentos ────────────────────
        messages = self._build_messages(state, user_prompt)

        # ── 3. Invocar LLM ────────────────────────────────────────────────────
        try:
            response = self.llm.invoke(messages)
            print(f"DEBUG raw: {repr(response.content[:200])}")  # ← agrega esto
            mensaje = response.content.strip()
            mensaje = self._limpiar_mensaje(mensaje)  # ← truncado
            print(f"DEBUG limpio: {repr(mensaje)}")  # ← agrega esto
            # Agrega al historial de mensajes
            nuevos_messages = [
                HumanMessage(content=user_prompt),
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
                "error_node": "generator",
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

    def _build_messages(self, state: AgentState, user_prompt: str) -> list:
        """
        Construye la lista de mensajes para el LLM.
        Incluye historial de intentos fallidos si existen.
        """
        system_prompt = load_prompt("generator_system.md")

        messages = [SystemMessage(content=system_prompt)]

        # Inyecta historial de intentos fallidos
        historial_intentos = state.get("messages", [])
        if historial_intentos:
            messages.append(
                SystemMessage(
                    content="Historial de intentos anteriores (aprende de estos errores):"
                )
            )
            messages.extend(historial_intentos)

        # Agrega crítica si existe
        critica = state.get("critica")
        if critica:
            messages.append(
                HumanMessage(
                    content=f"Crítica del intento anterior que DEBES corregir:\n{critica}"
                )
            )

        messages.append(HumanMessage(content=user_prompt))
        return messages
