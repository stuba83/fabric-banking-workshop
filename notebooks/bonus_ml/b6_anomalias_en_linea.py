# %% [markdown]
# # Bonus B6 — Detectar transacciones atípicas y puntuar en línea
#
# **Objetivo.** Recorrer el ciclo de vida de un modelo cuyo uso es **en línea**: una decisión por transacción, en el momento en que ocurre. Se entrena un detector **sin etiquetas**, se mide con anomalías conocidas, se registra, se puntúa por lotes y **una transacción a la vez** por el punto de conexión (*endpoint*) del modelo, y se monitorea sin necesitar etiquetas.
#
# **Qué cambia frente a B1–B4**
#
# | Tema | B1–B4 (propensión de actividad) | B6 (transacciones atípicas) |
# |---|---|---|
# | Tipo de problema | Supervisado, con etiqueta del mes siguiente | **No supervisado**: no hay etiquetas de fraude |
# | Grano | Una fila por cuenta y mes | **Una fila por transacción** |
# | Uso | Por lotes, una vez al mes | Por lotes **y en línea** |
# | Cómo se mide | AUC con la etiqueta real | **Anomalías inyectadas** (conocidas) en validación y prueba |
# | Monitoreo | Deriva y desempeño real | **Tasa de marcadas** y deriva de las variables, que no necesitan etiquetas |
#
# **Honestidad sobre la evaluación.** En un caso real hay pocos casos confirmados o ninguno. Aquí se **inyectan** anomalías de tres tipos (monto extremo, madrugada y ráfaga) en agosto y septiembre para poder medir; las métricas son de datos sintéticos y solo sirven para practicar. Los meses de entrenamiento **no** llevan anomalías inyectadas.
#
# **Idea central: el mismo código para entrenar y para servir.** Las variables de una transacción (qué tan alto es su monto para su tipo, qué tan inusual es su canal para esa cuenta, cuánto pasó desde la anterior) se calculan con **una sola función**. Un servicio en línea necesita esas mismas variables al llamar al *endpoint*: si se calculan distinto, el modelo da resultados distintos. Los almacenes de variables (*feature stores*) existen para resolver esto; aquí se resuelve con la función compartida y una **tabla de referencia** que viaja con el modelo.
#
# **Requisitos.** Sesión 3 completada (tablas plata). Funciona en Trial salvo el *endpoint*, que está en vista previa. `p_confirmar_reemplazo = 'SI'` se necesita para registrar el modelo y escribir las tablas. Cada ejecución registra **una versión nueva** del modelo `<prefijo>_modelo_atipicas_tx`.

# %% parameters
p_lakehouse_esperado = ''
p_prefijo = ''
p_confirmar_reemplazo = 'NO'
p_tasa_revision = 0.01
p_probar_endpoint = 'SI'

# %% embed ml_actividad.py

# %% embed anomalias_tx.py

# %% [markdown]
# ## 1. Preparar
#
# Se reutilizan las protecciones de B1 a B4 (Lakehouse correcto, prefijo válido) y las tablas plata de la Sesión 3. `p_tasa_revision` es la **capacidad de revisión**: la fracción de transacciones que el equipo puede revisar a mano (por defecto 1 %).
#
# `mlflow.autolog(disable=True)` desactiva el registro automático: en Fabric viene activo y cada `fit` crearía una corrida extra con nombre automático. Aquí se registra **exactamente** lo que se decide registrar (igual que en B4).

# %%
import notebookutils
import mlflow
from mlflow.models import infer_signature

mlflow.autolog(disable=True)
lakehouse = validar_parametros_ml(
    notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo,
    exigir_confirmacion=False,
)
nombres = nombres_anomalias(p_prefijo)
tasa_revision = float(p_tasa_revision)
silver = leer_silver(spark, p_prefijo)
tx = preparar_transacciones(silver["transacciones"])
mes_de = tx[FECHA].dt.strftime("%Y-%m")
transacciones_entrenamiento = tx.loc[mes_de.isin(MESES_ENTRENAMIENTO)]
print({"transacciones": len(tx), "meses_entrenamiento": list(MESES_ENTRENAMIENTO), "filas_entrenamiento": len(transacciones_entrenamiento)})

