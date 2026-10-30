# %% [markdown]
# # Bonus B2 — Entrenar y comparar experimentos con MLflow
#
# **Objetivo.** Entrenar varios modelos sobre la tabla de features de B1, **registrar cada intento como una corrida de MLflow**, compararlos de forma justa y elegir uno con un criterio explícito. Además: AutoML, ajuste de hiperparámetros, importancia de variables y auditoría por grupos.
#
# **Conceptos de MLflow en Fabric**
#
# | Concepto | Qué es |
# |---|---|
# | **Experimento** | Elemento del workspace que agrupa las corridas de un mismo problema. `mlflow.set_experiment("nombre")` lo crea si no existe |
# | **Corrida** (*run*) | Un intento de entrenamiento: parámetros, métricas y artefactos, como el modelo |
# | **Autologging** | Se activa al importar `mlflow` y registra parámetros, métricas y el modelo solos. Con `exclusive=False` se conserva también lo que registras a mano |
#
# **Reglas de este notebook**
#
# - La división es **por tiempo**: se entrena con los cortes de mayo y junio, se compara en **validación** (julio) y se mide **una sola vez** en **prueba** (agosto) con el modelo elegido.
# - Todo modelo se compara contra un **baseline** sin aprendizaje: la actividad del mes actual como predictor del siguiente.
# - Los datos son sintéticos: **no interpretes las métricas como rendimiento real**. Lo que importa es el método.
#
# **Requisitos.** B1 completado. Todo funciona en Trial. Los valores son aproximados: el entrenamiento depende de la versión de las bibliotecas del runtime.

# %% parameters
p_lakehouse_esperado = ''
p_prefijo = ''
p_presupuesto_automl_s = 30

# %% embed ml_actividad.py

# %% [markdown]
# ## 1. Cargar y dividir

# %%
import notebookutils
import mlflow

lakehouse = validar_parametros_ml(
    notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, "NO", exigir_confirmacion=False,
)
nombres = nombres_ml(p_prefijo)
features = leer_tabla(spark, nombres["features"])
problemas = validar_features(features, cuentas_esperadas=1800)
if problemas:
    raise ValueError(f"{nombres['features']}: " + "; ".join(problemas))

partes = dividir_temporal(features)
entrenamiento, validacion, prueba = partes["entrenamiento"], partes["validacion"], partes["prueba"]
X_tr, y_tr = entrenamiento[list(FEATURES)], entrenamiento[ETIQUETA].astype(int)
X_va, y_va = validacion[list(FEATURES)], validacion[ETIQUETA].astype(int)
print({nombre: len(parte) for nombre, parte in partes.items()})
print("Prevalencia entrenamiento / validación / prueba:",
      round(y_tr.mean(), 3), round(y_va.mean(), 3), round(prueba[ETIQUETA].mean(), 3))

# %% [markdown]
# **Controles esperados.** 3.600 filas de entrenamiento, 1.800 de validación, 1.800 de prueba y 1.800 por puntuar. Prevalencia ≈ 0,32 / 0,35 / 0,36.

# %% [markdown]
# ## 2. Experimento y baseline
#
# `mlflow.autolog(exclusive=False)` mantiene el registro automático **y** deja que tus llamadas manuales (`log_params`, `log_metrics`) convivan con él. El baseline es la corrida de referencia: si un modelo no lo supera con claridad, no justifica su complejidad.

# %%
mlflow.autolog(exclusive=False)
mlflow.set_experiment(nombres["experimento"])

with mlflow.start_run(run_name="baseline_regla"):
    metricas_baseline = evaluar_clasificador(y_va, baseline_regla(validacion))
    mlflow.log_params({"tipo_modelo": "regla_baseline", "regla": "tx_mes_corte / 9"})
    mlflow.log_metrics({f"{k}_validacion": v for k, v in metricas_baseline.items()})
print("Baseline en validación:", {k: round(v, 3) for k, v in metricas_baseline.items() if k in ("auc", "f1")})

# %% [markdown]
# ## 3. Entrenar tres modelos
#
# Regresión logística (`logreg`), bosque aleatorio (`rf`) y *gradient boosting* (`hgb`). Cada uno es **una corrida** con sus parámetros y sus métricas de validación. Entrénalos en este orden: del más simple al más complejo.

