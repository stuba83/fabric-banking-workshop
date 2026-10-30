# Módulo B2 — Entrenar y comparar con MLflow

**Notebook:** [B2_entrenamiento_mlflow.ipynb](../../notebooks/bonus_ml/B2_entrenamiento_mlflow.ipynb)  
**Dedicación orientativa:** 60–75 minutos  
**Capacidad:** funciona en Trial  
**Guía general:** [Bonus de ciencia de datos](guia.md)

## Objetivo

Entrenar varios modelos, **registrar cada intento** como una corrida de MLflow, compararlos de forma justa frente a un *baseline* y elegir con un criterio explícito. Además se prueban AutoML, el ajuste de hiperparámetros, la importancia de variables y una auditoría por grupos.

## Antes de empezar

- B1 completado: existe `<prefijo>_gold_ml_features_cuentas` con 9.000 filas.
- Parámetros: `p_lakehouse_esperado`, `p_prefijo` y `p_presupuesto_automl_s` (segundos, 30 por defecto). No escribe tablas; crea el experimento `<prefijo>_exp_actividad`.
- `import flaml` debe funcionar en tu runtime.

## Conceptos

| Concepto | Qué es |
|---|---|
| **Experimento** | Elemento del workspace que agrupa las corridas de un problema |
| **Corrida** | Un intento: parámetros, métricas y artefactos, como el modelo |
| **Autologging** | Se activa al importar `mlflow`. Con `mlflow.autolog(exclusive=False)` conviven el registro automático y el manual |
| **Baseline** | Una regla sin aprendizaje. Si un modelo no la supera con claridad, no justifica su complejidad |
| **Conjunto de prueba** | Se mide **una sola vez**, con el modelo ya elegido; elegir mirando la prueba la contamina |

## Qué hace cada sección

| Sección | Qué se hace |
|---|---|
| 1. Cargar y dividir | División por tiempo: entrenamiento (mayo y junio), validación (julio), prueba (agosto) |
| 2. Experimento y baseline | La primera corrida es la referencia |
| 3. Tres modelos | `logreg`, `rf` y `hgb`, una corrida cada uno |
| 4. Comparar | `mlflow.search_runs` y la vista de comparación del workspace |
| 5. Elegir | Entre los modelos a menos de 0,005 de AUC del mejor se elige el **más simple**; se mide en prueba y se registra |
| 6. Importancia y auditoría | Importancia por permutación; AUC por grupo de edad (`grupo_edad` **no** es variable del modelo) |
| 7. AutoML | FLAML con la misma división temporal; un solo nodo para que el modelo tenga **firma** |
| 8. Hiperparámetros | `flaml.tune` sobre la regularización `C` |
| 9. SynapseML (opcional) | LightGBM distribuido; se omite si no está disponible |

**En la interfaz.** Abre el experimento `<prefijo>_exp_actividad` en el workspace, selecciona las corridas y usa la comparación (tabla y gráficos). Fabric también ofrece **AutoML de bajo código**, que genera un notebook (ver [referencias](guia.md#referencias)); no se usa aquí.

## Resultado verificable

Los tamaños son exactos; las métricas, **aproximadas** (dependen de las versiones del runtime).

| Control | Esperado |
|---|---|
| Filas de entrenamiento, validación, prueba y por puntuar | 3.600, 1.800, 1.800 y 1.800 |
| Prevalencia (entrenamiento, validación, prueba) | ≈ 0,32, 0,35 y 0,36 |
| Corridas en el experimento | Baseline, `logreg`, `rf`, `hgb` y AutoML, **más decenas de corridas automáticas** (las pruebas internas de FLAML y del ajuste de `C`, con nombres como `keen_candle_…`). Filtra por `tags.mlflow.runName` |
| AUC de validación del baseline | ≈ 0,81 |
| AUC de validación de los tres modelos | ≈ 0,84 a 0,86 |
| AUC de prueba del modelo elegido | ≈ 0,83 a 0,85 |
| Variables más importantes | Las de actividad reciente (`tx_ventana`, `tx_mes_previo`, `tx_mes_corte`) |
| AUC por grupo de edad | Similar entre grupos (≈ 0,83 a 0,88) |

**Qué esperar de la comparación.** Los modelos quedan cerca unos de otros y solo unos puntos por encima del baseline; AutoML y el ajuste de `C` casi no cambian el resultado. Es información útil, no un fallo.

## Qué documentar en las evidencias

- La tabla de comparación de corridas (los valores que tú mediste) y el modelo elegido, con tu explicación de por qué.
- El AUC del baseline y la diferencia con el modelo elegido.
- El AUC de prueba, medido **una vez**.
- Lo que encontraste en la importancia de variables y en la auditoría por grupos, **sin atribuir causas** (los datos son sintéticos).
- Qué hizo AutoML frente a tu modelo manual y qué significa.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `expected an existing table` | Que B1 se ejecutó con `p_confirmar_reemplazo = 'SI'` |
| `No module named 'flaml'` | El runtime o el Environment; no instales con `%pip` si lo vas a programar |
| La búsqueda de corridas devuelve pocas filas | Que `mlflow.set_experiment` apunte a `<prefijo>_exp_actividad` y que las celdas anteriores corrieron |
| AutoML o `tune` tardan | Capacidad compartida; reduce `p_presupuesto_automl_s` |
| Las métricas difieren un poco de la guía | Esperado: cambian con la versión de las bibliotecas; lo importante es el orden de magnitud y la conclusión |

## Siguiente

[Módulo B3: registrar el modelo y puntuar por lotes](modulo-3-registro-puntuacion.md).