# %% [markdown]
# ## 2. La referencia y las variables de cada transacción
#
# **Referencia.** Para saber si un monto es alto hay que compararlo con lo normal **de su tipo** (500 000 es poco para un salario y mucho para una compra). La referencia guarda la mediana y la desviación robusta del logaritmo del monto por tipo, calculadas **solo con los meses de entrenamiento**.
#
# **Variables.** Cada una usa únicamente lo que ocurrió **antes** de la transacción:
#
# | Variable | Qué mide |
# |---|---|
# | `z_monto_tipo` | Cuántas desviaciones robustas se aleja el monto de lo normal de su tipo |
# | `hora`, `es_fin_semana` | Cuándo ocurrió |
# | `log_minutos_desde_ultima` | Tiempo desde la transacción anterior de la cuenta, en escala logarítmica (los minutos y las horas pesan distinto) |
# | `tx_ultimas_24h` | Cuántas transacciones previas tuvo la cuenta en las últimas 24 horas |
# | `pct_canal_historial` | Qué parte del historial de la cuenta usó este mismo canal (bajo = canal inusual para ella) |
# | `canal`, `tipo_transaccion` | Categóricas |
#
# Una transacción necesita al menos tres previas en su cuenta para tener historial; abril solo aporta historial.

# %%
referencia = calcular_referencia(transacciones_entrenamiento)
display(referencia.round(3))

# %% [markdown]
# ## 3. Anomalías conocidas para poder medir
#
# En agosto (validación) y septiembre (prueba) se **inyectan** anomalías, cerca del 1 % de las filas de cada mes, repartidas por igual en tres tipos:
#
# | Tipo | Qué se hace |
# |---|---|
# | `monto_extremo` | El monto se multiplica por un factor entre 3 y 8 |
# | `madrugada` | La hora pasa a las 0 a 5 h (en estos datos **nunca** ocurre) y el monto sube entre 1 y 2,5 veces |
# | `rafaga` | Tras una transacción se agregan tres más de la misma cuenta, tipo y canal en menos de 20 minutos |
#
# Cada fila lleva su etiqueta (`es_anomalia_inyectada`) y su tipo. Se usan **semillas distintas** para validación y prueba.

# %%
tx_evaluacion = inyectar_anomalias(tx, {MES_VALIDACION: SEMILLA_VALIDACION, MES_PRUEBA: SEMILLA_PRUEBA})
features = construir_features_tx(tx_evaluacion, referencia)
resumen_inyeccion = (
    features.loc[features[ETIQUETA_INYECTADA] == 1]
    .groupby([MES, TIPO_INYECTADO]).size().rename("filas").reset_index()
)
display(resumen_inyeccion)
print({"filas_con_variables": len(features), "inyectadas": int(features[ETIQUETA_INYECTADA].sum())})

# %% [markdown]
# ### Prueba de fuga de datos
#
# Si se **cortan los datos a mitad de septiembre**, las variables de todas las transacciones anteriores al corte no pueden cambiar. Si cambian, alguna variable está usando el futuro (y en producción no lo tendría).

# %%
corte_fuga = pd.Timestamp("2026-09-15")
recortadas = construir_features_tx(tx_evaluacion.loc[tx_evaluacion[FECHA] < corte_fuga], referencia)
diferencias = diferencias_entre_features(features, recortadas)
if diferencias:
    raise ValueError(f"data leakage check: expected 0 differences; observed {diferencias}")
print(f"Sin fuga de datos: {len(recortadas)} transacciones anteriores al corte tienen las mismas variables.")

# %% [markdown]
# ## 4. Entrenar, comparar y elegir
#
# Se entrena **solo con comportamiento normal** (mayo a julio). `LocalOutlierFactor` compara cada transacción nueva contra los datos de entrenamiento, así que se usa una **muestra reproducible** de hasta 20 000 filas.
#
# Se comparan dos familias, con su corrida de MLflow cada una:
#
# - **`iforest`** (*Isolation Forest*): el detector que casi todos prueban primero.
# - **`lof`** (*Local Outlier Factor*), con distintos números de vecinos.
#
# Y una **línea base sin aprendizaje**: marcar lo que supere el monto máximo que su tipo tuvo en el entrenamiento. Se elige con el **AP de validación** (promedio de precisión, que no depende del umbral).

