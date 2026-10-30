# %% [markdown]
# # Bonus B5 — IA en los notebooks: funciones de IA, LLM, Copilot y agente de datos
#
# **Objetivo.** Conocer las capacidades de **IA generativa** de Fabric para ciencia de datos y usarlas con criterio: **funciones de IA** sobre columnas de texto, un **LLM** desde el código, **Copilot** como asistente del notebook y el **agente de datos** para preguntar en lenguaje natural.
#
# > **Capacidad requerida.** Estas funciones **no están soportadas en una capacidad Trial**: requieren una capacidad de pago **F2 o superior** (o P), el ajuste de inquilino *Users can use Copilot and other features powered by Azure OpenAI* y, según la región, el procesamiento entre geografías. Con Trial, este notebook **no falla**: la comprobación de la sección 2 lo detecta y las celdas de IA se omiten. En ese caso, el facilitador lo demuestra desde un ambiente con capacidad de pago y las secciones de Copilot y del agente (solo texto) siguen siendo útiles como guía.
#
# | Capacidad | Estado | Trial | Qué necesita |
# |---|---|---|---|
# | **Funciones de IA** (pandas y PySpark) | Vista previa parcial | No | F2+ y ajustes de inquilino; runtime 1.3 o superior |
# | **LLM desde código** (SDK de OpenAI, SynapseML) | Vista previa | No | Igual que arriba |
# | **Copilot en notebooks** | Vista previa | No | F2+; panel de chat y comandos en celda |
# | **Agente de datos** | Disponible | No | F2+, misma región que los datos |
# | **Data Wrangler con IA** | Vista previa | No | F2+ (el resto de Data Wrangler sí funciona en Trial) |
# | **Semantic link, MLflow, AutoML, PREDICT** | — | **Sí** | Ver B1–B4 |
#
# **Datos.** Solo se usan comentarios **sintéticos** inventados para este ejercicio. **No envíes datos reales de clientes a un modelo** sin la aprobación de tu organización. Las funciones de IA no registran ni almacenan tus *prompts*, entradas ni salidas, pero la revisión de datos sensibles sigue siendo tu responsabilidad.
#
# **Costo.** Cada llamada consume capacidad (medidor «Copilot y AI»). `aifunc.default_conf.progress_bar_mode = "stats"` muestra los tokens y las CU consumidas.

# %% parameters
p_lakehouse_esperado = ''
p_prefijo = ''
p_runtime_2_0 = 'SI'

# %% embed ml_actividad.py

# %% [markdown]
# ## 1. Configuración según el runtime
#
# - **Runtime 1.3:** sin instalación para la mayoría de los usos.
# - **Runtime 2.0 (Spark 4.1):** hay un ajuste **temporal** documentado: instalar `nest_asyncio` en una celda aparte (reinicia Python) y fijar unos valores del modelo. Si tu runtime es 1.3, deja `p_runtime_2_0 = 'NO'`.
# - En ejecuciones de **pipeline o programadas**, no uses `%pip`: agrega `nest-asyncio` a un **Environment** y publícalo.

# %%
%pip install -q nest_asyncio 2>/dev/null

# %%
import notebookutils

validar_parametros_ml(
    notebookutils.runtime.context, p_lakehouse_esperado, p_prefijo, "NO", exigir_confirmacion=False,
)
nombres = nombres_ml(p_prefijo)

# %% [markdown]
# ## 2. Comprobar que la capacidad lo permite
#
# Una llamada mínima. Si falla, no es un error del notebook: la capacidad o el inquilino no tienen habilitadas las funciones de IA.

# %%
import pandas as pd
import synapse.ml.aifunc as aifunc

aifunc.default_conf.model_deployment_name = "gpt-5-mini"
aifunc.default_conf.reasoning_effort = "low"
if p_runtime_2_0 == "SI":
    aifunc.default_conf.temperature = None  # ajuste temporal documentado para el runtime 2.0
aifunc.default_conf.progress_bar_mode = "stats"


def probar_ia():
    try:
        resultado = pd.Series(["Excelente servicio, muchas gracias."]).ai.analyze_sentiment()
        return True, str(resultado.iloc[0])
    except Exception as error:  # capacidad Trial, ajustes de inquilino o región
        return False, f"{type(error).__name__}: {error}"


ia_disponible, detalle = probar_ia()
print("Funciones de IA disponibles:" if ia_disponible else "Funciones de IA NO disponibles:", detalle)
if not ia_disponible:
    print("Se omiten las celdas de IA. Requiere capacidad F2 o superior y los ajustes de inquilino de Copilot y Azure OpenAI.")