# %%
modelos = {}
resultados = {}
for tipo in ("logreg", "rf", "hgb"):
    with mlflow.start_run(run_name=tipo) as corrida:
        modelo = crear_modelo(tipo).fit(X_tr, y_tr)
        metricas = evaluar_clasificador(y_va, modelo.predict_proba(X_va)[:, 1])
        mlflow.log_params({
            "tipo_modelo": tipo,
            "cortes_entrenamiento": ",".join(CORTES_ENTRENAMIENTO),
            "filas_entrenamiento": len(entrenamiento),
        })
        mlflow.log_metrics({f"{k}_validacion": v for k, v in metricas.items()})
        modelos[tipo] = modelo
        resultados[tipo] = {"run_id": corrida.info.run_id, **metricas}
    print(f"{tipo:7s} AUC validación = {metricas['auc']:.4f}")

# %% [markdown]
# ## 4. Comparar las corridas
#
# En el workspace abre el experimento `<prefijo>_exp_actividad` y usa la vista de comparación de corridas (tabla y gráficos). Aquí hacemos lo mismo por código con `mlflow.search_runs`.

# %%
corridas = mlflow.search_runs(experiment_names=[nombres["experimento"]])
columnas = ["tags.mlflow.runName", "metrics.auc_validacion", "metrics.average_precision_validacion", "metrics.f1_validacion"]
comparacion = (
    corridas[columnas].dropna(subset=["metrics.auc_validacion"])
    .sort_values("metrics.auc_validacion", ascending=False)
    .reset_index(drop=True)
)
display(comparacion)

# %% [markdown]
# **Qué esperar.** Los tres modelos quedan cerca (AUC ≈ 0,84–0,86 en validación) y solo unos puntos por encima del baseline (≈ 0,81). Con datos sintéticos y una señal sencilla, un modelo simple casi iguala a uno complejo. Eso es información útil: **la complejidad solo se justifica si mejora de forma medible**.

# %% [markdown]
# ## 5. Elegir con un criterio explícito
#
# Regla: entre los modelos cuyo AUC de validación está a menos de 0,005 del mejor, se elige el **más simple**. Después se mide **una sola vez** en el corte de prueba (agosto) y se registra en la misma corrida.

# %%
ORDEN_DE_SIMPLICIDAD = ("logreg", "rf", "hgb")
mejor_auc = max(r["auc"] for r in resultados.values())
elegido = next(t for t in ORDEN_DE_SIMPLICIDAD if resultados[t]["auc"] >= mejor_auc - 0.005)

metricas_prueba = evaluar_clasificador(
    prueba[ETIQUETA], modelos[elegido].predict_proba(prueba[list(FEATURES)])[:, 1]
)
with mlflow.start_run(run_id=resultados[elegido]["run_id"]):
    mlflow.log_metrics({f"{k}_prueba": v for k, v in metricas_prueba.items()})
    mlflow.set_tag("seleccionado", "si")
print(f"Modelo elegido: {elegido}")
print("Prueba (se mide una vez):", {k: round(v, 3) for k, v in metricas_prueba.items()})

# %% [markdown]
# ## 6. Importancia de variables y auditoría por grupos
#
# **Importancia por permutación.** Mide cuánto cae el AUC cuando se baraja una variable: si cae mucho, el modelo depende de ella. **Auditoría por grupos.** `grupo_edad` no es una variable del modelo, pero se usa para comprobar que el desempeño no cambia mucho entre grupos. Una diferencia grande sería una señal para investigar antes de usar el modelo, no una conclusión.

# %%
importancia = importancia_permutacion(modelos[elegido], validacion, repeticiones=5)
display(importancia.head(8))

silver = leer_silver(spark, p_prefijo)
grupos = silver["cuentas"].merge(silver["clientes"][["cliente_id", "grupo_edad"]], on="cliente_id")[[CLAVE, "grupo_edad"]]
auditado = prueba.merge(grupos, on=CLAVE, how="left")
auditoria = metricas_por_grupo(
    auditado[ETIQUETA],
    modelos[elegido].predict_proba(auditado[list(FEATURES)])[:, 1],
    auditado["grupo_edad"],
)
display(auditoria)

with mlflow.start_run(run_id=resultados[elegido]["run_id"]):
    mlflow.log_dict(
        {"importancia": importancia.to_dict("records"), "auditoria_grupo_edad": auditoria.to_dict("records")},
        "explicabilidad.json",
    )

# %% [markdown]
# **Qué esperar.** Las variables de actividad reciente (`tx_ventana`, `tx_mes_previo`, `tx_mes_corte`) dominan. El AUC por grupo de edad es similar (≈ 0,83–0,88) porque los datos sintéticos no tienen sesgos por edad; en datos reales esta tabla es donde aparecerían.

