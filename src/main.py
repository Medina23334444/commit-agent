# src/main.py
import os
import subprocess
import logging
import warnings
from pathlib import Path

warnings.filterwarnings("ignore") 
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"   
os.environ["TRANSFORMERS_VERBOSITY"] = "error"      
os.environ["TOKENIZERS_PARALLELISM"] = "false"     

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

from agent.graph import CommitGraph
from agent.state import AgentState

env_path = Path(__file__).parent.parent / ".env"

if not env_path.exists():
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Configuración del Agente de Commits\n")
        f.write("OLLAMA_HOST=http://localhost:11434\n")
    print("⚙️ Archivo .env generado automáticamente con la configuración por defecto.")

load_dotenv(dotenv_path=env_path)


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

    # 1. ELIMINADO EL 'git add .' AUTOMÁTICO (Cumple RF03)
    # El usuario debe usar git add manualmente antes de llamar a commit-agent.

    llm   = build_llm()
    graph = CommitGraph(llm).build()

    # Bucle infinito para permitir la opción de "Regenerar" (Cumple RF08)
    while True:
        state = build_initial_state()
        resultado = graph.invoke(state)

        # 3. Manejar resultado
        error_type = resultado.get("error_type")

        # Mensaje claro si el staging está vacío (Cumple RF03)
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

        # 4. Confirmar y aplicar commit con 3 opciones (Cumple RF08)
        print(f"\n💬 Propuesta de commit:\n\033[92m{mensaje}\033[0m\n")
        
        opcion = input("¿Qué deseas hacer? [a]ceptar, [r]egenerar, [c]ancelar (Enter=aceptar): ").strip().lower()
        
        if opcion == 'c':
            print("🚫 Operación cancelada. El staging se mantiene intacto.")
            return
        elif opcion == 'r':
            print("🔄 Regenerando mensaje...")
            continue # Vuelve al inicio del bucle while y genera un mensaje nuevo
        else:
            # Opción por defecto o si elige 'a'
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