import sys
import os

# Ajuste de ruta para que encuentre 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.graph import CommitGraph

# 1. Creamos un LLM simulado falso (Mock) 
# LangGraph solo necesita inicializar la clase para mapear las rutas, no hará inferencia.
class DummyLLM:
    pass

llm_simulado = DummyLLM()

# 2. Construir y compilar el grafo con el LLM falso
agent = CommitGraph(llm_simulado)
app = agent.build()

# 3. Exportar el grafo arquitectónico a una imagen PNG
try:
    image_data = app.get_graph().draw_mermaid_png()
    with open("diagrama_arquitectura.png", "wb") as f:
        f.write(image_data)
    print("¡Grafo exportado exitosamente como diagrama_arquitectura.png!")
except Exception as e:
    print(f"Error al generar PNG: {e}")
    print("\nCódigo Mermaid nativo (por si falla la imagen):\n", app.get_graph().draw_mermaid())