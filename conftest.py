import sys
from pathlib import Path

# Obtiene la ruta absoluta de la carpeta 'src' y la inyecta en las rutas de Python
raiz_src = str(Path(__file__).parent / "src")
if raiz_src not in sys.path:
    sys.path.insert(0, raiz_src)
