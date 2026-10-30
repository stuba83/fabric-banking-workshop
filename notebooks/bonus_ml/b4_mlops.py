# %% [markdown]
# # Bonus B4 — MLOps: automatizar el ciclo, decidir con reglas y vigilar el modelo
#
# **Objetivo.** Convertir el trabajo de B1–B3 en un **ciclo repetible**: cada mes se validan los datos, se entrena un *retador*, se decide con una regla explícita si reemplaza al *campeón*, se puntúa y se **monitorea** el modelo. Todo queda registrado y se puede reejecutar sin duplicar nada.
#
# ```text
#  datos (features)  →  compuerta de calidad  →  entrenar retador  →  ¿mejora al campeón?
#        ↑                                                              │ sí: registrar versión
#        │                                                              │ no: conservar campeón
#        └── etiquetas del mes anterior  ←  monitoreo  ←  puntuar con el campeón
# ```
#
# **Qué aporta Fabric y qué construimos nosotros**
#
# | Pieza | Fabric | En este notebook |
# |---|---|---|
# | Orquestación | Actividad **Notebook** de un pipeline, con parámetros y programación | Parámetros `p_*` y el modo `ciclo` |
# | Seguimiento de experimentos | Experimentos y corridas de MLflow | Una corrida por ciclo, con decisión y métricas |
# | Registro de versiones | Elemento de modelo con versiones y etiquetas | Se registra **solo** al promover |
# | Quién es el campeón | Sin etapas ni alias documentados | **Tabla de control** auditable (`<prefijo>_ml_registro_modelos`) |
# | Monitoreo de calidad del modelo | No hay una función de deriva integrada (solo métricas de tráfico del endpoint) | **PSI** y desempeño real, guardados en tablas Delta |
# | Alertas | **Activator** y estado de las ejecuciones | Recomendación (`sin_accion`, `revisar`, `reentrenar`) |
#
# **Dos modos.** `p_modo = 'guiado'` (por defecto) recorre seis escenarios para **aprender**. `p_modo = 'ciclo'` ejecuta **un** ciclo con los parámetros que recibe y devuelve el resumen; es el que se programa en un pipeline.
#
# **Requisitos.** B1 completado. Funciona en Trial. Requiere `p_confirmar_reemplazo = 'SI'`: escribe tablas y registra versiones. Cada ciclo toma de uno a dos minutos.

# %% parameters
p_lakehouse_esperado = ''
p_prefijo = ''
p_confirmar_reemplazo = 'NO'
p_modo = 'guiado'
p_corte_puntuacion = '2026-09'
p_tipo_modelo = 'logreg'
p_factor_deriva = 0.0

# %% embed ml_actividad.py

# %% [markdown]
# ## 1. Preparar
#
# `mlflow.autolog(disable=True)` desactiva el registro automático: en un proceso de producción se registra **exactamente** lo que se decide registrar. `ciclo()` envuelve a `ejecutar_ciclo` con tus parámetros.

# %%
import notebookutils
import mlflow

mlflow.autolog(disable=True)
nombres = nombres_ml(p_prefijo)
contexto = notebookutils.runtime.context
validar_parametros_ml(contexto, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo)


def ciclo(corte, tipo=None, factor=0.0):
    return ejecutar_ciclo(
        spark, mlflow, contexto, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo,
        p_corte_puntuacion=corte, p_tipo_modelo=tipo or p_tipo_modelo, p_factor_deriva=factor,
    )


def tabla(clave, **filtros):
    datos = leer_tabla(spark, nombres[clave], opcional=True)
    if datos is None:
        return None
    for columna, valor in filtros.items():
        datos = datos[datos[columna] == valor]
    return datos.reset_index(drop=True)


print("Modo:", p_modo)

# %% [markdown]
# ## Escenario 1 — La historia: el cierre de agosto
#
# Se simula que estamos al **cierre de agosto**. El ciclo solo ve cortes hasta agosto y **no conoce la etiqueta del corte que puntúa** (la actividad de septiembre aún no ocurre). Es la regla de *corrección en el tiempo*: una ejecución retrospectiva no puede ver el futuro.
#
# Como aún no hay campeón, el retador solo debe superar un **piso de calidad** (AUC ≥ 0,70). Se promueve y se registra como versión 1.

