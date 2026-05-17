# src/agent/state.py
from typing import Optional, List, Dict, Any, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):

    # ── INPUT ─────────────────────────────────────────────────────────────────
    diff:            str
    rama:            Optional[str]
    historial:       Optional[List[str]]

    # ── PARSE DEL DIFF ────────────────────────────────────────────────────────
    archivos:        Optional[List[str]]        # ["modified: auth/models.py"]
    estadisticas:    Optional[Dict[str, int]]   # {"added": 10, "deleted": 3}

    # ── SEMÁNTICA ─────────────────────────────────────────────────────────────
    intencion:       Optional[str]
    tipo_detectado:  Optional[str]              # feat, fix, refactor, etc.
    scope_detectado: Optional[str]              # módulo afectado
    resumen:         Optional[str]              # resumen estructurado del cambio

    # ── CONTEXTO RAG ──────────────────────────────────────────────────────────
    contexto_repo:   Optional[Dict[str, Any]]  # README, convenciones, etc.

    # ── OUTPUT ────────────────────────────────────────────────────────────────
    message:         Optional[str]

    # ── LOOP DE MEJORA ────────────────────────────────────────────────────────
    critica:         Optional[str]
    intentos:        int                        # default 0

    # ── CONTROL DE FLUJO ──────────────────────────────────────────────────────
    error_node:      Optional[str]              # nodo donde ocurrió el error
    error_message:   Optional[str]              # descripción del error
    error_type:      Optional[str]              # NO_DIFF, API_ERROR, GIT_ERROR
    
    # ── MEMORIA DE MENSAJES ──────────────────────────────────────────────────────
    messages:        Annotated[List[BaseMessage], add_messages]