# %% [markdown]
# ## 3. Funciones de IA sobre texto
#
# Las **funciones de IA** aplican un modelo de lenguaje a una columna con **una línea de código**, sin armar *prompts* ni llamar a una API. Existen nueve: `analyze_sentiment`, `classify`, `extract`, `fix_grammar`, `generate_response`, `similarity`, `summarize`, `translate` y `embed`. Funcionan con **pandas** (`df["col"].ai.…`) y con **PySpark** (`df.ai.…(input_col=…, output_col=…)`, otro módulo: `synapse.ml.spark.aifunc`).
#
# Aquí se usan comentarios **sintéticos** de clientes. Aviso de la documentación: la mayoría de las funciones están **optimizadas para texto en inglés**; en español suelen funcionar bien, pero **valida los resultados**.

# %%
comentarios = pd.DataFrame({"comentario": [
    "La app móvil se cierra sola cada vez que intento transferir dinero. Muy frustrante.",
    "Me atendieron rápido en la sucursal y resolvieron mi duda sobre la tarjeta en pocos minutos.",
    "No entiendo por qué me cobraron una comisión por retirar en el cajero si mi cuenta es de ahorro.",
    "La nueva función de pago de servicios en la web es muy cómoda. Gracias.",
    "Llevo tres días esperando que me desbloqueen la tarjeta y nadie me llama.",
    "El cajero automático de la esquina estuvo sin efectivo el fin de semana completo.",
    "Me gustó que la app muestre mis gastos por categoría, aunque a veces tarda en cargar.",
    "Quiero reportar un cargo desconocido de 45.000 colones del lunes pasado en mi tarjeta.",
    "El chat de ayuda respondió muy bien y en un español claro. Excelente.",
    "La fila en la sucursal de Cartago fue de más de una hora un viernes por la tarde.",
    "No pude cambiar mi PIN desde la web; el mensaje de error no explica qué hacer.",
    "Pagué mi préstamo y el saldo todavía aparece pendiente en la app.",
]})
print(len(comentarios), "comentarios sintéticos")

# %% [markdown]
# **Sentimiento, tema y entidades.** `analyze_sentiment` devuelve `positive`, `negative`, `neutral` o `mixed` (o tus propias etiquetas). `classify` asigna **una** de las etiquetas que le des (conviene dar al menos dos). `extract` devuelve un **DataFrame** con una columna por entidad pedida.

# %%
if ia_disponible:
    comentarios["sentimiento"] = comentarios["comentario"].ai.analyze_sentiment()
    comentarios["tema"] = comentarios["comentario"].ai.classify(
        "tarjeta", "app o web", "sucursal", "cajero", "comisiones", "otro"
    )
    entidades = comentarios["comentario"].ai.extract("producto", "monto", "ciudad")
    comentarios = pd.concat([comentarios, entidades], axis=1)
    display(comentarios)

# %% [markdown]
# **Resumir, traducir, corregir y comparar.** `summarize` acepta `instructions` (tono, longitud, audiencia). `translate` recibe el idioma de destino (probado en diez idiomas, entre ellos español e inglés). `similarity` devuelve una puntuación relativa de **-1 a 1** (sirve para **ordenar**, no como probabilidad) y, como `embed`, **no está soportada si usas tu propio recurso de Foundry**.

# %%
if ia_disponible:
    resumen = pd.DataFrame({
        "resumen": comentarios["comentario"].ai.summarize(instructions="Una frase de máximo 12 palabras."),
        "ingles": comentarios["comentario"].ai.translate("english"),
        "parecido_a_tarjeta_bloqueada": comentarios["comentario"].ai.similarity("tarjeta bloqueada sin respuesta"),
    })
    display(pd.concat([comentarios[["comentario"]], resumen], axis=1).sort_values(
        "parecido_a_tarjeta_bloqueada", ascending=False
    ).head(6))

# %% [markdown]
# ## 4. `generate_response`: explicar una predicción del modelo
#
# `generate_response` aplica un *prompt* a cada fila. Con `is_prompt_template=True` solo se usan las columnas entre llaves. Aquí se pide una **explicación en lenguaje claro** de por qué el modelo de B3 marcó una cuenta, a partir de sus variables. Es un buen uso de un LLM: **redactar**; la decisión la tomó el modelo, no el LLM.
#
# **Buenas prácticas:** pídele que use **solo** los datos de la fila, sin inventar; revisa una muestra; y recuerda que esta explicación **no es la causa real** de la predicción (para eso está la importancia por permutación de B2).

