# %% [markdown]
# # Bonus B1 — Preparar los datos para ML
#
# **Caso del bonus.** Dado el comportamiento de una cuenta hasta el cierre de un mes, ¿tendrá **al menos 9 transacciones** el mes siguiente? Es una pregunta de clasificación binaria sobre las tablas plata de la Sesión 3. Los datos son **sintéticos**: las métricas sirven para practicar el ciclo de vida, no para estimar el rendimiento de un modelo real.
#
# **Qué hace este notebook**
#
# 1. Lee las tablas plata (`<prefijo>_silver_*`) y comprueba sus conteos.
# 2. Explora los datos y practica **Data Wrangler**.
# 3. Construye una tabla de *features* con un corte por mes y la etiqueta del mes siguiente.
# 4. Demuestra que las variables **no usan datos posteriores al corte** (sin fuga de datos).
# 5. Guarda la tabla `<prefijo>_gold_ml_features_cuentas` en el Lakehouse.
# 6. (Opcional) Usa **semantic link** para reconciliar con el modelo semántico de la Sesión 4.
#
# **Requisitos.** Sesión 3 completada, Lakehouse propio como predeterminado y un runtime PySpark de Fabric. Todo lo de este notebook funciona en una capacidad Trial, **excepto** las funciones de IA de Data Wrangler, que requieren capacidad de pago (se indican más abajo).
#
# **Parámetros.** `p_confirmar_reemplazo = 'SI'` solo se necesita para escribir la tabla. Puedes explorar con `'NO'`.

# %% parameters
p_lakehouse_esperado = ''
p_prefijo = ''
p_confirmar_reemplazo = 'NO'
p_modelo_semantico = ''

# %% embed ml_actividad.py

# %% [markdown]
# ## 1. Leer las tablas plata
#
# La lectura falla antes de cargar datos si una tabla no existe o no tiene el conteo medido en la Sesión 3 (72.000 transacciones, 1.800 cuentas y 1.200 clientes). Las tablas pequeñas se llevan a pandas por claridad didáctica; con volúmenes grandes, las mismas reglas se expresan con Spark.

# %%
import notebookutils

lakehouse = validar_parametros_ml(
    notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo,
    exigir_confirmacion=False,
)
nombres = nombres_ml(p_prefijo)
silver = leer_silver(spark, p_prefijo)
tx, cuentas, clientes = silver["transacciones"], silver["cuentas"], silver["clientes"]
print(f"Lakehouse: {lakehouse}")
print({nombre: len(tabla) for nombre, tabla in silver.items()})

# %% [markdown]
# ## 2. Exploración rápida
#
# Antes de modelar, mira los datos. Tres preguntas que conviene responder siempre: ¿cuántas filas hay?, ¿qué valores toma cada variable? y ¿hay valores faltantes o raros?

# %%
display(tx.head())
print(tx["monto"].describe())
print(tx["canal"].value_counts())
print(tx.groupby(tx["fecha_hora"].dt.to_period("M")).size())

# %% [markdown]
# ## 3. Data Wrangler (práctica guiada)
#
# **Data Wrangler** es una herramienta visual dentro del notebook para explorar y limpiar un DataFrame de **pandas o de Spark**. Muestra un resumen por columna y **genera el código** de cada paso, que luego se exporta al notebook como una función. Es útil para explorar rápido y para aprender la sintaxis; el código generado se revisa como cualquier otro.
#
# **Pasos**
#
# 1. Ejecuta la celda siguiente, que deja un DataFrame de pandas llamado `tx_dw`. Data Wrangler no se puede abrir mientras el kernel está ocupado.
# 2. En la cinta del notebook, abre **Data Wrangler** y elige `tx_dw`. También puede aparecer una invitación al mostrar `df.head()`.
# 3. En el **resumen**, revisa por columna los valores faltantes, los distintos y la distribución. Mira `canal` y `monto`.
# 4. En el panel de **operaciones**, aplica **agrupar y agregar** (*Group by and aggregate*): agrupa por `cuenta_id` y cuenta las filas. Revisa la vista previa del resultado.
# 5. Selecciona **agregar el código al notebook** (*Add code to notebook*). Se crea una función y una celda que la llama. Renombra el DataFrame resultante a `conteo_dw` y la columna del conteo a `n_tx`.
# 6. Ejecuta la celda de verificación que sigue: compara tu resultado con `tx.groupby("cuenta_id").size()`.
#
# Otras operaciones para probar (la lista exacta depende de la versión): ordenar, filtrar, cambiar el tipo de una columna, rellenar o eliminar faltantes y codificar categorías.
#
# > **Solo con capacidad de pago (F2 o superior).** Data Wrangler también ofrece sugerencias con **IA** (*AI enrichments* y una caja de Copilot para describir una transformación en lenguaje natural). Requieren los ajustes de inquilino de Copilot y Azure OpenAI, y no funcionan en Trial. Si las tienes, prueba: «agrega una columna con el porcentaje de transacciones de fin de semana por cuenta» y **revisa el código** antes de aceptarlo.

