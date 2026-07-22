import sys
import os
import pandas as pd
from tqdm import tqdm
from langchain_ollama import ChatOllama

# 1. Asegurar que Python reconozca la carpeta 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 2. Importar la clase de tu grafo
from src.agent.graph import CommitGraph 

class GeneradorMensajes:
    def __init__(self, input_csv, output_csv):
        self.input_csv = input_csv
        self.output_csv = output_csv
        
        # 3. Inicializar el motor de inferencia local y compilar el grafo
        print("Inicializando el LLM y compilando el grafo del Agente...")
        llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.0, cache=False)
        self.app = CommitGraph(llm).build()

    def generar_lote(self):
        print(f"Cargando diffs desde: {self.input_csv}")
        df = pd.read_csv(self.input_csv)
        resultados = []

        # Procesamiento secuencial con barra de progreso
        for index, row in tqdm(df.iterrows(), total=len(df), desc="Generando commits"):
            diff_actual = row['diff']
            hash_actual = row['commit_hash']
            
            # A. CONFIGURAR ESTADO INICIAL (Con las claves exactas de tu AgentState)
            estado_inicial = {
                "diff": diff_actual,
                "rama": "historico",
                "message": "",
                "intentos": 0
            }
            
            # B. INVOCAR AL AGENTE
            try:
                estado_final = self.app.invoke(estado_inicial)
                # Extraemos el texto usando la clave correcta
                mensaje_agente = estado_final.get("message", "")
            except Exception as e:
                print(f"\n  [!] Error de ejecución en el grafo para el hash {hash_actual[:7]}: {e}")
                mensaje_agente = "ERROR_DE_GENERACION"
            
            # Si el agente aborta internamente (ej. por diff muy largo) y devuelve vacío
            if not mensaje_agente:
                mensaje_agente = "ERROR_DE_GENERACION (Mensaje vacío)"
            
            # C. GUARDAR REGISTRO COMBINADO
            registro = row.to_dict()
            registro['mensaje_generado'] = mensaje_agente
            resultados.append(registro)
        
        # D. EXPORTAR AL NUEVO CSV
        df_resultados = pd.DataFrame(resultados)
        df_resultados.to_csv(self.output_csv, index=False)
        print(f"\n¡Generación completada! Archivo guardado como '{self.output_csv}'.")

if __name__ == "__main__":
    # Rutas de los archivos
    archivo_entrada = "dataset_diffs_historicos.csv"
    archivo_salida = "dataset_mensajes_generados.csv"
    
    generador = GeneradorMensajes(archivo_entrada, archivo_salida)
    generador.generar_lote()