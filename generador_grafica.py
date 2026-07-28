import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Configuración visual académica
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12, 'font.family': 'sans-serif'})

def generar_graficas_investigacion():
    ruta_csv = "CMG_eval_binary_metrics.csv"
    
    if not os.path.exists(ruta_csv):
        print(f"Error: No se encontró el archivo {ruta_csv}")
        return

    # 1. Leer los datos
    df = pd.read_csv(ruta_csv)
    total_commits = len(df)
    
    # Nombres exactos de las columnas en tu CSV
    metricas = ['Authenticity', 'Logicality', 'Non-redundancy', 'Rationality', 'Comprehensiveness']
    nombres_espanol = ['Autenticidad', 'Lógica', 'No Redundancia', 'Racionalidad', 'Exhaustividad']
    
    for m in metricas:
        df[m] = pd.to_numeric(df[m], errors='coerce')

    # 2. Calcular individuales
    conteos_individuales = [df[m].sum() for m in metricas]
    
    # 3. Calcular el cumplimiento conjunto (filas donde TODAS las métricas son 1)
    df['Cumplimiento_Conjunto'] = df[metricas].all(axis='columns').astype(int)
    conteo_conjunto = df['Cumplimiento_Conjunto'].sum()

    # 4. Preparar datos para la gráfica
    etiquetas = nombres_espanol + ['Cumplimiento\nConjunto (Las 5)']
    valores = conteos_individuales + [conteo_conjunto]
    porcentajes = [(v / total_commits) * 100 for v in valores]

    # 5. Dibujar la gráfica
    plt.figure(figsize=(12, 7))
    
    # Damos un color diferente a la barra de "Conjunto" para resaltarla
    colores = sns.color_palette("viridis", len(metricas)) + ['#e74c3c'] 
    
    ax = sns.barplot(x=etiquetas, y=porcentajes, palette=colores)
    
    plt.title('Cumplimiento Individual vs. Conjunto de Métricas CommitSuite', fontsize=15, fontweight='bold', pad=20)
    plt.ylabel('Porcentaje de Éxito (%)', fontsize=13)
    plt.xlabel('Criterios de Evaluación', fontsize=13)
    plt.ylim(0, 100)
    
    # Añadir las etiquetas de porcentaje y conteo exacto sobre cada barra
    for i, p in enumerate(ax.patches):
        texto = f"{porcentajes[i]:.2f}%\n(n={int(valores[i])})"
        ax.annotate(texto, 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha='center', va='bottom', 
                    fontsize=11, color='black', xytext=(0, 5), 
                    textcoords='offset points')
    
    plt.tight_layout()
    nombre_salida = 'grafica_individual_vs_conjunto.png'
    plt.savefig(nombre_salida, dpi=300)
    plt.close()
    
    print(f"¡Análisis completado! Se ha generado la imagen '{nombre_salida}' con calidad de 300 DPI para tu tesis.")
    print(f"Total de commits analizados: {total_commits}")
    print(f"Commits que cumplen todo en conjunto: {int(conteo_conjunto)} ({porcentajes[-1]:.2f}%)")

if __name__ == "__main__":
    generar_graficas_investigacion()