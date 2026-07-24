import warnings

warnings.showwarning = lambda *args, **kwargs: None
warnings.filterwarnings("ignore")

import os
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"

import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("langgraph").setLevel(logging.ERROR)

import subprocess
from pathlib import Path

# ── CAMBIO: Usar ChatOllama para conexión local ──
from langchain_ollama import ChatOllama

from agent.graph import CommitGraph
from agent.state import AgentState

# ══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN CON OLLAMA
# ══════════════════════════════════════════════════════════════════════════════

def build_llm():
    return ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0.0,
        keep_alive="5m",
        num_ctx=4096    
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

    llm = build_llm()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # refuerzo justo antes del import lazy de langgraph
        graph = CommitGraph(llm).build()

        while True:
            state = build_initial_state()
            resultado = graph.invoke(state)

            error_type = resultado.get("error_type")

            if error_type == "NO_DIFF":
                print("ℹ️  El área de preparación (staging) está vacía. Ejecuta 'git add' primero para preparar tus cambios.")
                return

            if error_type in ("API_ERROR", "GIT_ERROR"):
                print(f"❌ Error en {resultado.get('error_node')}: {resultado.get('error_message')}")
                return

            mensaje = resultado.get("message")
            if not mensaje:
                print("❌ No se pudo generar el mensaje.")
                return

            print(f"\n💬 Propuesta de commit:\n\033[92m{mensaje}\033[0m\n")

            opcion = input("¿Qué deseas hacer? [a]ceptar, [r]egenerar, [c]ancelar (Enter=aceptar): ").strip().lower()

            if opcion == 'c':
                print("🚫 Operación cancelada. El staging se mantiene intacto.")
                return
            elif opcion == 'r':
                print("🔄 Regenerando mensaje...")
                continue
            else:
                resultado_commit = subprocess.run(
                    ["git", "commit", "-m", mensaje],
                    cwd=cwd,
                    capture_output=True,
                    text=True
                )
                if resultado_commit.returncode == 0:
                    print("✅ Commit aplicado exitosamente.")
                else:
                    print(f"❌ Error al commitear: {resultado_commit.stderr}")
                return

if __name__ == "__main__":
    run()