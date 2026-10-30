# %% [markdown]
# # Bonus B3 — Registrar el modelo y puntuar por lotes
#
# **Objetivo.** Pasar de «un modelo entrenado en un notebook» a «una **versión registrada** del modelo que cualquiera puede cargar y usar»: registrarla con su firma y sus etiquetas, puntuar las cuentas del último corte, comprobar que el resultado es el mismo por dos caminos y dejar la tabla lista para Power BI.
#
# **Conceptos**
#
# | Concepto | Qué es |
# |---|---|
# | **Modelo de ML** (elemento) | Agrupa las **versiones** de un modelo. Cada versión guarda su firma, etiquetas y la corrida que la creó |
# | **Firma** (*signature*) | Columnas y tipos de entrada y salida. **`PREDICT` la exige** |
# | **Etiquetas** | Pares clave-valor que se fijan **al registrar** la versión (por ejemplo, tipo de modelo y métrica) |
# | **PREDICT** | Puntuación por lotes en cualquier motor (Spark, SQL, UDF) a partir de un modelo registrado |
#
# **Importante.** Fabric no documenta *etapas* ni *alias* de modelo (por ejemplo, «producción»). Por eso en B4 el modelo vigente (el «campeón») se decide con una **tabla de control** y las versiones se identifican por su número.
#
# **Requisitos.** B1 completado. Funciona en Trial. `p_confirmar_reemplazo = 'SI'` se necesita para registrar la versión y escribir la tabla de puntuación. Cada ejecución registra **una versión nueva** del modelo.

# %% parameters
p_lakehouse_esperado = ''
p_prefijo = ''
p_confirmar_reemplazo = 'NO'
p_tipo_modelo = 'logreg'

# %% embed ml_actividad.py

# %% [markdown]
# ## 1. Preparar

# %%
import notebookutils
import mlflow
from mlflow.models import infer_signature

lakehouse = validar_parametros_ml(
    notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo,
    exigir_confirmacion=False,
)
nombres = nombres_ml(p_prefijo)
features = leer_tabla(spark, nombres["features"])
problemas = validar_features(features, cuentas_esperadas=1800)
if problemas:
    raise ValueError(f"{nombres['features']}: " + "; ".join(problemas))

partes = dividir_temporal(features)
entrenamiento, validacion, prueba = partes["entrenamiento"], partes["validacion"], partes["prueba"]
X_tr, y_tr = entrenamiento[list(FEATURES)], entrenamiento[ETIQUETA].astype(int)
print({nombre: len(parte) for nombre, parte in partes.items()})

# %% [markdown]
# ## 2. Entrenar y guardar el modelo con su firma
#
# La **firma** se infiere de un ejemplo de entrada y de la salida del modelo. Se guarda junto con el modelo: es lo que permite que otro motor (Spark, SQL) sepa qué columnas esperar. El formato de serialización se fija explícitamente para que el resultado sea idéntico en cualquier versión de MLflow.

# %%
mlflow.set_experiment(nombres["experimento"])
with mlflow.start_run(run_name=f"candidato_{p_tipo_modelo}") as corrida:
    modelo = crear_modelo(p_tipo_modelo).fit(X_tr, y_tr)
    metricas_val = evaluar_clasificador(validacion[ETIQUETA], modelo.predict_proba(validacion[list(FEATURES)])[:, 1])
    metricas_prueba = evaluar_clasificador(prueba[ETIQUETA], modelo.predict_proba(prueba[list(FEATURES)])[:, 1])
    firma = infer_signature(X_tr, modelo.predict(X_tr))
    mlflow.sklearn.log_model(modelo, "model", signature=firma, serialization_format="cloudpickle")
    mlflow.log_params({"tipo_modelo": p_tipo_modelo, "cortes_entrenamiento": ",".join(CORTES_ENTRENAMIENTO)})
    mlflow.log_metrics({
        **{f"{k}_validacion": v for k, v in metricas_val.items()},
        **{f"{k}_prueba": v for k, v in metricas_prueba.items()},
    })
    run_id = corrida.info.run_id