# %%
entrenamiento = features.loc[features[MES].isin(MESES_ENTRENAMIENTO)]
validacion = features.loc[features[MES] == MES_VALIDACION].reset_index(drop=True)
prueba = features.loc[features[MES] == MES_PRUEBA].reset_index(drop=True)
if int(entrenamiento[ETIQUETA_INYECTADA].sum()) != 0:
    raise ValueError("training months: expected no injected anomalies; observed some")
muestra = muestrear_entrenamiento(entrenamiento)
print({"entrenamiento": len(entrenamiento), "muestra": len(muestra), "validacion": len(validacion), "prueba": len(prueba)})

linea_base = regla_maximo_por_tipo(validacion, referencia)
metricas_base = evaluar_deteccion(validacion[ETIQUETA_INYECTADA], linea_base["score_anomalia"], linea_base["es_atipica"])
print("Línea base (máximo por tipo), validación:", {k: round(v, 3) for k, v in metricas_base.items() if k in ("auc", "average_precision", "precision", "recall")})

# %%
from sklearn.metrics import average_precision_score, roc_auc_score

mlflow.set_experiment(nombres["experimento"])
CANDIDATOS = (("iforest", "iforest", 0), ("lof_20", "lof", 20), ("lof_50", "lof", 50), ("lof_100", "lof", 100), ("lof_200", "lof", 200))
filas_candidatos = []
for nombre, tipo, vecinos in CANDIDATOS:
    with mlflow.start_run(run_name=f"candidato_{nombre}"):
        detector = crear_detector(tipo, vecinos or 100).fit(muestra[list(FEATURES_TX)])
        puntaje = -detector.score_samples(validacion[list(FEATURES_TX)])
        auc = float(roc_auc_score(validacion[ETIQUETA_INYECTADA], puntaje))
        ap = float(average_precision_score(validacion[ETIQUETA_INYECTADA], puntaje))
        mlflow.log_params({"tipo_detector": tipo, "vecinos": vecinos, "filas_entrenamiento": len(muestra)})
        mlflow.log_metrics({"auc_validacion": auc, "average_precision_validacion": ap})
    filas_candidatos.append(
        {"nombre": nombre, "tipo": tipo, "vecinos": vecinos, "complejidad": vecinos,
         "auc_validacion": auc, "average_precision_validacion": ap}
    )
candidatos = pd.DataFrame(filas_candidatos)
elegido = elegir_candidato(candidatos)
display(candidatos.round(3))
print("Elegido (el menos complejo a menos de 0,01 de AP del mejor):", elegido)

# %% [markdown]
# **Qué leer en la tabla.** `iforest` rinde mucho peor aquí. No es un error: un *Isolation Forest* separa puntos con cortes al azar **dentro del rango que vio al entrenar**, y una madrugada o un monto muy alto caen **fuera de ese rango**, donde apenas se distinguen del borde. `lof` mide distancia a los vecinos y sí detecta lo que queda lejos. **La elección del algoritmo depende de cómo se ven las anomalías**, y eso se averigua con experimentos, no por reputación.

# %% [markdown]
# ## 5. Fijar el umbral y medir en prueba
#
# El modelo da un **puntaje**; qué tan alto debe ser para marcar depende de **cuántas se pueden revisar**. Se fija el umbral en el mes de **validación** para que se marque aproximadamente `p_tasa_revision`, y queda guardado **dentro del modelo** (`offset_`): el lote, `PREDICT` y el *endpoint* usan exactamente el mismo.
#
# El mes de **prueba** se mide **una sola vez**, con el modelo final.

# %%
elegida = candidatos.loc[candidatos["nombre"] == elegido].iloc[0]
modelo = crear_detector(elegida["tipo"], int(elegida["vecinos"]) or 100).fit(muestra[list(FEATURES_TX)])
umbral = fijar_umbral(modelo, validacion, tasa_revision)

puntos_validacion = puntuar_anomalias(modelo, validacion)
puntos_prueba = puntuar_anomalias(modelo, prueba)
metricas_validacion = evaluar_deteccion(validacion[ETIQUETA_INYECTADA], puntos_validacion["score_anomalia"], puntos_validacion["es_atipica"])
metricas_prueba = evaluar_deteccion(prueba[ETIQUETA_INYECTADA], puntos_prueba["score_anomalia"], puntos_prueba["es_atipica"])
base_prueba = regla_maximo_por_tipo(prueba, referencia)
metricas_base_prueba = evaluar_deteccion(prueba[ETIQUETA_INYECTADA], base_prueba["score_anomalia"], base_prueba["es_atipica"])

