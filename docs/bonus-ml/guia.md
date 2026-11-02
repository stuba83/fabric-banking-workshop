# Bonus — Ciencia de datos y ciclo de vida de ML en Microsoft Fabric

**Audiencia:** Ingenieros de datos y analistas que quieren ver el ciclo completo de machine learning en Fabric, incluido MLOps y las capacidades de IA para ciencia de datos  
**Formato:** Seis módulos de trabajo individual (B1 a B6), cada uno con un notebook importable  
**Dedicación orientativa:** de 45 a 90 minutos por módulo  
**Verificado contra Microsoft Learn:** 30 de octubre de 2026

Este bonus **no forma parte de las cinco sesiones** ni de sus evidencias. Se apoya en lo que construiste en ellas: las tablas plata de la [Sesión 3](../sesion-03/guia.md) y, de forma opcional, el modelo semántico de la [Sesión 4](../sesion-04/guia.md).

## Resultado esperado

Al terminar, cada participante podrá:

1. **Preparar datos para ML sin fuga de datos**, con variables que no crecen con el calendario y una etiqueta calculada solo con el futuro que corresponde.
2. **Entrenar, rastrear y comparar** modelos con MLflow, frente a un *baseline*, y elegir con un criterio explícito.
3. **Registrar una versión** del modelo, **puntuar por lotes** con `PREDICT` y dejar el resultado listo para Power BI.
4. **Operar el ciclo** con una regla de promoción, monitoreo de deriva y desempeño real, y reversión auditable.
5. **Saber qué capacidades de IA existen** en Fabric (funciones de IA, LLM, Copilot, agente de datos), qué requiere cada una y qué **no funciona en una capacidad Trial**.
6. **Llevar un modelo de uso en línea** al ciclo de vida: detectar transacciones atípicas **sin etiquetas**, elegir el algoritmo con experimentos, calcular las mismas variables al entrenar y al servir, puntuar una transacción por el *endpoint* y monitorear sin etiquetas.

## El caso

> Dado el comportamiento de una cuenta hasta el cierre de un mes, ¿tendrá **al menos 9 transacciones** el mes siguiente?

Es una clasificación binaria sobre las tablas plata. Cada fila de la tabla de *features* es **una cuenta en un corte mensual**. La etiqueta mira el mes siguiente.

| Corte | Uso | Etiqueta (actividad de…) | Filas | Positivas |
|---|---|---|---:|---:|
| 2026-05 y 2026-06 | Entrenamiento | junio y julio | 3.600 | 563 + 589 |
| 2026-07 | Validación | agosto | 1.800 | 631 |
| 2026-08 | Prueba (se mide **una vez**) | septiembre | 1.800 | 651 |
| 2026-09 | Puntuación | octubre (aún no existe) | 1.800 | sin etiqueta |

**La división es por tiempo, nunca al azar.** Un modelo no debe ver el futuro con el que se le juzga. Todo modelo se compara con un **baseline** sin aprendizaje (la actividad del mes actual como predictor del siguiente), que con estos datos ya alcanza un AUC cercano a 0,81.

**Lo que enseña el caso.** Con datos sintéticos y una señal sencilla, un modelo simple (regresión logística, AUC ≈ 0,85) casi iguala a uno complejo, y AutoML o el ajuste fino de hiperparámetros apenas mejoran. La conclusión útil es de método: **la complejidad solo se justifica si mejora de forma medible**.

> **Los datos son sintéticos.** Las métricas sirven para practicar el ciclo de vida. No las interpretes como el rendimiento de un modelo real, ni uses estos valores como referencia para otro conjunto de datos.

**Un segundo caso, en B6.** B1 a B4 trabajan con un modelo supervisado que se usa por lotes. El [módulo B6](modulo-6-anomalias-en-linea.md) agrega un modelo de uso **en línea**: detectar transacciones atípicas **sin etiquetas** (una fila por transacción), medido con anomalías **inyectadas** de tres tipos, registrado y servido por lotes y por el *endpoint* del modelo.

## Ruta de los seis módulos