print("AUC validación / prueba:", round(metricas_val["auc"], 4), "/", round(metricas_prueba["auc"], 4))
print("Columnas de entrada en la firma:", len(firma.inputs.input_names()), "→", firma.inputs.input_names()[:3], "...")

# %% [markdown]
# ## 3. Registrar una versión
#
# `register_model` crea (o actualiza) el **elemento de modelo** `<prefijo>_modelo_actividad` y le agrega una versión nueva. Las **etiquetas** se fijan en este momento y quedan visibles en la página de la versión: úsalas para que cualquiera entienda de dónde viene y cómo se evaluó.

# %%
validar_parametros_ml(notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo)
registrada = mlflow.register_model(
    f"runs:/{run_id}/model",
    nombres["modelo"],
    tags={
        "tipo_modelo": p_tipo_modelo,
        "corte_prueba": CORTE_PRUEBA,
        "auc_prueba": f"{metricas_prueba['auc']:.4f}",
        "umbral_alta_actividad": str(UMBRAL_ALTA_ACTIVIDAD),
    },
)
version = int(registrada.version)
print(f"Modelo {nombres['modelo']}, versión {version}")

# %% [markdown]
# **Qué mirar en el workspace.** Abre el elemento del modelo y entra a la versión: verás la corrida de origen, las etiquetas y la firma. Desde la misma página puedes copiar código de `PREDICT` o abrir el asistente (sección 6).

# %% [markdown]
# ## 4. Cargar la versión registrada y comprobar que es la misma
#
# Cargar `models:/<nombre>/<versión>` es lo que hará cualquier otro notebook o pipeline. Comprueba que produce **exactamente** las mismas probabilidades que el modelo en memoria.

# %%
modelo_registrado = mlflow.sklearn.load_model(f"models:/{nombres['modelo']}/{version}")
local = modelo.predict_proba(prueba[list(FEATURES)])[:, 1]
cargado = modelo_registrado.predict_proba(prueba[list(FEATURES)])[:, 1]
if not np.allclose(local, cargado):
    raise ValueError("registry roundtrip: expected identical probabilities; observed differences")
print("La versión registrada reproduce las probabilidades del modelo original.")

# %% [markdown]
# ## 5. El umbral es una decisión de negocio
#
# El modelo da una **probabilidad**; el umbral que la convierte en «alta actividad» depende de qué cuesta equivocarse. Un umbral bajo marca a más cuentas (más *recall*, menos *precision*); uno alto marca a menos (al revés). Esta tabla se calcula con el corte de **prueba** (agosto), que ya tiene etiqueta.

# %%
probabilidad = modelo_registrado.predict_proba(prueba[list(FEATURES)])[:, 1]
tabla_umbrales = pd.DataFrame([
    {
        "umbral": umbral,
        "marcadas": float((probabilidad >= umbral).mean()),
        **{k: evaluar_clasificador(prueba[ETIQUETA], probabilidad, umbral)[k] for k in ("precision", "recall", "f1")},
    }
    for umbral in (0.3, 0.4, 0.5, 0.6, 0.7)
])
display(tabla_umbrales.round(3))

# %% [markdown]
# ## 6. Puntuar por lotes
#
# Se puntúa el corte de **septiembre**, que no tiene etiqueta: es la predicción para octubre. El resultado se guarda en `<prefijo>_gold_ml_puntuacion_actividad` junto con la **versión del modelo** y la fecha, para poder auditar qué modelo produjo cada predicción. La escritura reemplaza solo las filas de este corte, así que se puede repetir sin duplicar.