# %%
if p_modo == "guiado":
    informe_agosto = ciclo("2026-08")
    display(tabla("registro"))

# %% [markdown]
# ## Escenario 2 — El mes siguiente: el cierre de septiembre
#
# Ahora hay un campeón. El ciclo entrena un retador con los datos nuevos y **ambos se evalúan en el mismo corte de prueba**. Se promueve solo si el AUC mejora al menos **0,005**; en caso contrario, el campeón se conserva.
#
# Además, ya llegó la etiqueta del mes pasado: se mide el **AUC real** de las predicciones que el campeón hizo en agosto. Esa es la única forma de saber cómo le va al modelo en producción.

# %%
if p_modo == "guiado":
    informe_septiembre = ciclo("2026-09")
    print("Decisión:", informe_septiembre["decision"], "|", informe_septiembre["motivo"])
    display(tabla("desempeno"))

# %% [markdown]
# **Qué esperar.** Con estos datos, el retador casi nunca supera por 0,005 al campeón: la decisión habitual es `mantener`. Que no se promueva es el resultado **correcto** si no hay mejora; la regla evita cambiar de modelo por ruido. El AUC real del mes anterior queda cerca del de prueba (≈ 0,85).

# %% [markdown]
# ## Escenario 3 — Reejecutar sin duplicar
#
# Una reejecución con los mismos datos debe dejar **todo igual**: mismas filas, ninguna versión nueva. Es lo que permite que un pipeline reintente tras un fallo sin ensuciar los datos. Si algo no cuadra, el notebook se detiene.

# %%
if p_modo == "guiado":
    antes = {clave: len(tabla(clave)) for clave in ("registro", "puntuacion", "deriva", "desempeno")}
    informe_repeticion = ciclo("2026-09")
    despues = {clave: len(tabla(clave)) for clave in ("registro", "puntuacion", "deriva", "desempeno")}
    print("Filas antes:", antes)
    print("Filas después:", despues)
    if antes != despues:
        raise ValueError(f"idempotencia: expected {antes!r}; observed {despues!r}")
    print("Sin duplicados: el ciclo es idempotente.")

# %% [markdown]
# ## Escenario 4 — Deriva: simular una campaña
#
# **Deriva** es un cambio en los datos de entrada respecto de los de entrenamiento. Se mide con el **PSI** (índice de estabilidad de la población) por variable: menos de 0,10 es estable, de 0,10 a 0,25 moderada y de 0,25 en adelante alta.
#
# Aquí se multiplica la actividad por 1,6 (por ejemplo, una campaña) y se vuelve a correr el ciclo para comprobar que el monitoreo **lo detecta**. Después se restaura el ciclo normal.

# %%
if p_modo == "guiado":
    informe_deriva = ciclo("2026-09", factor=1.6)
    print("Variables con deriva:", informe_deriva["deriva"])
    print("Alertas:", informe_deriva["alertas"])
    print("Recomendación:", informe_deriva["recomendacion"])
    display(tabla("deriva", corte="2026-09").sort_values("psi", ascending=False).head(6))
    ciclo("2026-09")  # restaura la puntuación y la deriva reales de septiembre

# %% [markdown]
# **Qué esperar.** Las variables de actividad (`tx_mes_corte`, `tx_mes_previo`, `tx_ventana`, `monto_ventana`) superan 0,25. La recomendación es **`revisar`**, no `reentrenar`: la deriva de entrada avisa, pero solo la **caída del AUC real** (cuando llegan las etiquetas) justifica reentrenar. Sobre los datos reales casi todo es `estable`.
#
# **Una lección de diseño.** Si las variables fueran acumuladas (como las transacciones totales desde el inicio), el PSI marcaría deriva **cada mes** sin que nada haya cambiado. Por eso las features de B1 usan ventanas fijas.

# %% [markdown]
# ## Escenario 5 — Un retador más complejo
#
# ¿Y si probamos un bosque aleatorio (`rf`)? La compuerta decide con la **misma regla**. Los resultados quedan registrados como corrida de MLflow aunque no se promueva.