| Módulo | Tema | Guía | Notebook | Trial | Dedicación |
|---|---|---|---|---|---|
| **B1** | Preparar datos: exploración, Data Wrangler, features sin fuga y semantic link | [Guía](modulo-1-preparacion.md) | [B1](../../notebooks/bonus_ml/B1_preparacion_datos.ipynb) | Sí (la IA de Data Wrangler no) | 45–60 min |
| **B2** | Entrenar y comparar con MLflow; AutoML; hiperparámetros; explicabilidad | [Guía](modulo-2-entrenamiento.md) | [B2](../../notebooks/bonus_ml/B2_entrenamiento_mlflow.ipynb) | Sí | 60–75 min |
| **B3** | Registrar el modelo, puntuar por lotes con `PREDICT` y llevarlo a Power BI | [Guía](modulo-3-registro-puntuacion.md) | [B3](../../notebooks/bonus_ml/B3_registro_puntuacion.ipynb) | Sí | 45–60 min |
| **B4** | MLOps: ciclo repetible, compuerta de promoción, monitoreo y reversión | [Guía](modulo-4-mlops.md) | [B4](../../notebooks/bonus_ml/B4_mlops.ipynb) | Sí | 60–90 min |
| **B5** | IA en notebooks: funciones de IA, LLM, Copilot y agente de datos | [Guía](modulo-5-ia.md) | [B5](../../notebooks/bonus_ml/B5_ia_en_notebooks.ipynb) | **No** (requiere F2 o superior) | 20 min de lectura; 45–60 min con capacidad de pago |
| **B6** | Detectar transacciones atípicas sin etiquetas y puntuar en línea con el *endpoint* | [Guía](modulo-6-anomalias-en-linea.md) | [B6](../../notebooks/bonus_ml/B6_anomalias_en_linea.ipynb) | Sí, salvo la llamada al *endpoint* (vista previa) | 60–75 min |

Registra tus resultados en una copia de la [plantilla de evidencias](evidencias.md), conservada dentro de tu organización.

## Mapa de capacidades de Fabric para ciencia de datos