# %%
tx_dw = tx[["cuenta_id", "fecha_hora", "tipo_transaccion", "direccion", "canal", "monto"]].copy()
tx_dw.head()

# %%
if "conteo_dw" in globals():
    esperado = tx.groupby("cuenta_id").size()
    observado = conteo_dw.set_index("cuenta_id")["n_tx"]
    if esperado.sort_index().equals(observado.sort_index().astype(esperado.dtype)):
        print(f"Coincide con pandas: {len(observado)} cuentas, {int(observado.sum())} transacciones.")
    else:
        print("No coincide: revisa la agrupación (columna cuenta_id, conteo de filas) y el nombre n_tx.")
else:
    print("Aún no existe conteo_dw. Completa la práctica de Data Wrangler o sigue con el notebook.")

# %% [markdown]
# ## 4. Construir las features
#
# Cada fila es **una cuenta en un corte mensual**. Las variables usan una **ventana fija de dos meses** (el mes de corte y el anterior) y la etiqueta mira el **mes siguiente**.
#
# | Variable | Qué mide |
# |---|---|
# | `tx_mes_corte`, `tx_mes_previo`, `tx_ventana` | Transacciones del mes de corte, del anterior y de ambos |
# | `monto_ventana`, `monto_prom_ventana` | Monto total y promedio en la ventana |
# | `pct_credito`, `pct_fin_semana` | Proporción de créditos y de movimientos en fin de semana |
# | `pct_banca_movil`, `pct_web`, `pct_atm`, `pct_sucursal` | Mezcla de canales |
# | `n_tipos`, `dias_desde_ultima` | Variedad de movimientos y días sin actividad |
# | `saldo_inicial`, `producto_id`, `segmento` | Datos de la cuenta y del cliente |
#
# **Por qué ventanas fijas.** Una variable acumulada (como «transacciones totales») crece con el calendario: el monitoreo la marcaría como deriva aunque el comportamiento no haya cambiado. Con ventanas fijas, un cambio en la variable es un cambio real.
#
# **Variables que no entran al modelo.** `grupo_edad` y `provincia` son atributos sensibles: no se usan para predecir, pero sí para **auditar** si el modelo se comporta distinto entre grupos (B2).

# %%
CORTES = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
features = construir_dataset(tx, cuentas, clientes, CORTES)

problemas = validar_features(features, cuentas_esperadas=len(cuentas))
if problemas:
    raise ValueError("features: " + "; ".join(problemas))

resumen = features.groupby(CORTE)[ETIQUETA].agg(filas="size", etiquetadas="count", positivas="sum", prevalencia="mean")
display(resumen)

# %% [markdown]
# **Controles esperados.** Cada corte tiene 1.800 filas. Las positivas son 563, 589, 631 y 651 para los cortes de mayo a agosto. El corte de septiembre **no tiene etiqueta**: su mes siguiente (octubre) aún no ocurre. Esas son las filas que se puntúan, no las que se entrenan.
#
# Fíjate también en la prevalencia: sube de 31 % a 36 % porque la actividad crece mes a mes. Es un cambio real de la población que el monitoreo (B4) tendrá que distinguir de una falsa alarma.

# %%
positivas = resumen["positivas"].astype(int).to_dict()
esperadas = {"2026-05": 563, "2026-06": 589, "2026-07": 631, "2026-08": 651, "2026-09": 0}
if positivas != esperadas:
    raise ValueError(f"control positivas por corte: expected {esperadas!r}; observed {positivas!r}")
print("Controles de etiquetas conformes:", positivas)

# %% [markdown]
# ## 5. Prueba de fuga de datos
#
# La **fuga de datos** ocurre cuando una variable usa información que no existiría al momento de predecir. La prueba es simple: si se eliminan todos los movimientos posteriores al corte, las variables de ese corte **no deben cambiar**.