# %%
if p_modo == "guiado":
    informe_rf = ciclo("2026-09", tipo="rf")
    print("Decisión:", informe_rf["decision"], "|", informe_rf["motivo"])
    print("AUC prueba retador:", round(informe_rf["retador"]["auc"], 4),
          "| campeón:", round(informe_rf["campeon_previo"]["auc"], 4))

# %% [markdown]
# ## Escenario 6 — Reversión (*rollback*)
#
# Si una versión nueva da problemas, se vuelve a la anterior **sin borrar nada**: se agrega un evento de reversión a la tabla de control. Si solo hay una versión, no hay a qué volver y la celda lo indica.

# %%
if p_modo == "guiado":
    registro = tabla("registro")
    versiones = sorted(registro["version"].unique().tolist())
    if len(versiones) >= 2:
        campeon_tras = revertir_campeon(spark, p_prefijo, versiones[0], "demostración de reversión")
        print("Campeón tras la reversión:", campeon_tras["version"])
    else:
        print(f"Solo existe la versión {versiones[0]}: la reversión requiere al menos dos versiones.")
    display(tabla("registro"))

# %% [markdown]
# ## Modo ciclo: lo que se programa en un pipeline
#
# En `p_modo = 'ciclo'` solo se ejecuta esta celda: un ciclo con los parámetros recibidos. `notebookutils.notebook.exit` devuelve el resumen al pipeline, que puede decidir qué hacer según `recomendacion`.

# %%
if p_modo == "ciclo":
    informe = ciclo(p_corte_puntuacion, factor=float(p_factor_deriva))
    notebookutils.notebook.exit(json.dumps(informe))

# %% [markdown]
# ## Llevarlo a producción en Fabric
#
# **Orquestar y programar.** En un pipeline, agrega una actividad **Notebook** y define los parámetros base (`p_modo = ciclo`, `p_corte_puntuacion`, etc.): llegan al notebook a través de la **celda de parámetros**. Programa el pipeline cada mes. Para encadenar notebooks en código existen `notebookutils.notebook.run` y `runMultiple`.
#
# **Bibliotecas reproducibles.** Las instalaciones en línea (`%pip`) están desactivadas por defecto en las ejecuciones de pipeline. Fija las versiones en un **Environment** y publícalo en modo completo para tener un entorno estable.
#
# **Control de versiones y despliegue.** Los **notebooks**, los **environments** y las **bibliotecas de variables** se integran con Git y con los *deployment pipelines*. Los **experimentos y modelos de ML** también (vista previa), pero **solo viajan sus metadatos**: las corridas y las versiones del modelo no se copian entre workspaces. Para llevar un modelo a otro workspace se registra de nuevo en el destino con el complemento `synapseml-mlflow` y la variable `MLFLOW_TRACKING_URI`.
#
# **Observar y alertar.** El **hub de monitoreo** muestra las ejecuciones (y los experimentos, en vista previa); **Activator** puede avisar cuando una ejecución falla o cuando un valor, por ejemplo la recomendación, cambia.
#
# **Gobernanza.** El modelo, el experimento y las tablas aparecen en la **vista de linaje**; **promueve** el modelo cuando esté listo para reutilizarse, como en la Sesión 4.
#
# **Lo que este ciclo no resuelve.** No hay reentrenamiento automático por deriva (se decide con una persona), no hay pruebas A/B ni se versionan los datos de entrenamiento. Son los siguientes pasos de un proceso real.

# %% [markdown]
# ## Verificar con T-SQL
#
# ```sql
# -- Qué modelo es el campeón y por qué (último evento)
# SELECT TOP 5 secuencia, evento, version, auc_prueba, motivo FROM ab_ml_registro_modelos ORDER BY secuencia DESC;
#
# -- Deriva del último corte
# SELECT variable, psi, deriva FROM ab_ml_monitoreo_deriva WHERE corte = '2026-09' ORDER BY psi DESC;
#
# -- Desempeño real una vez llegan las etiquetas
# SELECT * FROM ab_ml_monitoreo_desempeno;
# ```
