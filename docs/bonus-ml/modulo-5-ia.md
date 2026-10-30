# Módulo B5 — IA en los notebooks

**Notebook:** [B5_ia_en_notebooks.ipynb](../../notebooks/bonus_ml/B5_ia_en_notebooks.ipynb)  
**Dedicación orientativa:** 20 minutos de lectura; 45–60 minutos con capacidad de pago  
**Capacidad:** **no funciona en Trial.** Requiere F2 o superior (o P)  
**Guía general:** [Bonus de ciencia de datos](guia.md)

## Objetivo

Conocer las capacidades de **IA generativa** de Fabric para ciencia de datos y usarlas con criterio: **funciones de IA** sobre columnas de texto, un **LLM** desde el código, **Copilot** como asistente del notebook y el **agente de datos** para preguntar en lenguaje natural.

## Qué requiere cada capacidad

| Capacidad | Estado | Trial | Requisitos |
|---|---|---|---|
| Funciones de IA (pandas y PySpark) | Parcialmente en vista previa | **No** | F2+; ajuste de inquilino de Copilot y Azure OpenAI; runtime 1.3 o superior |
| LLM desde el código (SDK de OpenAI, SynapseML) | Vista previa | **No** | Igual que arriba |
| Copilot en notebooks | Vista previa | **No** | F2+; mismos ajustes; el panel de chat no funciona con Private Link |
| Agente de datos | General (SDK, MCP y consumo desde Foundry en vista previa) | **No** | F2+; datos y agente en la **misma región** de capacidad |
| IA de Data Wrangler | Vista previa | **No** | F2+ |

Si tu región queda fuera de EE. UU. y la UE, el administrador puede necesitar habilitar el **procesamiento entre geografías**. Cada llamada consume capacidad (medidor «Copilot y AI»).

**¿Y si solo tienes Trial?** El notebook **no falla**: la sección 2 detecta que las funciones de IA no están disponibles y omite las celdas de IA. Las secciones de Copilot y del agente de datos son texto y sirven de guía. La demostración la hace el facilitador desde un ambiente con capacidad de pago (una SKU pequeña basta).

## Qué hace cada sección

| Sección | Contenido |
|---|---|
| 1. Configuración | Instala `nest_asyncio` (ajuste temporal del runtime 2.0) y `openai` con una celda `%pip`, **solo en sesiones interactivas**; en pipelines, usa un Environment |
| 2. Comprobar la capacidad | Una llamada mínima; si falla, el mensaje distingue «falta `nest_asyncio`» de «la capacidad no lo permite» |
| 3. Funciones de IA | `analyze_sentiment`, `classify`, `extract`, `summarize`, `translate` y `similarity` sobre 12 comentarios **sintéticos** |
| 4. `generate_response` | Redactar una explicación en lenguaje claro de por qué el modelo de B3 marcó una cuenta; un *prompt* ambiguo produce explicaciones confusas |
| 5. LLM desde el código | `openai.AzureOpenAI` con el cliente HTTP de Fabric, sin clave; SynapseML para volúmenes grandes; recurso propio con `aifunc.setup` |
| 6. Copilot | Panel de chat, comandos en celda y una **biblioteca de *prompts*** para el ciclo de ML |
| 7. Agente de datos | Cómo se prepara y qué preguntar |
| 8. Uso responsable | Validación, datos, determinismo, costo y el papel de la IA |

Las nueve funciones de IA son `analyze_sentiment`, `classify`, `embed`, `extract`, `fix_grammar`, `generate_response`, `similarity`, `summarize` y `translate`. Existen versiones para pandas (`df["col"].ai.…`) y para PySpark (`df.ai.…(input_col=…, output_col=…)`).

## Práctica con capacidad de pago