# %%
if ia_disponible:
    puntuacion = leer_tabla(spark, nombres["puntuacion"], opcional=True)
    features = leer_tabla(spark, nombres["features"], opcional=True)
    if puntuacion is None or features is None:
        print("Faltan las tablas de B1 y B3: se omite la explicación de predicciones.")
    else:
        top = (
            puntuacion.sort_values("probabilidad_alta_actividad", ascending=False).head(5)
            .merge(features[[CLAVE, CORTE, "tx_mes_corte", "tx_mes_previo", "pct_banca_movil"]], on=[CLAVE, CORTE])
        )
        top["explicacion"] = top.ai.generate_response(
            prompt=(
                "Eres analista de datos. En dos frases en español, explica a un gerente por qué la cuenta {cuenta_id} "
                "se marcó con probabilidad {probabilidad_alta_actividad} de tener alta actividad el mes siguiente. "
                "Usa solo estos datos: transacciones del mes {tx_mes_corte}, del mes previo {tx_mes_previo} y "
                "proporción de banca móvil {pct_banca_movil}. No inventes información."
            ),
            is_prompt_template=True,
        )
        display(top[[CLAVE, "probabilidad_alta_actividad", "explicacion"]])

# %% [markdown]
# ## 5. Un LLM desde el código
#
# Para casos que las funciones de IA no cubren, Fabric ofrece los modelos **Azure OpenAI integrados** (por ejemplo `gpt-5.1` y `gpt-5-mini`, y `text-embedding-ada-002`) **sin claves ni recursos propios**. Dos caminos:
#
# - **Cliente del SDK de OpenAI**, ya autenticado: `aifunc.session.client_sync` (y `client_async`). Se usa la API de *respuestas*; `store=True` y `previous_response_id` no están soportados.
# - **SynapseML**, para Spark: `OpenAIPrompt`, `OpenAIEmbedding`, `OpenAIChatCompletion` y `OpenAIResponses` en `synapse.ml.services.openai` (runtime 1.3 o superior, vista previa). Úsalo cuando el volumen pida procesar en paralelo.

# %%
if ia_disponible:
    cliente = aifunc.session.client_sync
    respuesta = cliente.responses.create(
        model="gpt-5-mini",
        input=(
            "En tres viñetas, ¿qué riesgos hay al usar variables acumuladas en el monitoreo de deriva "
            "de un modelo? Responde en español."
        ),
        store=False,
    )
    print(getattr(respuesta, "output_text", respuesta))

# %% [markdown]
# **Tu propio modelo o recurso.** Si tu organización ya tiene un recurso de Microsoft Foundry (Azure OpenAI) o una puerta de enlace APIM, las funciones de IA pueden usarlo con `aifunc.setup(cliente)`, con un `OpenAI(base_url="https://<recurso>.openai.azure.com/openai/v1", api_key=...)`. **Nunca pegues la clave en el notebook**: léela de **Azure Key Vault**. La documentación de Learn no confirma si esta opción funciona en una capacidad Trial; compruébalo en tu tenant. Las funciones basadas en *embeddings* (`embed`, `similarity`) no se soportan con un recurso propio.

