import warnings
import os
import subprocess

warnings.showwarning = lambda *args, **kwargs: None
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv()

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

from langchain_openai import ChatOpenAI
from agent.graph import CommitGraph
from agent.state import AgentState


# ══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN DEL LLM (CONFIGURACIÓN OFICIAL KIMI K2.6)
# ══════════════════════════════════════════════════════════════════════════════

def build_llm():
    api_key = os.getenv("MOONSHOT_API_KEY")

    if not api_key:
        raise RuntimeError("Falta MOONSHOT_API_KEY en el entorno o archivo .env")

    base_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
    model = os.getenv("MOONSHOT_MODEL", "kimi-k2.6")

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        # Parámetros estrictos exigidos por K2.6 según su documentación oficial:
        temperature=1.0,          # Requerido por K2.6 (1.0 para thinking, o 0.6 si se desactiva)
        model_kwargs={
            "top_p": 0.95,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            # Si deseas desactivar el modo de pensamiento (thinking) puedes descomentar la siguiente línea:
            # "thinking": {"type": "disabled"}
        }
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

    try:
        llm = build_llm()
    except Exception as exc:
        print(f"❌ Error de configuración de API: {exc}")
        return

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