1. Ejecuta el notebook completo y revisa cada columna que produce una función de IA. **Compara una muestra con la realidad**: ¿la etiqueta de sentimiento y el tema son correctos? ¿`extract` encontró el monto y el producto?
2. Abre el **panel de Copilot** con este notebook y tu Lakehouse adjunto. Usa los *prompts* de **Explorar** y **Evaluar** de la biblioteca. **Aprueba** un cambio y revisa la **vista de diferencias** antes de conservarlo.
3. Prueba `/explain`, `/fix` o `/optimize` sobre una celda de B1 o B2.
4. (Opcional) Crea un **agente de datos** sobre tu Lakehouse, agrega instrucciones y ejemplos, y mide cuántas de diez preguntas responde bien.

## Lo que debes tener en cuenta

- **Los datos de B5 son sintéticos.** No envíes datos reales de clientes a un modelo sin la aprobación de tu organización.
- **El LLM redacta; no decide.** La decisión sobre las cuentas la toma un modelo medido, auditado y monitoreado (B2–B4). Una explicación generada **no es la causa real** de una predicción.
- **Revisa lo que genera una IA**, sea código de Copilot o una respuesta.
- **Idioma.** La documentación indica que la mayoría de las funciones están optimizadas para texto en inglés; en español **valida los resultados**.
- **Recurso propio.** Se puede usar tu propio recurso de Microsoft Foundry con `aifunc.setup`; las funciones basadas en *embeddings* (`embed`, `similarity`) no se soportan así. Lee la clave de Azure Key Vault; **nunca la pegues en el notebook**. Learn no confirma si esto funciona en Trial.

## Qué documentar en las evidencias

- Si tu capacidad permitió las funciones de IA, y el mensaje que viste si no.
- Para tres comentarios, la salida de las funciones y tu valoración de si era correcta.
- Qué *prompts* de Copilot probaste, qué cambió y qué rechazaste o corregiste.
- Una regla de uso responsable que aplicarías en tu equipo.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `Funciones de IA NO disponibles: RuntimeError: This event loop is already running` | **No es la capacidad.** En el runtime 2.0 falta `nest_asyncio`: ejecuta la celda `%pip` de la sección 1 (o agrégalo a un Environment) |
| `Funciones de IA NO disponibles` con otro error | Capacidad **Trial**, ajuste de inquilino de Copilot y Azure OpenAI, o región; coordina con el administrador |
| La sesión se cancela con `System_Cancelled_Session_Statements_Failed` al ejecutar por API o pipeline | La celda `%pip` no funciona fuera de una sesión interactiva; instala `nest-asyncio` y `openai` en un **Environment** |
| `No module named 'openai'` | Tampoco viene en el runtime 2.0; instálalo con la celda `%pip` o en un Environment |
| `'coroutine' object has no attribute 'choices'` o `no attribute 'client_sync'` | No uses `aifunc.session.client`: es asíncrono. Usa `openai.AzureOpenAI` con `get_openai_httpx_sync_client` |
| `No module named 'synapse.ml.aifunc'` | Notebook de PySpark en un runtime de Fabric |
| Error con `temperature` en el runtime 1.3 | Fija `p_runtime_2_0 = 'NO'`: el ajuste de temperatura es solo para el runtime 2.0 |
| El panel de Copilot no abre | Private Link, capacidad sin F2 o ajuste de inquilino |
| Las funciones son lentas o costosas | Prueba con pocas filas y revisa el consumo de CU en la aplicación de métricas de la capacidad |

**Lo observado en Fabric (30 de octubre de 2026, capacidad F8, runtime 2.0).** Con `nest_asyncio` y `openai` instalados, las nueve funciones probadas y el LLM desde código **respondieron correctamente, en español**. Dos ejemplos para validar: `extract` llegó a devolver «más de una hora» como si fuera un monto, y un *prompt* ambiguo («transacciones del mes 21») hizo que el modelo leyera un conteo como un número de mes. Las salidas **varían entre ejecuciones**.

## Siguiente

Completa la [plantilla de evidencias del bonus](evidencias.md) y revisa las [referencias](guia.md#referencias).