comparacion = pd.DataFrame(
    {"validación (umbral fijado)": metricas_validacion, "prueba (modelo)": metricas_prueba, "prueba (línea base)": metricas_base_prueba}
).T[["auc", "average_precision", "precision", "recall", "tasa_marcadas", "prevalencia"]]
display(comparacion.round(3))

por_tipo = recall_por_tipo(prueba, puntos_prueba["es_atipica"].to_numpy()).merge(
    recall_por_tipo(prueba, base_prueba["es_atipica"].to_numpy())[["tipo_anomalia", "recall"]],
    on="tipo_anomalia", suffixes=("_modelo", "_linea_base"),
)
display(por_tipo.round(2))

# %% [markdown]
# **Cómo leerlo.**
#
# - La **línea base** tiene buena precisión (marca poco y casi siempre acierta), pero **solo ve montos altos**: las ráfagas le son invisibles y deja pasar la mayoría de las anomalías.
# - El **modelo** combina varias variables y ve los tres tipos, a cambio de más marcas falsas. **Ninguno gana en todos los tipos**: la línea base detecta mejor los montos extremos. En la práctica se **combinan** reglas y modelo.
# - La **tasa de marcadas** en prueba difiere un poco de `p_tasa_revision`: el umbral se fijó en agosto. Esa diferencia es justo lo que el monitoreo (sección 9) vigila.
# - Con `p_tasa_revision = 1 %`, una precisión cercana a 50 % significa que **de cada dos transacciones que el equipo revisa, una es realmente atípica**. Esa es la conversación de negocio.

# %% [markdown]
# ## 6. Registrar el modelo con su firma y su referencia
#
# La corrida final guarda el modelo con su **firma** (8 columnas de entrada), las métricas y la **referencia** como artefacto: así, quien consuma el modelo sabe con qué referencia se calcularon sus variables. La versión se registra con etiquetas.

