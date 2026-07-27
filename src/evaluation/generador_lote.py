import sys
import os
import pandas as pd
from tqdm import tqdm

# 1. Importar el cliente de Ollama local
from langchain_ollama import ChatOllama

# 2. Asegurar que Python reconozca la carpeta 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 3. Importar la clase de tu grafo
from src.agent.graph import CommitGraph 

class GeneradorMensajes:
    def __init__(self, input_csv, output_csv):
        self.input_csv = input_csv
        self.output_csv = output_csv

        print("Inicializando el LLM (Ollama Local) y compilando el grafo del Agente...")
        
        # 4. Configurar Ollama apuntando a tu modelo local con los parámetros optimizados
        llm = ChatOllama(
            model="qwen2.5-coder:7b",
            temperature=0.0,
             keep_alive="5m",
            num_ctx=4096    
        )
        
        self.app = CommitGraph(llm).build()

    def generar_lote(self):
        print(f"Cargando diffs desde: {self.input_csv}")
        df = pd.read_csv(self.input_csv)
        resultados = []

        # Procesamiento secuencial con barra de progreso
        for index, row in tqdm(df.iterrows(), total=len(df), desc="Generando commits"):
            # Límite de seguridad: Truncar diffs masivos para evitar desbordar num_ctx
            MAX_DIFF_LENGTH = 12000
            diff_actual = str(row['diff'])
            if len(diff_actual) > MAX_DIFF_LENGTH:
                diff_actual = diff_actual[:MAX_DIFF_LENGTH] + "\n\n... [DIFF TRUNCADO POR LONGITUD]"
            
            hash_actual = row['commit_hash']
            
            # A. CONFIGURAR ESTADO INICIAL
            estado_inicial = {
                "diff": diff_actual,
                "rama": "historico",
                "message": "",
                "intentos": 0
            }
            
            # B. INVOCAR AL AGENTE
            try:
                estado_final = self.app.invoke(estado_inicial)
                mensaje_agente = estado_final.get("message", "")
            except Exception as e:
                print(f"\n  [!] Error de ejecución en el grafo para el hash {hash_actual[:7]}: {e}")
                mensaje_agente = f"ERROR_DE_GENERACION: {str(e)}"
            
            if not mensaje_agente:
                mensaje_agente = "ERROR_DE_GENERACION (Mensaje vacío)"
            
            # C. GUARDAR REGISTRO COMBINADO
            registro = row.to_dict()
            registro['mensaje_generado'] = mensaje_agente
            resultados.append(registro)
            
            # Guardado parcial opcional cada 50 iteraciones para no perder datos si hay un crash
            if (index + 1) % 50 == 0:
                pd.DataFrame(resultados).to_csv(self.output_csv, index=False)
        
        # D. EXPORTAR AL NUEVO CSV
        df_resultados = pd.DataFrame(resultados)
        df_resultados.to_csv(self.output_csv, index=False)
        print(f"\n¡Generación completada! Archivo guardado como '{self.output_csv}'.")

if __name__ == "__main__":
    # Rutas de los archivos
    archivo_entrada = "dataset_diffs_limpios.csv"
    archivo_salida = "dataset_mensajes_generados.csv"
    
    generador = GeneradorMensajes(archivo_entrada, archivo_salida)
    generador.generar_lote()