# %% [markdown]
# ## 6. Copilot en notebooks
#
# **Copilot** es el asistente del notebook (vista previa). Conoce el contexto: el Lakehouse adjunto, sus esquemas y tablas, el código existente, los DataFrames cargados y el estado de ejecución. Funciona de dos maneras:
#
# | Modo | Para qué sirve |
# |---|---|
# | **Panel de chat** (botón **Copilot** de la cinta) | Flujos de varios pasos: generar y refactorizar código **en varias celdas**, explorar datos, resumir el notebook. Los cambios se revisan con una **vista de diferencias** |
# | **Copilot en la celda** | Mejoras puntuales: generar código, `/explain`, `/fix`, `/comments`, `/optimize` |
# | **Fix with Copilot** | Aparece bajo una celda que falló: resumen del error, causa probable y corrección propuesta |
# | **Sugerencias de código en línea** | Vista previa, solo Python y consumen CU adicionales |
#
# **Control.** Por defecto Copilot **pide permiso** para editar código o ejecutar celdas: puedes *Permitir*, *Permitir y aprobar automáticamente* acciones similares, u *Omitir*. Después puedes *Conservar* o *Deshacer*, y abrir la **vista de diferencias**. Mantén la aprobación activa.
#
# **Límites documentados.** Con **Private Link** el panel de chat no funciona. El contexto está optimizado para escenarios de **Lakehouse**: si trabajas con otra fuente, nómbrala en el *prompt*. En bibliotecas muy nuevas puede inventar sintaxis. Los datos del cliente se procesan temporalmente para detectar usos dañinos.
#
# ### Biblioteca de *prompts* para el ciclo de ML
#
# Úsalos como punto de partida y **revisa siempre lo que genera**.
#
# | Etapa | *Prompt* |
# |---|---|
# | Explorar | «Perfila la tabla `ab_gold_ml_features_cuentas`: columnas, nulos, duplicados y distribución de `alta_actividad_siguiente` por `corte`» |
# | Features | «Crea, a partir de `ab_silver_transacciones`, el porcentaje de movimientos de fin de semana por cuenta en una ventana de dos meses» |
# | Entrenar | «Entrena una regresión logística y un bosque aleatorio con una división temporal (entrenamiento hasta junio, validación julio) y registra cada corrida en MLflow» |
# | Evaluar | «Revisa este notebook y dime si hay fuga de datos entre las variables y la etiqueta» |
# | Explicar | «Explica qué mide el PSI y qué significa un valor de 0,3 en la variable `tx_ventana`» |
# | Depurar | `/fix` sobre la celda que falla, o **Fix with Copilot** |
# | Documentar | `/comments` y «Agrega una explicación en Markdown de cada paso» |
# | Optimizar | `/optimize`: «¿Esta unión provoca un *shuffle* innecesario?» |
#
# **Práctica (con capacidad F2+).** 1) Abre el panel con este notebook y un Lakehouse adjunto. 2) Usa los *prompts* de *Explorar* y *Evaluar*. 3) Aprueba un cambio y revisa la **vista de diferencias** antes de conservarlo. 4) Compara lo que Copilot propone con tu código de B1: ¿qué haría distinto?
#
# Copilot también puede **leer modelos semánticos de Power BI** mediante semantic link.

# %% [markdown]
# ## 7. Agente de datos de Fabric
#
# Un **agente de datos** permite **preguntar en lenguaje natural** sobre tus datos (por ejemplo, tablas de un Lakehouse) y obtiene la respuesta generando y ejecutando consultas. Está disponible de forma general (el SDK de Python, el servidor MCP y el consumo desde Foundry siguen en vista previa). Requiere capacidad **F2 o superior**, los ajustes de inquilino de Copilot y Azure OpenAI, y que los datos y el agente estén en la **misma región** de capacidad.
#
# **Cómo se prepara (resumen).** Crea el agente en el workspace, **agrega una fuente de datos** (un Lakehouse) y **selecciona las tablas** que podrá usar (aquí, las tablas plata, `ab_gold_ml_features_cuentas` y `ab_gold_ml_puntuacion_actividad`). Después define **instrucciones** (cómo entender el negocio, qué significa «alta actividad», qué tablas preferir) y agrega **ejemplos de preguntas y consultas** que lo guíen. Pruébalo y mide la calidad con un conjunto fijo de preguntas.
#
# **Preguntas de ejemplo.** «¿Cuántas cuentas se marcaron como de alta actividad en septiembre?», «¿Cuál es la transacción promedio por canal?», «¿Qué versión del modelo hizo las últimas predicciones?».
#
# **Gobierno.** El agente respeta los permisos de quien pregunta sobre las fuentes; verifica que la **seguridad por filas** de la Sesión 4 aplique a lo que expone. Se integra con **Git** y con los *deployment pipelines*. Revisa sus respuestas igual que las de cualquier otro modelo.

# %% [markdown]
# ## 8. Uso responsable
#
# - **Valida los resultados.** Un LLM puede equivocarse con total seguridad. Compara una muestra con la realidad antes de confiar.
# - **Datos.** No envíes datos personales o confidenciales sin aprobación. Las funciones de IA no almacenan tus *prompts* ni salidas, pero la política de tu organización manda.
# - **Determinismo.** Para reproducibilidad fija `seed` y `temperature` donde el modelo lo permita; los modelos de razonamiento (`gpt-5`) solo admiten el valor por defecto de `temperature`.
# - **Costo.** Empieza con muestras pequeñas, usa `progress_bar_mode = "stats"` y revisa el consumo de CU en la aplicación de métricas de la capacidad.
# - **Rol de la IA.** Aquí el LLM **redacta, resume y clasifica texto**; las decisiones sobre cuentas las toma un modelo medido, auditado y monitoreado (B2–B4).
#
# ## Qué sigue
#
# Completa las evidencias del bonus y revisa las **Referencias** de la guía para profundizar en cada capacidad.
