from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage

# Imports de tu aplicación (Pytest los buscará dentro de /src gracias a tu configuración)
from agent.router import Router
from nodes.generator import GeneratorNode
from nodes.validator import ValidatorNode
from tools.validation_tools import validate_format


# ==============================================================================
# 1. PRUEBAS DEL ENRUTADOR (ROUTER)
# ==============================================================================
def test_router_after_analyzer_no_diff():
    """Verifica que el router aborte si no se detectan cambios en staging."""
    state = {"error_type": "NO_DIFF", "error_message": "No hay cambios"}
    assert Router.after_analyzer(state) == "abort"


def test_router_after_analyzer_continue():
    """Verifica que el flujo continúe si el análisis del diff fue exitoso."""
    state = {"error_type": None, "error_message": None}
    assert Router.after_analyzer(state) == "continue"


def test_router_after_validator_approved():
    """Verifica que apruebe el mensaje si está validado correctamente."""
    state = {"error_type": "VALID", "intentos": 1}
    assert Router.after_validator(state) == "approved"


def test_router_after_validator_max_retries():
    """Verifica que aborte si se alcanza el límite máximo de 3 intentos."""
    state = {"error_type": "INVALID", "intentos": 3}
    assert Router.after_validator(state) == "abort"


# ==============================================================================
# 2. PRUEBAS DE VALIDACIÓN DE FORMATO (CONVENTIONAL COMMITS)
# ==============================================================================
def test_validate_format_success():
    """Verifica un mensaje con formato correcto y longitud válida."""
    message = "feat(auth): añadir validación de tokens jwt"
    assert validate_format.invoke({"message": message}) == "VALID"


def test_validate_format_too_long():
    """Verifica que rechace headers que superen el límite estricto de 72 caracteres."""
    long_message = "fix(api): " + "x" * 70  # Supera los 72 caracteres permitidos
    resultado = validate_format.invoke({"message": long_message})
    assert "INVALID: primera línea demasiado larga" in resultado


def test_validate_format_missing_separator():
    """Verifica que detecte la falta del separador ':' obligatorio."""
    bad_message = "chore(config) actualizar dependencias de desarrollo"
    resultado = validate_format.invoke({"message": bad_message})
    assert "INVALID: falta el separador ':'" in resultado


# ==============================================================================
# 3. PRUEBAS AVANZADAS CON MOCKS (SIMULACIÓN DE LLM)
# ==============================================================================
def test_generator_node_truncates_long_messages():
    """Simula al LLM respondiendo un mensaje gigante para verificar que el nodo lo trunque."""
    # Creamos un mock del LLM para evitar peticiones reales a Ollama en los tests
    mock_llm = MagicMock()
    mensaje_gigante = "feat(auth): " + "x" * 80
    mock_llm.invoke.return_value = AIMessage(content=mensaje_gigante)

    node = GeneratorNode(mock_llm)

    # Estado simulado con la estructura de tu AgentState
    state = {
        "diff": "some git diff data",
        "rama": "develop",
        "historial": [],
        "archivos": ["src/main.py"],
        "estadisticas": {"added": 1, "deleted": 0, "files": 1},
        "tipo_detectado": "feat",
        "scope_detectado": "auth",
        "intencion": "add verification",
        "resumen": "summary",
        "messages": [],
    }

    resultado = node.run(state)

    # El limpiador interno del nodo debe obligar a que la primera línea mida <= 72 caracteres
    primera_linea = resultado["message"].splitlines()[0]
    assert len(primera_linea) <= 72


def test_validator_node_captures_llm_critique():
    """Verifica que el nodo validador procese y guarde la crítica si el LLM rechaza el formato."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="MEJORAR: la descripción usa verbos en pasado en lugar de infinitivo."
    )

    node = ValidatorNode(mock_llm)
    state = {
        "message": "fix(api): corregido error en llamadas asíncronas",
        "diff": "some diff",
        "intencion": "corregir bug",
        "intentos": 0,
    }

    resultado = node.run(state)

    # El componente debe marcar el estado como INVALID e incrementar el contador de bucle
    assert resultado["error_type"] == "INVALID"
    assert resultado["intentos"] == 1
    assert "verbos en pasado" in resultado["critica"]
