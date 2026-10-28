# src/prompts/formatting.py
from agent.state import AgentState

class PromptFormatter:
    """
    Construye prompts dinámicos inyectando el contexto del estado.
    Separado de los templates para mantener lógica de construcción limpia.
    """

    def build_user_prompt(self, state: AgentState) -> str:
        """
        Construye el user prompt dinámico con todo el contexto disponible.
        Cada sección se agrega solo si tiene datos.
        """
        secciones = []

        # ── Contexto del repositorio ───────────────────────────────────────────
        secciones.append(self._seccion_repo(state))

        # ── Análisis semántico (Comprehension Node) ────────────────────────────
        secciones.append(self._seccion_semantica(state))

        # ── Contexto RAG si está disponible ───────────────────────────────────
        contexto_rag = self._seccion_rag(state)
        if contexto_rag:
            secciones.append(contexto_rag)

        # ── NUEVO: Checklist de Cobertura ─────────────────────────────────────
        secciones.append(self._seccion_cobertura(state))

        # ── Diff ──────────────────────────────────────────────────────────────
        secciones.append(self._seccion_diff(state))

        return "\n\n".join(filter(None, secciones))

    # ── Secciones ──────────────────────────────────────────────────────────────

    def _seccion_repo(self, state: AgentState) -> str:
        rama = state.get("rama", "unknown")
        historial = state.get("historial", [])
        archivos = state.get("archivos", [])
        stats = state.get("estadisticas", {})

        historial_str = "\n".join(historial) if historial else "sin historial"
        archivos_str = "\n".join(archivos) if archivos else "no disponible"
        stats_str = (
            f"+{stats.get('added', 0)} líneas / "
            f"-{stats.get('deleted', 0)} líneas / "
            f"{stats.get('files', 0)} archivos"
            if stats
            else "no disponible"
        )

        return f"""CONTEXTO DEL REPOSITORIO:
- Rama: {rama}
- Últimos commits:
{historial_str}
- Archivos modificados:
{archivos_str}
- Estadísticas: {stats_str}"""

    def _seccion_semantica(self, state: AgentState) -> str:
        tipo = state.get("tipo_detectado", "no detectado")
        scope = state.get("scope_detectado", "no detectado")
        intencion = state.get("intencion", "no disponible")
        resumen = state.get("resumen", "no disponible")

        return f"""ANÁLISIS SEMÁNTICO:
- Tipo detectado: {tipo}
- Scope detectado: {scope}
- Intención del cambio: {intencion}
- Resumen: {resumen}"""


    def _seccion_cobertura(self, state: AgentState) -> str:
        archivos = state.get("archivos", [])
        if not archivos:
            return ""
            
        partes = [
            'CHECKLIST DE ARCHIVOS OBLIGATORIOS (Comprehensiveness):',
            'Tu viñeta "- Qué cambia:" DEBE mencionar explícita o implícitamente la modificación de TODOS estos archivos para ser aprobada:'
        ]
        for archivo in archivos:
            partes.append(f"- {archivo}")
            
        return "\n".join(partes)

    def _seccion_rag(self, state: AgentState) -> str:
        contexto_repo = state.get("contexto_repo")
        if not contexto_repo:
            return ""

        convenciones = contexto_repo.get("convenciones", "")
        readme = contexto_repo.get("readme", "")

        partes = []
        if convenciones:
            partes.append(f"Convenciones del proyecto:\n{convenciones}")
        if readme:
            partes.append(f"README (extracto):\n{readme[:500]}")

        if not partes:
            return ""

        return "CONTEXTO DEL PROYECTO (RAG):\n" + "\n".join(partes)

    def _resumir_diff_estructural(self, diff: str) -> str:
        """Comprime diffs conservando firmas de clases/funciones y archivos."""
        import re
        lineas_importantes = []
        for linea in diff.splitlines():
            if linea.startswith('diff --git') or linea.startswith('+++') or linea.startswith('---'):
                lineas_importantes.append(linea)
            # Regex mejorada para soportar JS/TS (Angular, Deno, etc)
            elif re.match(r'^[\+\-]\s*(export\s+|async\s+|public\s+|private\s+|protected\s+|static\s+)*(class|def|function|interface|type|const|let|var)\s', linea):
                lineas_importantes.append(linea)
        
        if not lineas_importantes:
            return diff[:8000]
            
        return "\n".join(lineas_importantes)[:8000]

    def _seccion_diff(self, state: AgentState) -> str:
        diff = state.get("diff", "")
        archivos = state.get("archivos", [])
        
        # --- REGLA CI/CD RESTAURADA ---
        archivos_ci = [f for f in archivos if any(kw in f for kw in [".github/workflows", "gitlab-ci", "jenkins", "docker-compose"])]
        todo_es_ci = len(archivos_ci) > 0 and len(archivos_ci) == len(archivos)

        if todo_es_ci and len(diff) > 2000:
            return f"""DIFF (resumido por contener archivos CI/CD):
    Archivos de automatización modificados:
    {chr(10).join(archivos_ci)}

    Nota: El diff completo fue omitido por contener configuración de CI/CD.
    Usa el tipo 'ci' o 'build' para este cambio."""
        # -------------------------------

        # Umbral en 8000: con 4000 el generador veía solo ~5% de las líneas cambiadas en los commits de 4000-4500 chars
        if len(diff) > 8000:
            diff_resumido = self._resumir_diff_estructural(diff)
            return f"""DIFF (⚠️ Resumido estructuralmente por longitud):\n{diff_resumido}\n...\n[!] NOTA: El diff es masivo, se muestran solo las firmas de funciones/clases alteradas para guiarte."""
        
        return f"DIFF:\n{diff}"
