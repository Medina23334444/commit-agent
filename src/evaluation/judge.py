import pandas as pd
import json
import time
from tqdm import tqdm
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Configuración del modelo local
# Temperatura 0 para que el juez sea lo más determinista y objetivo posible
llm_juez = ChatOllama(model="qwen2.5-coder:7b", temperature=0.0)

# 2. El Prompt Oficial de CommitSuite adaptado a LangChain
plantilla_prompt = """You are a code reviewer evaluating the quality of an AI-generated commit message.
You are given the following information:
- Modified files (with diffs)
- The generated commit message (CMG_result)

You should assess the generated commit message from five perspectives:
  1. Rationality: Whether it contains "why" information (describe the reasons for the changes).
  2. Comprehensiveness: Whether it contains "what" information (summarize the changes in this commit) and covers all affected files.
  3. Non-redundancy: Whether there is no semantic repetition, mergable details, meaningless content (unrelated to "what" and "why"), or content of little use.
  4. Authenticity: Whether it does not include modifications absent in the actual code changes.
  5. Logicality: Whether the content in it is reasonable and logical.

Please answer using the following JSON format (Use 1 for "yes", 0 for "no"; Don't miss any fields):
{{
  "Rationality": 0,
  "Comprehensiveness": 0,
  "Non-redundancy": 0,
  "Authenticity": 0,
  "Logicality": 0
}}

Here is the information:

Modified Files:
Diff:
{diff}

Generated Commit Message:
{mensaje_generado}

Now, answer the 5 questions in JSON format (please be as strict as possible and don't make any explanations):"""

prompt_juez = ChatPromptTemplate.from_template(plantilla_prompt)
cadena_evaluacion = prompt_juez | llm_juez | StrOutputParser()

def llamar_juez_local(diff, mensaje_generado, max_intentos=3):
    for intento in range(max_intentos):
        try:
            # Ejecutar inferencia local
            respuesta_cruda = cadena_evaluacion.invoke({
                "diff": diff, 
                "mensaje_generado": mensaje_generado
            })
            
            # Limpieza del formato Markdown que suelen devolver los LLMs locales
            contenido = respuesta_cruda.strip().replace('```json', '').replace('```', '').strip()
            
            # Parsear el JSON
            parsed = json.loads(contenido)
            return {
                "Rationality": int(parsed.get("Rationality", 0)),
                "Comprehensiveness": int(parsed.get("Comprehensiveness", 0)),
                "Non-redundancy": int(parsed.get("Non-redundancy", 0)),
                "Authenticity": int(parsed.get("Authenticity", 0)),
                "Logicality": int(parsed.get("Logicality", 0)),
            }
        except Exception:
            print(f"\n  [!] Error de formato del juez (intento {intento + 1}/{max_intentos}). Reintentando...")
            time.sleep(1)
            
    # Degradación segura si falla después de 3 intentos
    return {key: 0 for key in ["Rationality", "Comprehensiveness", "Non-redundancy", "Authenticity", "Logicality"]}

def ejecutar_evaluacion():
    print("Cargando dataset con mensajes generados...")
    # Leer el archivo que acabas de generar
    df = pd.read_csv("dataset_mensajes_generados.csv")
    
    # Filtramos los fallidos o vacíos para evaluar únicamente los 209 éxitos
    df_exitosos = df[~df['mensaje_generado'].str.contains("ERROR_DE_GENERACION|❌", na=False, case=False)]
    df_exitosos = df_exitosos.dropna(subset=['mensaje_generado'])
    df_exitosos = df_exitosos[df_exitosos['mensaje_generado'].str.strip() != ""]

    print(f"Total de commits válidos a evaluar: {len(df_exitosos)}")
    
    resultados = []
    
    # Procesamiento secuencial con barra de progreso
    for index, row in tqdm(df_exitosos.iterrows(), total=len(df_exitosos), desc="Evaluando commits"):
        diff_actual = row['diff']
        hash_actual = row['commit_hash']
        mensaje_agente = row['mensaje_generado']
        
        # El LLM Juez califica el mensaje
        veredictos = llamar_juez_local(diff_actual, mensaje_agente)
        
        # Guardar el registro
        registro = {
            "repositorio": row['repositorio'],
            "commit_hash": hash_actual,
            "mensaje_original": row['mensaje_original'],
            "mensaje_generado": mensaje_agente
        }
        registro.update(veredictos)
        resultados.append(registro)
        
    # Exportar resultados
    df_resultados = pd.DataFrame(resultados)
    df_resultados.to_csv("CMG_eval_binary_metrics.csv", index=False)
    print("\n¡Evaluación completada! Resultados guardados en 'CMG_eval_binary_metrics.csv'.")

if __name__ == "__main__":
    ejecutar_evaluacion()