# %%
puntuacion = puntuar(modelo_registrado, partes["puntuacion"])
puntuacion["version_modelo"] = version
puntuacion["fecha_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
filas = reemplazar_corte(spark, nombres["puntuacion"], puntuacion, COLUMNAS_PUNTUACION, CORTE, CORTE_PUNTUACION)
print(json.dumps({"status": "success", "tabla": nombres["puntuacion"], "filas": filas, "version": version}))
display(puntuacion.sort_values("probabilidad_alta_actividad", ascending=False).head(10))

# %% [markdown]
# ### PREDICT: el mismo resultado con Spark
#
# `PREDICT` aplica un modelo registrado a un DataFrame de Spark (también existen la forma SQL y la de UDF). Debe dar **la misma clase** que la puntuación con pandas. Requiere un modelo con **firma** y de un sabor soportado (`sklearn` lo es). `PREDICT` devuelve la **clase** (0 o 1); para la **probabilidad** se usa el modelo cargado, como arriba.

# %%
try:
    from synapse.ml.predict import MLFlowTransformer
except ImportError as error:
    print(f"MLFlowTransformer no disponible en este entorno: {error}")
else:
    entrada = (
        spark.table(nombres["features"]).filter(f"{CORTE} = '{CORTE_PUNTUACION}'").select(CLAVE, *FEATURES)
    )
    transformador = MLFlowTransformer(
        inputCols=list(FEATURES), outputCol="prediccion_predict",
        modelName=nombres["modelo"], modelVersion=version,
    )
    predict = transformador.transform(entrada).select(CLAVE, "prediccion_predict").toPandas()
    union = puntuacion.merge(predict, on=CLAVE)
    acuerdo = float((union["prediccion"] == union["prediccion_predict"].astype(int)).mean())
    print(f"Acuerdo entre pandas y PREDICT: {acuerdo:.4f} ({len(union)} cuentas)")
    if acuerdo < 1.0:
        raise ValueError(f"PREDICT: expected agreement 1.0; observed {acuerdo}")

# %% [markdown]
# ## 7. Otras formas de aplicar el modelo
#
# **Asistente de la versión (sin código).** En la página de la versión, abre **Apply this version** → **Apply this model in wizard**: eliges la tabla de entrada de tu Lakehouse, mapeas las columnas a las entradas del modelo, indicas el destino y se **genera un notebook** con `PREDICT`.
#
# **Punto de conexión en tiempo real (vista previa).** Una versión puede exponerse como un *endpoint* que responde solicitudes una a una (`.../versions/<n>/score`). Detalles documentados: se aplica a sabores como scikit-learn, LightGBM, XGBoost y Keras, exige un modelo con esquema, se **duerme solo tras 5 minutos sin uso** y mientras está activo **consume capacidad** (5 CU-segundos por nodo y por segundo). Comprueba en tu tenant si está disponible en Trial y en tu región. No es necesario para esta práctica.
#
# **Cuándo usar cada uno.** Por lotes (esta práctica) sirve para campañas, reportes y listas diarias o mensuales; en tiempo real, para decisiones durante una interacción (por ejemplo, una app). Aquí la pregunta es mensual, así que **el lote es la opción adecuada**.

# %% [markdown]
# ## 8. Llevarlo a Power BI
#
# 1. Agrega `<prefijo>_gold_ml_puntuacion_actividad` al **modelo semántico de la Sesión 4** (o a uno nuevo Direct Lake).
# 2. Crea la relación `puntuacion[cuenta_id]` → `cuentas[cuenta_id]` (muchos a uno, una sola dirección). Así la **seguridad por filas por sucursal** de la Sesión 4 también filtra las predicciones.
# 3. Crea una medida, por ejemplo `Cuentas de alta actividad probable = CALCULATE(COUNTROWS(puntuacion), puntuacion[prediccion] = 1)`, y un visual por sucursal o segmento.
#
# **Verifica con T-SQL** en el SQL analytics endpoint (reemplaza `ab_` por tu prefijo):
#
# ```sql
# SELECT version_modelo, COUNT(*) AS filas, SUM(prediccion) AS marcadas
# FROM ab_gold_ml_puntuacion_actividad
# GROUP BY version_modelo;
# ```

# %% [markdown]
# ## Siguiente paso
#
# Cada ejecución de este notebook registra una versión nueva. En un proceso real eso no se hace a mano: **B4** automatiza el ciclo con una regla de promoción, monitoreo y reversión.