Qué ofrece Fabric hoy, qué estado tiene según Microsoft Learn y si funciona en **Trial**. «No indicado» significa que la página de Learn no lo etiqueta como disponible de forma general ni como vista previa. El detalle y los enlaces están en las [referencias](#referencias).

| Capacidad | Para qué sirve | Estado según Learn | ¿Trial? | Dónde se practica |
|---|---|---|---|---|
| **Notebooks** (Spark y Python) | Explorar, entrenar y orquestar | General | Sí | B1–B6 |
| **Data Wrangler** (pandas y Spark) | Explorar y limpiar con una interfaz visual que **genera código** | No indicado | Sí | B1 |
| ↳ IA en Data Wrangler (*AI enrichments*, Copilot) | Transformaciones descritas en lenguaje natural | Vista previa | **No** (F2+) | B1 y B5 (solo descripción) |
| **Experimentos con MLflow** | Registrar y comparar corridas; *autologging* | No indicado (integración con el hub de monitoreo en vista previa) | Sí | B2 |
| **Modelos de ML** (registro) | Versiones, etiquetas y firma de cada modelo | No indicado | Sí | B3 y B4 |
| **`PREDICT`** y asistente «Apply model» | Puntuación por lotes en Spark, SQL o UDF | No indicado | Sí | B3 y B6 |
| **Endpoints en tiempo real** | Servir una versión de modelo por una API | Vista previa | No indicado (compruébalo en tu tenant) | B3 (descripción) y B6 (llamada real) |
| **Detección de anomalías sin etiquetas** (scikit-learn: `LocalOutlierFactor`, `IsolationForest`) | Marcar lo que se aleja de lo normal, con el umbral guardado dentro del modelo | General (biblioteca del runtime) | Sí | B6 |
| **AutoML** (FLAML, en código) | Probar modelos y configuraciones dentro de un presupuesto | No indicado | Sí | B2 |
| **AutoML de bajo código** | Lo mismo con una interfaz que genera un notebook | No indicado | Sí | Solo referencia |
| **Ajuste de hiperparámetros** (`flaml.tune`) | Buscar el mejor valor de un hiperparámetro | No indicado | Sí | B2 |
| **SynapseML** (LightGBM, OpenAI, ONNX…) | Entrenamiento distribuido y modelos de lenguaje sobre Spark | No indicado | Sí | B2 (opcional) |
| **Semantic link** (`sempy`) | Leer y consultar modelos semánticos de Power BI desde un notebook | No indicado | Sí | B1 |
| **Funciones de IA** (nueve, en pandas y PySpark) | Aplicar un LLM a una columna con una línea | Parcialmente en vista previa | **No** (F2+) | B5 |
| **LLM integrado** (Azure OpenAI, SDK y SynapseML) | Llamar a un modelo de lenguaje sin claves propias | Vista previa | **No** (F2+) | B5 |
| **Copilot en notebooks** | Asistente de código con panel de chat y comandos en celda | Vista previa | **No** (F2+) | B5 (guía de uso) |
| **Agente de datos** | Preguntar en lenguaje natural sobre tus datos | General (partes en vista previa) | **No** (F2+) | B5 (guía de uso) |
| **Environments** | Fijar bibliotecas para ejecuciones reproducibles | General | Sí | B4 (descripción) |
| **Orquestación** (pipelines, `notebookutils`) | Programar y encadenar notebooks con parámetros | General | Sí | B4 |
| **Git y *deployment pipelines*** | Control de versiones y despliegue entre entornos | Notebooks y environments compatibles; **vista previa** para experimentos y modelos (solo metadatos) | Sí | B4 (descripción) |
| **Hub de monitoreo** y **Activator** | Ver ejecuciones y alertar | Hub de experimentos en vista previa | Sí | B4 (descripción) |
| **Linaje** | Ver cómo se conectan los elementos del workspace | General | Sí | Sesión 4 y B4 |

**Lo que Fabric no tiene hoy (según la documentación verificada):**

- **Etapas ni alias de modelo** (por ejemplo, «producción»). Por eso B4 decide el campeón con una **tabla de control** auditable.
- **Monitoreo de deriva o de calidad de modelos.** Solo existen métricas de tráfico del endpoint (solicitudes, fallos, latencia). Por eso B4 mide el **PSI** y el desempeño real con tablas propias, y B6 vigila el PSI y la **tasa de marcadas**, que no necesitan etiquetas.
- **Un almacén de variables (*feature store*) dedicado:** no se encontró en la documentación revisada. B6 muestra la alternativa mínima: **una función compartida** que calcula las variables igual al entrenar y al servir, y una **tabla de referencia** que viaja con el modelo como artefacto.
- **Una arquitectura de referencia de MLOps** en Learn. El nodo «Operationalize with MLOps» solo enlaza la página de Git y *deployment pipelines*.

> **Capacidad Trial frente a capacidad de pago.** La página oficial de la prueba gratuita indica que **Copilot y las experiencias de IA (agente de datos, funciones de IA y servicios de IA) no están soportados** en Trial. Otras páginas de Learn mezclan estos mensajes (algunas dicen «regístrate para la prueba gratuita» como requisito). Ante la duda, **comprueba el botón o la llamada en tu workspace**: B5 lo hace por ti y no falla si no está disponible. Una capacidad de pago pequeña (F2) basta para B5.

## Requisitos

- Sesión 3 completada: las nueve tablas existen en tu Lakehouse con sus conteos medidos. Sesión 4 recomendada, para la reconciliación con semantic link (B1) y el paso a Power BI (B3).
- Un notebook de **PySpark** (no uno de Python puro) con tu Lakehouse como **predeterminado**.
- Runtime de Fabric **1.3 o 2.0**. Según las páginas de runtime de octubre de 2026, el 2.0 es el predeterminado en los workspaces nuevos (así fue en la prueba) y el 1.3 entra en soporte de largo plazo; otras páginas aún lo describen como opcional, así que **confirma cuál usa tu workspace**. Las bibliotecas que usa el bonus (`pandas`, `scikit-learn`, `mlflow`, `flaml`) vienen en el runtime; sus versiones difieren entre runtimes (en el 2.0 de la prueba: pandas 2.3.3, scikit-learn 1.6.1, MLflow 2.22 y FLAML 2.5; en el 1.3 se documenta scikit-learn 1.2.2). **No** vienen preinstalados `nest_asyncio` ni `openai`, que solo necesita B5.
- Licencia Power BI Pro para el paso de Power BI de B3, igual que en la Sesión 4.
- **Capacidad F2 o superior** solo para B5 (y la IA de Data Wrangler).

Las [reglas del laboratorio](../requisitos.md) siguen vigentes: datos sintéticos, tu carpeta y tu prefijo, sin conexión a producción.

## Importar y ejecutar los notebooks

1. Descarga cada `.ipynb` desde el repositorio (el archivo, no la página HTML de GitHub).
2. En Fabric, usa **Import notebook**, renómbralo con tu prefijo (por ejemplo, `AB_NB_B1`) y colócalo en tu carpeta.
3. Elige **PySpark (Python)**, adjunta **solo** tu Lakehouse y márcalo como predeterminado.
4. Fija los parámetros de la primera celda de código (la celda de parámetros) y ejecuta las celdas **en orden**.

| Parámetro | Notebooks | Valor del ejemplo | Significado |
|---|---|---|---|
| `p_lakehouse_esperado` | Todos | `AB_Lakehouse` | Nombre de tu Lakehouse; el notebook se detiene si no coincide |
| `p_prefijo` | Todos | `AB` | Tu prefijo; las tablas nuevas lo usan en minúsculas |
| `p_confirmar_reemplazo` | B1, B3, B4, B6 | `SI` | Autoriza escribir tablas y registrar versiones. Con `NO`, B1 solo explora |
| `p_modelo_semantico` | B1 | `AB_SM_Transacciones` | Opcional: tu modelo de la Sesión 4, para la reconciliación |
| `p_presupuesto_automl_s` | B2 | `30` | Segundos de AutoML |
| `p_tipo_modelo` | B3, B4 | `logreg` | `logreg`, `rf` o `hgb` |
| `p_modo`, `p_corte_puntuacion`, `p_factor_deriva` | B4 | `guiado`, `2026-09`, `0.0` | `guiado` recorre seis escenarios; `ciclo` ejecuta uno y es el que se programa |
| `p_runtime_2_0` | B5 | `SI` | `NO` si tu runtime es 1.3 |
| `p_tasa_revision` | B6 | `0.01` | Capacidad de revisión: fracción de transacciones que se puede revisar a mano; fija el umbral de validación |
| `p_probar_endpoint` | B6 | `SI` | `NO` omite la llamada al *endpoint*; con `SI` solo se llama si hay una versión activa (nunca activa una) |

**Tablas que crea el bonus** (con el prefijo en minúsculas): `ab_gold_ml_features_cuentas` (B1), `ab_gold_ml_puntuacion_actividad` (B3 y B4), `ab_ml_registro_modelos`, `ab_ml_monitoreo_deriva` y `ab_ml_monitoreo_desempeno` (B4), y `ab_gold_ml_referencia_tx` y `ab_gold_ml_anomalias_tx` (B6). También se crean los experimentos `ab_exp_actividad` y `ab_exp_anomalias_tx` y los modelos `ab_modelo_actividad` y `ab_modelo_anomalias_tx`. **Las escrituras reemplazan solo las tablas con tu prefijo.**

## Controles esperados

Mide estos valores tú mismo y regístralos en las evidencias. Los **conteos** son exactos; las **métricas** son aproximadas, porque dependen de la versión de las bibliotecas del runtime.

| Control | Valor esperado | Tipo |
|---|---:|---|
| Filas de la tabla de features | 9.000 (1.800 por corte × 5) | Exacto |
| Positivas por corte (mayo a agosto) | 563, 589, 631, 651 | Exacto |
| Septiembre | Sin etiqueta | Exacto |
| Baseline, AUC de validación | ≈ 0,81 | Aproximado |
| Modelos (`logreg`, `rf`, `hgb`), AUC de validación | ≈ 0,84 a 0,86 | Aproximado |
| Modelo elegido, AUC de prueba | ≈ 0,83 a 0,85 | Aproximado |
| Filas de `ab_gold_ml_puntuacion_actividad` tras B3 | 1.800 (una versión de modelo) | Exacto |
| Deriva con datos reales (septiembre frente al entrenamiento) | Todas las variables `estable` | Aproximado |
| Deriva con la campaña simulada (factor 1,6) | Al menos 4 variables `alta`; recomendación `revisar` | Aproximado |
| Reejecución del ciclo con los mismos datos | Mismas filas y ninguna versión nueva | Exacto |
| B6: filas con variables (al menos 10 transacciones previas) | 54.526 | Exacto |
| B6: entrenamiento (mayo a julio) / validación / prueba | 28.743 / 12.231 / 12.800 | Exacto |
| B6: anomalías inyectadas en agosto y en septiembre | 125 y 130 | Exacto |
| B6: filas de `ab_gold_ml_referencia_tx` y de `ab_gold_ml_anomalias_tx` | 9 y 12.800 (una versión de modelo) | Exacto |
| B6: modelo elegido, AUC y AP de prueba | `lof`; AUC ≈ 0,98, AP ≈ 0,5–0,6 (`iforest`: AP de validación ≈ 0,1) | Aproximado |
| B6: tasa de marcadas en septiembre / con montos +60 % | ≈ 1 % / más de 2,5 veces esa tasa; PSI de `z_monto_tipo` `alta` | Aproximado |

## Uso responsable y límites

- **No uses estas métricas fuera del laboratorio.** Son de datos sintéticos.
- **Atributos sensibles.** `grupo_edad` y `provincia` **no entran al modelo**; se usan solo para auditar si el desempeño cambia entre grupos. En un caso real, decidir qué atributos usar (y cuáles auditar) es una decisión de negocio y de cumplimiento, no solo técnica.
- **Datos hacia un LLM.** No envíes datos personales o confidenciales a un modelo sin la aprobación de tu organización.
- **Revisa lo que genera una IA.** El código de Copilot, las respuestas de un LLM y las transformaciones de Data Wrangler con IA se **revisan** antes de usarse.
- **Lo que no cubre.** No hay ciencia de datos con aprendizaje profundo, series de tiempo ni sistemas de recomendación; no hay despliegue automático; y no se versionan los datos de entrenamiento.

## Estado de verificación

- **Verificado en un tenant de Fabric** (30 de octubre de 2026; capacidad F8 de pago; workspace nuevo con runtime 2.0, Python 3.13, pandas 2.3.3, scikit-learn 1.6.1, MLflow 2.22 y FLAML 2.5): las **Sesiones 2 y 3** y los notebooks **B1 a B5** se ejecutaron de principio a fin lanzándolos por API con parámetros. Los conteos de las Sesiones 2 y 3 coincidieron exactamente con los de las guías, la hora de `fecha_hora` se conservó sin cambios, `PREDICT` coincidió con pandas en las 1.800 cuentas, el AUC real del mes anterior fue 0,8466 (el mismo valor que en las pruebas locales) y las funciones de IA y el LLM desde código respondieron en español.
- **B6 verificado en un tenant de Fabric** (2 de noviembre de 2026; capacidad F8 de pago; runtime 2.0, Python 3.13, pandas 2.3.3, scikit-learn 1.6.1 y MLflow 2.22): el notebook se ejecutó de principio a fin por API, en unos 2,5 a 3 minutos. Los conteos coincidieron con los de la guía (130 anomalías inyectadas en septiembre, 12.800 transacciones puntuadas) y las métricas con las de las pruebas locales (por ejemplo, `lof` con 200 vecinos: AUC de validación 0,979 y AP 0,625; AUC de prueba 0,986). La comprobación de `PREDICT` contra pandas (acuerdo 1,0) forma parte del notebook y no falló. Se activó el *endpoint* de una versión **por API** (de 5 a 6 minutos en dos pruebas) y desde un notebook de Fabric, con `FabricRestClient` de semantic link, se puntuaron dos transacciones: la respuesta coincidió con la del modelo local (primera llamada de unos 2 segundos, incluida la red). **No se probó la activación desde la interfaz.**
- **Verificado localmente** (Python 3.14, pandas 3.x, scikit-learn 1.9, MLflow 3.17, FLAML 2.7, con Spark y las APIs de IA simuladas): el módulo de funciones, el ciclo MLOps completo con MLflow real (promoción, reejecución idempotente, reversión, deriva y desempeño), el módulo de transacciones atípicas (variables, inyección, umbral, solicitudes), las celdas de B1 a B6 y los controles de esta guía, que las pruebas comprueban contra el dataset.
- **No verificado en un tenant de Fabric:** los pasos que dependen de la **interfaz** (Data Wrangler, el asistente de la versión, la activación del *endpoint* y **Preview predictions**, Copilot y el agente de datos), la reconciliación de semantic link **contra un modelo semántico real** (solo se comprobó que la biblioteca importa y responde), el comportamiento de la celda `%pip` en una sesión **interactiva** y el comportamiento en una capacidad **Trial** (la prueba usó una capacidad de pago). Hazlo **primero tú, como prueba de humo**, y registra lo que cambie. Si algo difiere, abre una incidencia **sin datos de tu organización**.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `expected an existing table` o `expected row count` al inicio de B1 | Que la Sesión 3 terminó bien y el prefijo es el mismo; las tablas plata deben medir 72.000, 1.800 y 1.200 filas |
| `p_confirmar_reemplazo must be exactly 'SI'` | Es lo esperado hasta que fijes `SI` para escribir o registrar |
| `No module named 'flaml'` o falta otra biblioteca | El runtime o el Environment adjunto; instala en un **Environment** (no con `%pip` en una ejecución de pipeline) |
| `ModuleNotFoundError: synapse.ml.predict` o `sempy` | Que el notebook sea de **PySpark** y que el runtime sea el de Fabric, no uno local |
| `PREDICT` falla o devuelve otro resultado | Que el modelo tenga **firma** y sea un sabor soportado; que el modelo no venga de AutoML con `use_spark=True` |
| Las funciones de IA fallan con `RuntimeError: This event loop is already running` | No es la capacidad: en el runtime 2.0 falta `nest_asyncio` (y `openai` para el LLM desde código). Instálalos con la celda `%pip` de B5 o en un Environment |
| Las funciones de IA fallan con otro error | Capacidad **Trial** o ajustes de inquilino de Copilot y Azure OpenAI; B5 lo detecta y omite las celdas |
| `System_Cancelled_Session_Statements_Failed` al ejecutar B5 por API o pipeline | La celda `%pip` solo funciona en una sesión **interactiva**; para ejecuciones automáticas, instala las bibliotecas en un **Environment** |
| El ciclo de B4 falla con `expected a champion model` | El retador se rechazó por debajo del piso de calidad y no hay campeón previo; revisa los datos de B1 |
| El reporte o el modelo semántico no cuadran con el notebook | Reconcilia con semantic link (B1) y revisa las relaciones de la Sesión 4 |
| La ejecución es lenta | Capacidad compartida, sesiones activas y el tiempo de AutoML; reduce `p_presupuesto_automl_s` |

Un bloqueo de identidad, licencia o capacidad no se resuelve en el notebook: coordínalo con el administrador del laboratorio.

## Referencias

**Ciencia de datos en Fabric**

- [Data Wrangler](https://learn.microsoft.com/en-us/fabric/data-science/data-wrangler) y [Data Wrangler en Spark](https://learn.microsoft.com/en-us/fabric/data-science/data-wrangler-spark).
- [Experimentos de ML y MLflow](https://learn.microsoft.com/en-us/fabric/data-science/machine-learning-experiment), [autologging](https://learn.microsoft.com/en-us/fabric/data-science/mlflow-autologging) y [modelos de ML](https://learn.microsoft.com/en-us/fabric/data-science/machine-learning-model).
- [Puntuación con PREDICT](https://learn.microsoft.com/en-us/fabric/data-science/model-scoring-predict) y [endpoints de modelos](https://learn.microsoft.com/en-us/fabric/data-science/model-endpoints).
- [AutoML en código](https://learn.microsoft.com/en-us/fabric/data-science/how-to-use-automated-machine-learning-fabric), [AutoML de bajo código](https://learn.microsoft.com/en-us/fabric/data-science/low-code-automl) y [ajuste de hiperparámetros](https://learn.microsoft.com/en-us/fabric/data-science/hyperparameter-tuning-fabric).
- [Semantic link](https://learn.microsoft.com/en-us/fabric/data-science/semantic-link-overview) y su [referencia de la API](https://learn.microsoft.com/en-us/python/api/semantic-link-sempy/sempy.fabric?view=semantic-link-python).
- [SynapseML](https://microsoft.github.io/SynapseML/).

**IA generativa**

- [Funciones de IA](https://learn.microsoft.com/en-us/fabric/data-science/ai-functions/overview), su [configuración con pandas](https://learn.microsoft.com/en-us/fabric/data-science/ai-functions/pandas/configuration) y los [ajustes temporales del runtime 2.0](https://learn.microsoft.com/en-us/fabric/data-science/ai-functions/runtime-2-0-workarounds).
- [Servicios de IA en Fabric](https://learn.microsoft.com/en-us/fabric/data-science/ai-services/ai-services-overview).
- [Copilot en notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/copilot-notebooks-overview) y su [panel de chat](https://learn.microsoft.com/en-us/fabric/data-engineering/copilot-notebooks-chat-pane).
- [Agente de datos](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent).

**Operación**

- [Git y *deployment pipelines* para elementos de ML](https://learn.microsoft.com/en-us/fabric/data-science/machine-learning-artifacts-git-deployment-pipelines) y [registro entre workspaces](https://learn.microsoft.com/en-us/fabric/data-science/machine-learning-cross-workspace-logging).
- [Actividad de notebook en un pipeline](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity) y [`notebookutils.notebook.run`](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run).
- [Hub de monitoreo](https://learn.microsoft.com/en-us/fabric/admin/monitoring-hub) y [linaje de ciencia de datos](https://learn.microsoft.com/en-us/fabric/data-science/data-science-lineage).
- [Prueba gratuita de Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial) y [runtimes](https://learn.microsoft.com/en-us/fabric/data-engineering/runtime).

Este repositorio no es documentación oficial de Microsoft. Las capacidades y su estado cambian: si una página de Learn contradice esta guía, **manda Learn**.