# %%
fin_julio = pd.Timestamp("2026-07-31 23:59:59")
recortada = construir_features(tx[tx["fecha_hora"] <= fin_julio], cuentas, clientes, "2026-07")
completa = features[features[CORTE] == "2026-07"].reset_index(drop=True)
pd.testing.assert_frame_equal(recortada[[CLAVE, *FEATURES]], completa[[CLAVE, *FEATURES]])
print("Sin fuga de datos: las variables de julio no cambian al quitar agosto y septiembre.")
print("Con datos solo hasta julio, la etiqueta de julio queda vacía:", bool(recortada[ETIQUETA].isna().all()))

# %% [markdown]
# ## 6. Guardar la tabla de features
#
# Requiere `p_confirmar_reemplazo = 'SI'`. La escritura reemplaza **solo** la tabla `<prefijo>_gold_ml_features_cuentas` y comprueba el conteo escrito (9.000 filas = 1.800 cuentas × 5 cortes).

# %%
validar_parametros_ml(notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo)
filas = escribir_tabla(spark, nombres["features"], features, COLUMNAS_FEATURES)
print(json.dumps({"status": "success", "tabla": nombres["features"], "filas": filas}, ensure_ascii=False))

# %% [markdown]
# **Verifica con T-SQL** en el SQL analytics endpoint de tu Lakehouse (reemplaza `ab_` por tu prefijo):
#
# ```sql
# SELECT corte, COUNT(*) AS filas, SUM(alta_actividad_siguiente) AS positivas
# FROM ab_gold_ml_features_cuentas
# GROUP BY corte
# ORDER BY corte;
# ```
#
# Debes ver 1.800 filas por corte y las positivas de la sección 4 (septiembre sin etiqueta).

# %% [markdown]
# ## 7. Semantic link (opcional)
#
# **Semantic link** conecta los notebooks con los modelos semánticos de Power BI. Aquí sirve para **reconciliar**: la medida `Transacciones` del modelo de la Sesión 4 debe coincidir con lo que calcula pandas sobre las tablas plata. Escribe en `p_modelo_semantico` el nombre de tu modelo (por ejemplo, `AB_SM_Transacciones`) y vuelve a ejecutar esta celda. Funciona en Trial.

# %%
if p_modelo_semantico:
    import sempy.fabric as fabric

    consulta = (
        f"EVALUATE SUMMARIZECOLUMNS('{p_prefijo.lower()}_silver_calendario'[mes], "
        '"Transacciones", [Transacciones])'
    )
    modelo = fabric.evaluate_dax(dataset=p_modelo_semantico, dax_string=consulta)
    por_mes_modelo = modelo.set_axis(["mes", "transacciones"], axis=1).sort_values("mes")
    por_mes_pandas = tx.groupby(tx["fecha_hora"].dt.month).size().rename("transacciones").reset_index()
    por_mes_pandas.columns = ["mes", "transacciones"]
    unido = por_mes_modelo.merge(por_mes_pandas, on="mes", suffixes=("_modelo", "_pandas"))
    unido["coincide"] = unido["transacciones_modelo"] == unido["transacciones_pandas"]
    display(unido)
    if not unido["coincide"].all() or len(unido) != 6:
        raise ValueError("reconciliacion: expected 6 matching months; observed differences")
    print("El modelo semántico coincide con las tablas plata en los 6 meses.")
else:
    print("Sin modelo semántico indicado: se omite la reconciliación.")

# %% [markdown]
# **Comprobar un rol de seguridad desde el notebook.** `evaluate_dax` acepta el parámetro `role`, así que puedes verificar la regla por filas de la Sesión 4 sin abrir el reporte. Con el rol `Heredia` debes ver 8.971 transacciones. El resultado depende de tus permisos sobre el modelo; si falla, mira el mensaje y vuelve a **Test as role** en el servicio.

# %%
if p_modelo_semantico:
    try:
        con_rol = fabric.evaluate_dax(
            dataset=p_modelo_semantico,
            dax_string='EVALUATE ROW("Transacciones", [Transacciones])',
            role="Heredia",
        )
        display(con_rol)
    except Exception as error:  # el rol puede no existir o faltar permisos
        print(f"No se pudo evaluar con el rol Heredia: {error}")

# %% [markdown]
# ## Qué sigue
#
# La tabla de features queda lista para **B2: entrenar y comparar experimentos con MLflow**.