# %% [markdown]
# ## 7. AutoML con FLAML
#
# **AutoML** prueba modelos y configuraciones automáticamente dentro de un presupuesto de tiempo. En Fabric se usa la biblioteca **FLAML** (código) o la experiencia **AutoML de bajo código**, que genera un notebook (ver Referencias de la guía). Con `eval_method="holdout"` y `X_val` se respeta la **misma división por tiempo**.
#
# Dos detalles de Fabric: FLAML registra sus pruebas en MLflow solo (no repitas el registro a mano), y con `use_spark=True` el modelo se guarda **sin firma**, así que `PREDICT` (B3) no funcionaría con él. Aquí se usa un solo nodo porque los datos son pequeños.

# %%
from flaml import AutoML

automl = AutoML()
with mlflow.start_run(run_name="automl_flaml"):
    automl.fit(
        X_train=X_tr, y_train=y_tr, X_val=X_va, y_val=y_va,
        task="classification", metric="roc_auc",
        time_budget=int(p_presupuesto_automl_s), estimator_list=["lgbm", "rf"],
        eval_method="holdout", seed=42, verbose=0,
        mlflow_exp_name=nombres["experimento"],
    )
    auc_automl = evaluar_clasificador(y_va, automl.predict_proba(X_va)[:, 1])["auc"]
    mlflow.log_metric("auc_validacion", auc_automl)
print(f"AutoML eligió {automl.best_estimator}; AUC validación = {auc_automl:.4f}")
print(f"Mejor modelo manual ({elegido}): AUC validación = {resultados[elegido]['auc']:.4f}")

# %% [markdown]
# ## 8. Ajuste de hiperparámetros
#
# `flaml.tune` busca el mejor valor de un hiperparámetro dentro de un espacio y un presupuesto. Aquí se ajusta `C` (la fuerza de regularización) de la regresión logística. Verás que la mejora, si existe, es mínima: el ajuste fino rara vez compensa una señal débil o una mala variable.

# %%
from flaml import tune
from sklearn.metrics import roc_auc_score


def evaluar_c(config):
    modelo = crear_modelo("logreg")
    modelo.set_params(modelo__C=config["C"])
    modelo.fit(X_tr, y_tr)
    return {"auc_validacion": float(roc_auc_score(y_va, modelo.predict_proba(X_va)[:, 1]))}


analisis = tune.run(
    evaluar_c,
    config={"C": tune.loguniform(1e-3, 1e2)},
    metric="auc_validacion", mode="max", num_samples=12, time_budget_s=30, verbose=0,
)
print("Mejor C:", round(analisis.best_config["C"], 4),
      "| AUC validación:", round(analisis.best_trial.last_result["auc_validacion"], 4),
      "| con C por defecto:", round(resultados["logreg"]["auc"], 4))

# %% [markdown]
# ## 9. SynapseML y LightGBM (opcional)
#
# Para volúmenes que no caben en una máquina, **SynapseML** trae LightGBM distribuido sobre Spark y ya viene instalado en los runtimes PySpark de Fabric. Esta celda es opcional, no forma parte de las evidencias y se omite si la biblioteca no está disponible.

# %%
try:
    from pyspark.ml.evaluation import BinaryClassificationEvaluator
    from pyspark.ml.feature import VectorAssembler
    from synapse.ml.lightgbm import LightGBMClassifier
except ImportError as error:
    print(f"SynapseML no disponible en este entorno: {error}")
else:
    columnas_num = list(FEATURES_NUMERICAS)
    ensamblador = VectorAssembler(inputCols=columnas_num, outputCol="features")
    sp_tr = ensamblador.transform(spark.createDataFrame(entrenamiento[columnas_num + [ETIQUETA]]))
    sp_va = ensamblador.transform(spark.createDataFrame(validacion[columnas_num + [ETIQUETA]]))
    lgbm = LightGBMClassifier(objective="binary", labelCol=ETIQUETA, featuresCol="features", numIterations=100)
    evaluador = BinaryClassificationEvaluator(labelCol=ETIQUETA, metricName="areaUnderROC")
    print("LightGBM (SynapseML), AUC validación:", round(evaluador.evaluate(lgbm.fit(sp_tr).transform(sp_va)), 4))

# %% [markdown]
# ## Resumen y siguiente paso
#
# Anota en tus evidencias: el modelo elegido y por qué, el baseline, el AUC de validación y de prueba, lo que encontraste en la importancia y en la auditoría, y qué hizo AutoML frente a tu modelo manual. En **B3** registrarás el modelo, lo puntuarás por lotes y verás cómo consumirlo.
