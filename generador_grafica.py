import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Configuración visual para publicaciones académicas
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.edgecolor': '#cccccc',
    'axes.linewidth': 0.8
})

def generar_graficas_investigacion():
    ruta_csv = "CMG_eval_original_n250.csv"
    
    if not os.path.exists(ruta_csv):
        print(f"Error: No se encontró el archivo {ruta_csv}")
        return

    # 1. Leer los datos
    df = pd.read_csv(ruta_csv)
    
    # Nombres exactos de las columnas
    metricas = ['Authenticity', 'Logicality', 'Non-redundancy', 'Rationality', 'Comprehensiveness']
    nombres_espanol = ['Autenticidad', 'Lógica', 'No Redundancia', 'Racionalidad', 'Exhaustividad']
    
    for m in metricas:
        df[m] = pd.to_numeric(df[m], errors='coerce').fillna(0).astype(int)

    total_commits = len(df)
    if total_commits == 0:
        print("Error: El DataFrame no contiene registros.")
        return

    # 2. Métricas individuales
    conteos_individuales = [df[m].sum() for m in metricas]
    
    # 3. Cumplimiento conjunto (todas las métricas en 1)
    df['Cumplimiento_Conjunto'] = (df[metricas].sum(axis=1) == len(metricas)).astype(int)
    conteo_conjunto = df['Cumplimiento_Conjunto'].sum()

    # 4. Estructurar datos
    etiquetas = nombres_espanol + ['Cumplimiento\nConjunto (Las 5)']
    valores = conteos_individuales + [conteo_conjunto]
    porcentajes = [(v / total_commits) * 100 for v in valores]

    df_plot = pd.DataFrame({
        'Criterio': etiquetas,
        'Porcentaje': porcentajes,
        'Conteo': valores
    })

    # 5. Generar gráfica
    fig, ax = plt.subplots(figsize=(11, 6.5))
    
    # Paleta con énfasis diferenciado para la barra final
    colores = sns.color_palette("mako", len(metricas)) + ['#d9534f']
    
    sns.barplot(
        data=df_plot,
        x='Criterio',
        y='Porcentaje',
        hue='Criterio',
        palette=colores,
        legend=False,
        edgecolor='black',
        linewidth=0.6,
        ax=ax
    )
    
    # Línea de referencia al 100%
    ax.axhline(100, color='#888888', linestyle='--', linewidth=1, alpha=0.7)
    
    ax.set_title('Cumplimiento Individual vs. Conjunto de Métricas CommitSuite', fontsize=14, fontweight='bold', pad=15)
    ax.set_ylabel('Tasa de Éxito (%)', fontsize=12, labelpad=10)
    ax.set_xlabel('Criterio de Evaluación', fontsize=12, labelpad=10)
    ax.set_ylim(0, 115)  # Espacio superior para etiquetas
    
    # Etiquetas de datos sobre cada barra
    for p, valor, pct in zip(ax.patches, valores, porcentajes):
        altura = p.get_height()
        texto = f"{pct:.1f}%\n(n={int(valor)})"
        ax.annotate(
            texto,
            (p.get_x() + p.get_width() / 2., altura),
            ha='center',
            va='bottom',
            fontsize=10.5,
            fontweight='semibold',
            color='#222222',
            xytext=(0, 4),
            textcoords='offset points'
        )

    sns.despine(top=True, right=True)
    plt.tight_layout()
    
    nombre_salida = 'grafica_individual_vs_conjunto.png'
    plt.savefig(nombre_salida, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Gráfica generada exitosamente: '{nombre_salida}' (300 DPI).")
    print(f"Total analizado: {total_commits} commits.")
    print(f"Cumplimiento total simultáneo: {int(conteo_conjunto)} ({porcentajes[-1]:.2f}%)")

if __name__ == "__main__":
    generar_graficas_investigacion()