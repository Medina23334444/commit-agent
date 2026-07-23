# src/utils/prompt_loader.py (o dentro de tu nodo)
from pathlib import Path

def load_prompt(filename: str, **kwargs) -> str:
    """
    Carga un archivo de prompt desde la carpeta src/prompts y formatea las variables.
    """
    # Localiza la carpeta de prompts relativa a este archivo
    base_path = Path(__file__).parent.parent / "prompts"
    file_path = base_path / filename

    if not file_path.exists():
        raise FileNotFoundError(f"No se encontró el prompt en: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Inyecta las variables (tipo_detectado, resumen, etc.)
    return content.format(**kwargs)