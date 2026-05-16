# src/main.py
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

from agent.graph import CommitGraph
from agent.state import AgentState

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# ══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def build_llm():
    return ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0.2,
    )

def build_initial_state() -> AgentState:
    return {
        # ── INPUT ──────────────────────────────────────────────────────────
        "diff":            "",
        "rama":            None,
        "historial":       None,

        # ── PARSE DEL DIFF ─────────────────────────────────────────────────
        "archivos":        None,
        "estadisticas":    None,

        # ── SEMÁNTICA ──────────────────────────────────────────────────────
        "intencion":       None,
        "tipo_detectado":  None,
        "scope_detectado": None,
        "resumen":         None,

        # ── CONTEXTO RAG ───────────────────────────────────────────────────
        "contexto_repo":   None,

        # ── OUTPUT ─────────────────────────────────────────────────────────
        "message":         None,

        # ── LOOP DE MEJORA ─────────────────────────────────────────────────
        "critica":         None,
        "intentos":        0,
        "messages":        [],

        # ── CONTROL DE FLUJO ───────────────────────────────────────────────
        "error_type":    None,
        "error_node":    None,
        "error_message": None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# EJECUCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def run():
    cwd = os.getcwd()

    # 1. git add .
    subprocess.run(["git", "add", "."], cwd=cwd)

    # 2. Construir y ejecutar el grafo
    llm   = build_llm()
    graph = CommitGraph(llm).build()
    state = build_initial_state()

    resultado = graph.invoke(state)

    # 3. Manejar resultado
    error_type = resultado.get("error_type")

    if error_type == "NO_DIFF":
        print("ℹ️  No hay cambios para commitear.")
        return

    if error_type in ("API_ERROR", "GIT_ERROR"):
        print(f"❌ Error en {resultado.get('error_node')}: {resultado.get('error_message')}")
        return

    mensaje = resultado.get("message")
    if not mensaje:
        print("❌ No se pudo generar el mensaje.")
        return

    # 4. Confirmar y aplicar commit
    print(f"\n💬 {mensaje}\n")
    confirmar = input("¿Aplicar commit? (Enter=sí / n=no): ")
    if confirmar.lower() != "n":
        resultado_commit = subprocess.run(
            ["git", "commit", "-m", mensaje],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        if resultado_commit.returncode == 0:
            print("✅ Commit aplicado.")
        else:
            print(f"❌ Error al commitear: {resultado_commit.stderr}")


if __name__ == "__main__":
    run()