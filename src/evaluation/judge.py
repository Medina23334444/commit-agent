"""
judge_original_full.py
Replica exacta de la metodología original de CommitSuite para TODO el dataset.
Prompt original, salida en JSON puro sin razonamiento (Chain-of-Thought).
"""
import os
import json
import pandas as pd
from tqdm import tqdm
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


ARCHIVO_ENTRADA = "dataset_mensajes_generados.csv"
ARCHIVO_SALIDA_CSV = "CMG_eval_original_n250.csv"
JUEZ_MODELO = "llama3.1:8b"
MAX_DIFF_CHARS = 14000

llm_juez = ChatOllama(model=JUEZ_MODELO, temperature=0.0)

# ============================================================
# PROMPT ORIGINAL EXACTO DEL PAPER
# ============================================================
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

def preparar_diff(diff):
    diff = "" if pd.isna(diff) else str(diff)
    if len(diff) <= MAX_DIFF_CHARS:
        return diff
    mitad = MAX_DIFF_CHARS // 2
    return diff[:mitad] + "\n\n[... middle of diff truncated for length ...]\n\n" + diff[-mitad:]

def limpiar_json(texto):
    texto = texto.replace('```json', '').replace('```', '').strip()
    try:
        # Buscar el primer '{' y el último '}' por si el modelo añadió texto extra
        inicio = texto.find('{')
        fin = texto.rfind('}')
        if inicio != -1 and fin != -1:
            texto = texto[inicio:fin+1]
        return json.loads(texto)
    except:
        return None

def ejecutar_evaluacion():
    print("=" * 60)
    print("CORRIENDO METODOLOGÍA ORIGINAL COMMITSUITE (DATASET COMPLETO)")
    print("=" * 60)
    
    df = pd.read_csv(ARCHIVO_ENTRADA)
    df = df[~df["mensaje_generado"].astype(str).str.contains("ERROR_DE_GENERACION|❌", na=False, case=False)]
    df = df.dropna(subset=["mensaje_generado"]).reset_index(drop=True)
    
    print(f"Evaluando total de {len(df)} commits...")

    resultados = {
        "Rationality": 0, "Comprehensiveness": 0, 
        "Non-redundancy": 0, "Authenticity": 0, "Logicality": 0
    }
    
    fallos = 0
    registros_csv = []
    
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Evaluando"):
        diff_str = preparar_diff(row["diff"])
        
        try:
            respuesta_cruda = cadena_evaluacion.invoke({
                "diff": diff_str,
                "mensaje_generado": row["mensaje_generado"]
            })
            
            parsed = limpiar_json(respuesta_cruda)
            
            registro = {
                "commit_hash": row["commit_hash"],
                "mensaje_generado": row["mensaje_generado"],
                "respuesta_cruda": respuesta_cruda,
                "json_valido": parsed is not None
            }
            
            if parsed:
                for key in resultados.keys():
                    val = int(parsed.get(key, 0))
                    resultados[key] += val
                    registro[key] = val
            else:
                fallos += 1
                for key in resultados.keys():
                    registro[key] = None
                    
            registros_csv.append(registro)
            
        except Exception as e:
            fallos += 1

    # Guardar los resultados fila por fila
    pd.DataFrame(registros_csv).to_csv(ARCHIVO_SALIDA_CSV, index=False)

    exitos = len(df) - fallos
    print("\n" + "=" * 60)
    print("RESUMEN ORIGINAL")
    print("=" * 60)
    print(f"Filas intentadas: {len(df)}")
    print(f"Fallos de formato JSON: {fallos}")
    print(f"Evaluados exitosamente: {exitos}")
    print("--- Aciertos (%) ---")
    
    if exitos > 0:
        for key in resultados:
            porcentaje = (resultados[key] / exitos) * 100
            print(f"  {key}: {porcentaje:.1f}%")
            
    print(f"\nResultados guardados en '{ARCHIVO_SALIDA_CSV}'.")

if __name__ == "__main__":
    ejecutar_evaluacion()