# %%
validar_parametros_ml(notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo)
referencia = calcular_referencia(transacciones_entrenamiento, fecha_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
muestra_firma = muestra[list(FEATURES_TX)].head(1000)
with mlflow.start_run(run_name=f"final_{elegido}") as corrida:
    firma = infer_signature(muestra_firma, modelo.predict(muestra_firma))
    mlflow.sklearn.log_model(modelo, "model", signature=firma, serialization_format="cloudpickle")
    mlflow.log_dict({"referencia": referencia.to_dict("records"), "features": list(FEATURES_TX)}, "referencia_tx.json")
    mlflow.log_params({
        "tipo_detector": elegida["tipo"], "vecinos": int(elegida["vecinos"]), "tasa_revision": tasa_revision,
        "umbral_offset": round(umbral, 6), "filas_entrenamiento": len(muestra),
    })
    mlflow.log_metrics({
        **{f"{k}_validacion": v for k, v in metricas_validacion.items()},
        **{f"{k}_prueba": v for k, v in metricas_prueba.items()},
    })
    run_id = corrida.info.run_id
registrada = mlflow.register_model(
    f"runs:/{run_id}/model",
    nombres["modelo"],
    tags={
        "tipo_detector": elegida["tipo"],
        "tasa_revision": str(tasa_revision),
        "mes_prueba": MES_PRUEBA,
        "auc_prueba": f"{metricas_prueba['auc']:.4f}",
        "evaluacion": "anomalias_inyectadas",
    },
)
version = int(registrada.version)
print(f"Modelo {nombres['modelo']}, versión {version}; columnas de entrada en la firma: {len(firma.inputs.input_names())}")

# %% [markdown]
# ### La versión cargada es el mismo modelo
#
# Cargar `models:/<nombre>/<versión>` es lo que harán otros notebooks, pipelines y el *endpoint*. Debe dar **exactamente** los mismos puntajes y las mismas marcas, incluido el umbral.

# %%
modelo_registrado = mlflow.sklearn.load_model(f"models:/{nombres['modelo']}/{version}")
muestra_prueba = prueba.head(2000)
if not np.allclose(modelo.decision_function(muestra_prueba[list(FEATURES_TX)]), modelo_registrado.decision_function(muestra_prueba[list(FEATURES_TX)])):
    raise ValueError("registry roundtrip: expected identical scores; observed differences")
if not np.array_equal(modelo.predict(muestra_prueba[list(FEATURES_TX)]), modelo_registrado.predict(muestra_prueba[list(FEATURES_TX)])):
    raise ValueError("registry roundtrip: expected identical flags; observed differences")
print("La versión registrada reproduce los puntajes y las marcas (el umbral viaja dentro del modelo).")

# %% [markdown]
# ## 7. Puntuar por lotes
#
# Se puntúa septiembre y se guardan dos tablas: la **referencia** (nueve filas) y las **transacciones puntuadas**, con la versión del modelo y la fecha para poder auditar qué modelo marcó qué. La escritura reemplaza solo las filas de este mes, así que se puede repetir sin duplicar.

# %%
puntuadas = puntuar_anomalias(modelo_registrado, prueba)
detalle = prueba[[CLAVE_TX, CUENTA, MES, FECHA, "tipo_transaccion", "canal", "monto", ETIQUETA_INYECTADA, TIPO_INYECTADO]].merge(puntuadas, on=CLAVE_TX)
detalle[FECHA] = detalle[FECHA].dt.strftime("%Y-%m-%d %H:%M:%S")
detalle["version_modelo"] = version
detalle["fecha_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
filas_referencia = escribir_tabla(spark, nombres["referencia"], referencia, COLUMNAS_REFERENCIA_TX)
filas_puntuadas = reemplazar_corte(spark, nombres["anomalias"], detalle, COLUMNAS_ANOMALIAS_TX, MES, MES_PRUEBA)
print(json.dumps({"status": "success", "referencia": filas_referencia, "puntuadas": filas_puntuadas, "version": version}))
display(detalle.sort_values("score_anomalia", ascending=False).head(10))

# %% [markdown]
# ### PREDICT: el mismo resultado con Spark
#
# `PREDICT` aplica el modelo registrado a un DataFrame de Spark. Debe dar **la misma marca** que la puntuación con pandas (`-1` = atípica, `1` = normal). Los sabores soportados incluyen `sklearn`, y la firma es obligatoria.

# %%
try:
    from synapse.ml.predict import MLFlowTransformer
except ImportError as error:
    print(f"MLFlowTransformer no disponible en este entorno: {error}")
else:
    entrada = spark.createDataFrame(prueba[[CLAVE_TX, *FEATURES_TX]])
    transformador = MLFlowTransformer(
        inputCols=list(FEATURES_TX), outputCol="prediccion_predict",
        modelName=nombres["modelo"], modelVersion=version,
    )
    predict = transformador.transform(entrada).select(CLAVE_TX, "prediccion_predict").toPandas()
    union = puntuadas.merge(predict, on=CLAVE_TX)
    acuerdo = float(((union["es_atipica"] == 1) == (union["prediccion_predict"].astype(int) == -1)).mean())
    print(f"Acuerdo entre pandas y PREDICT: {acuerdo:.4f} ({len(union)} transacciones)")
    if acuerdo < 1.0:
        raise ValueError(f"PREDICT: expected agreement 1.0; observed {acuerdo}")

# %% [markdown]
# ## 8. Puntuar en línea: una transacción por el *endpoint*
#
# En línea, una aplicación recibe **una** transacción y necesita decidir al instante. Calcula sus variables y llama al *endpoint*. Lo importante es **cómo se calculan esas variables**: con `features_de_una_transaccion`, que usa el **mismo código** que el entrenamiento, el historial previo de la cuenta y la referencia.
#
# Aquí se arman dos solicitudes para una cuenta real: una transacción **normal** y una **sospechosa** (una compra por cajero automático a las 3 a. m. con un monto seis veces el habitual).

# %%
cuenta_ejemplo = tx_evaluacion.loc[tx_evaluacion[ETIQUETA_INYECTADA] == 0].groupby(CUENTA).size().loc[lambda s: s >= 20].index[0]
historial = tx_evaluacion.loc[(tx_evaluacion[CUENTA] == cuenta_ejemplo) & (tx_evaluacion[ETIQUETA_INYECTADA] == 0) & (tx_evaluacion[FECHA] < pd.Timestamp("2026-09-20"))]
ultima = historial.sort_values(FECHA).iloc[-1]
habitual = float(historial.loc[historial["tipo_transaccion"] == "COMPRA", "monto"].median())
nuevas = {
    "normal": {CLAVE_TX: "TXNUEVA01", CUENTA: cuenta_ejemplo, FECHA: pd.Timestamp("2026-09-21 11:30:00"),
               "tipo_transaccion": "COMPRA", "direccion": "DEBITO", "canal": ultima["canal"], "monto": habitual},
    "sospechosa": {CLAVE_TX: "TXNUEVA02", CUENTA: cuenta_ejemplo, FECHA: pd.Timestamp("2026-09-21 03:05:00"),
                   "tipo_transaccion": "COMPRA", "direccion": "DEBITO", "canal": "ATM", "monto": round(habitual * 6, 2)},
}
solicitudes = {nombre: features_de_una_transaccion(historial, nueva, referencia) for nombre, nueva in nuevas.items()}
variables_en_linea = pd.concat(solicitudes.values(), ignore_index=True)
display(variables_en_linea[[CLAVE_TX, *FEATURES_TX]].round(3))
cuerpo = solicitud_endpoint(variables_en_linea)
print("Cuerpo de la solicitud (formato del endpoint):")
print(json.dumps(cuerpo, ensure_ascii=False)[:600])
local = puntuar_anomalias(modelo_registrado, variables_en_linea)
display(local.assign(descripcion=list(nuevas)).round(3))

# %% [markdown]
# **Llamar al *endpoint* (vista previa).** Un modelo nuevo **nunca** tiene su *endpoint* activo: se activa a propósito, desde la página de la versión (**Activate version endpoint**) o por la API, y tarda unos minutos. Esta celda **no activa nada**: busca la versión activa más reciente del modelo, le envía la solicitud, mide el tiempo y comprueba que la respuesta coincida con la de **esa misma versión** cargada aquí. Si no hay ninguna activa, lo dice y sigue.
#
# **Cómo probarla:** activa una versión, espera a que quede `Active` y **vuelve a ejecutar solo esta celda**. Recuerda lo documentado: sabores `sklearn`, LightGBM, XGBoost y Keras con firma; se **duerme a los 5 minutos** sin uso (y la primera llamada tarda más); consume capacidad mientras está activo.

# %%
if p_probar_endpoint != "SI":
    print("Prueba del endpoint omitida (p_probar_endpoint distinto de 'SI').")
else:
    try:
        import sempy.fabric as fabric
        modelos = fabric.list_items(type="MLModel")
        id_modelo = modelos.loc[modelos["Display Name"] == nombres["modelo"], "Id"].iloc[0]
        respuesta_endpoint = puntuar_en_linea(
            fabric.FabricRestClient(), notebookutils.runtime.context["currentWorkspaceId"], id_modelo, cuerpo
        )
    except Exception as error:  # el endpoint es una vista previa: puede no estar disponible en tu tenant
        respuesta_endpoint = {"estado": f"no disponible ({type(error).__name__}: {str(error)[:120]})", "version": None, "predicciones": None}
    print("Endpoint del modelo", nombres["modelo"], "→", respuesta_endpoint["estado"])
    if respuesta_endpoint["predicciones"] is None:
        print("Para probarlo: activa una versión en su página (Activate version endpoint) y vuelve a ejecutar esta celda.")
    else:
        activo = mlflow.sklearn.load_model(f"models:/{nombres['modelo']}/{respuesta_endpoint['version']}")
        esperado = [int(m) for m in activo.predict(variables_en_linea[list(FEATURES_TX)])]
        print("Versión", respuesta_endpoint["version"], "| marcas del endpoint (-1 = atípica):", respuesta_endpoint["predicciones"], "| tiempo de la llamada:", round(respuesta_endpoint["segundos"], 2), "s")
        if respuesta_endpoint["predicciones"] != esperado:
            raise ValueError(f"endpoint: expected {esperado}; observed {respuesta_endpoint['predicciones']}")
        print("El endpoint coincide con la puntuación local de la misma versión.")

# %% [markdown]
# ## 9. Monitorear sin etiquetas
#
# Los casos confirmados llegan tarde (o nunca). Mientras tanto hay dos señales que **no necesitan etiquetas**:
#
# 1. **La tasa de marcadas.** Si el umbral se fijó para marcar el 1 %, una tasa que se duplica o desaparece indica un cambio.
# 2. **La deriva de las variables** (PSI, igual que en B4) entre el entrenamiento y el mes nuevo.
#
# Para ver que funcionan se **simula** un cambio de comportamiento: en septiembre, todos los montos suben 60 % (por ejemplo, por inflación o una campaña). Las variables se recalculan y se vuelven a puntuar.

# %%
def reporte_deriva_tx(referencia_df: "pd.DataFrame", actual_df: "pd.DataFrame") -> "pd.DataFrame":
    filas = [{"variable": c, "psi": psi_numerico(referencia_df[c], actual_df[c])} for c in FEATURES_NUMERICAS_TX]
    filas += [{"variable": c, "psi": psi_categorico(referencia_df[c], actual_df[c])} for c in FEATURES_CATEGORICAS_TX]
    resultado = pd.DataFrame(filas)
    resultado["deriva"] = resultado["psi"].map(clasificar_psi)
    return resultado.sort_values("psi", ascending=False).reset_index(drop=True)


tx_simulada = tx_evaluacion.copy()
en_prueba = tx_simulada[FECHA].dt.strftime("%Y-%m") == MES_PRUEBA
tx_simulada.loc[en_prueba, "monto"] = (tx_simulada.loc[en_prueba, "monto"] * 1.6).round(2)
prueba_simulada = construir_features_tx(tx_simulada, referencia)
prueba_simulada = prueba_simulada.loc[prueba_simulada[MES] == MES_PRUEBA].reset_index(drop=True)

marcadas_por_mes = pd.DataFrame(
    [
        {"escenario": "validación (donde se fijó el umbral)", "tasa_marcadas": float(puntos_validacion["es_atipica"].mean())},
        {"escenario": "prueba (septiembre)", "tasa_marcadas": float(puntos_prueba["es_atipica"].mean())},
        {"escenario": "prueba con montos +60 % (simulado)", "tasa_marcadas": float(puntuar_anomalias(modelo_registrado, prueba_simulada)["es_atipica"].mean())},
    ]
)
display(marcadas_por_mes.round(4))
deriva_normal = reporte_deriva_tx(muestra, prueba)
deriva_simulada = reporte_deriva_tx(muestra, prueba_simulada)
display(deriva_normal.merge(deriva_simulada, on="variable", suffixes=("_septiembre", "_simulado")).round(3))

# %% [markdown]
# **Qué leer.** Con datos normales las variables quedan `estable` y la tasa de marcadas se mantiene cerca de la capacidad de revisión. Con el cambio simulado, **`z_monto_tipo` deriva** y la tasa de marcadas **se dispara**: el sistema avisa aunque no haya una sola etiqueta. Qué hacer con el aviso (revisar la referencia, reentrenar con datos nuevos) es una decisión de una persona, igual que en B4.
#
# Fabric no trae un monitor de deriva integrado: esta medición vive en tablas y notebooks propios, y las alertas se pueden enviar con **Activator** o desde un pipeline.

# %% [markdown]
# ## 10. Llevarlo a producción: qué falta
#
# | Pieza | En este bonus | En un proceso real |
# |---|---|---|
# | Etiquetas | Anomalías inyectadas | Casos que el equipo de revisión confirma o descarta; con ellas se mide precisión real |
# | Referencia y variables | Función compartida + tabla de referencia | Un almacén de variables o un servicio que calcule las mismas variables en línea |
# | Umbral | Capacidad de revisión fija (1 %) | Se revisa con la precisión observada y el costo de una revisión |
# | Ciclo mensual | Se ejecuta a mano | Se programa como en B4 (campeón, retador, regla de promoción, reversión) |
# | Endpoint | Se activa a mano | Se activa en el despliegue; se mide su latencia con la carga real antes de comprometer un SLA |
#
# **Siguiente paso.** Reemplazar el dataset sintético por tus transacciones, mantener la misma estructura (referencia, variables sin fuga, evaluación temporal, umbral por capacidad) y medir con los casos que ya conozcas.
