# Módulo B6 — Detectar transacciones atípicas y puntuar en línea

**Notebook:** [B6_anomalias_en_linea.ipynb](../../notebooks/bonus_ml/B6_anomalias_en_linea.ipynb)  
**Dedicación orientativa:** 60–75 minutos  
**Capacidad:** funciona en Trial salvo la llamada al *endpoint* en tiempo real (vista previa: comprueba tu tenant); esa celda no falla si no está disponible  
**Guía general:** [Bonus de ciencia de datos](guia.md)

## Objetivo

Recorrer el ciclo de vida de un modelo cuyo uso es **en línea**: una decisión por transacción, en el momento en que ocurre. Se entrena un detector **sin etiquetas**, se mide con anomalías conocidas, se elige entre algoritmos con experimentos, se registra, se puntúa por lotes y **una transacción a la vez** por el *endpoint* del modelo, y se monitorea sin necesitar etiquetas.

## Antes de empezar

- Sesión 3 completada (tablas plata con sus conteos). B3 y B4 recomendados: aquí se reutilizan el registro de modelos, `PREDICT` y el PSI.
- Parámetros: `p_lakehouse_esperado`, `p_prefijo`, `p_confirmar_reemplazo` (`SI` para registrar y escribir), `p_tasa_revision` (`0.01` por defecto) y `p_probar_endpoint` (`SI` por defecto).
- **Cada ejecución registra una versión nueva** del modelo `<prefijo>_modelo_anomalias_tx`.
- El notebook se ejecuta completo en unos **3 minutos** (la parte pesada es el seguimiento de las seis corridas y el registro).

## Qué cambia frente a B1–B4

| Tema | B1–B4 (propensión de actividad) | B6 (transacciones atípicas) |
|---|---|---|
| Tipo de problema | Supervisado, con etiqueta del mes siguiente | **No supervisado**: no hay etiquetas de fraude |
| Grano | Una fila por cuenta y mes | **Una fila por transacción** |
| Uso | Por lotes, una vez al mes | Por lotes **y en línea** |
| Cómo se mide | AUC con la etiqueta real | **Anomalías inyectadas** (conocidas) en validación y prueba |
| Monitoreo | Deriva y desempeño real | **Tasa de marcadas** y deriva de las variables, que no necesitan etiquetas |

> **Honestidad sobre la evaluación.** En un caso real hay pocos casos confirmados o ninguno. Aquí se **inyectan** anomalías para poder medir; las métricas son de datos sintéticos y solo sirven para practicar el ciclo de vida. Las anomalías inyectadas son más sencillas que las reales.

## El caso

> Dada una transacción en el momento en que ocurre, ¿se parece a lo que esa cuenta suele hacer?

| Período | Uso | Anomalías inyectadas |
|---|---|---|
| Abril | Solo aporta historial a las primeras transacciones | No |
| Mayo, junio y julio | **Entrenamiento** (supuesto: casi todo es normal) | **No** |
| Agosto | **Validación**: elegir el algoritmo y fijar el umbral | Sí (semilla 11) |
| Septiembre | **Prueba** (se mide **una vez**) y puntuación | Sí (semilla 23) |

Una transacción necesita al menos **10 previas** en su cuenta para tener historial.

### Los tres tipos de anomalía inyectada

Cerca del **1 %** de las filas de cada mes de evaluación, repartido por igual:

| Tipo | Qué se hace |
|---|---|
| `monto_extremo` | El monto se multiplica por un factor entre 3 y 8 |
| `madrugada` | La hora pasa a las 0 a 5 h (en estos datos **nunca** ocurre) y el monto sube entre 1 y 2,5 veces |
| `rafaga` | Tras una transacción se agregan tres más de la misma cuenta, tipo y canal en los siguientes 20 minutos. Las tres agregadas son las etiquetadas |

## Conceptos

| Concepto | Qué es |
|---|---|
| **Detección sin etiquetas** | El modelo aprende lo normal y puntúa qué tan lejos queda cada transacción |
| **Referencia** | Mediana y desviación robusta del logaritmo del monto por tipo, calculadas **solo con el entrenamiento**; sin ella no se puede calcular una variable en línea |
| **Umbral por capacidad de revisión** | Se marca la fracción de transacciones que el equipo puede revisar (`p_tasa_revision`); el umbral se fija en validación y **viaja dentro del modelo** (`offset_`) |
| **Mismo código para entrenar y servir** | Una sola función calcula las variables de una transacción, sea en el lote o en la solicitud en línea |
| **PSI y tasa de marcadas** | Señales de monitoreo que **no necesitan etiquetas** |

### Las variables

Cada una usa únicamente lo que ocurrió **antes** de la transacción:

| Variable | Qué mide |
|---|---|
| `z_monto_tipo` | Cuántas desviaciones robustas se aleja el monto de lo normal de su tipo |
| `hora`, `es_fin_semana` | Cuándo ocurrió |
| `log_minutos_desde_ultima` | Tiempo desde la transacción anterior de la cuenta, en escala logarítmica |
| `tx_ultimas_24h` | Transacciones previas de la cuenta en las últimas 24 horas |
| `pct_canal_historial` | Parte de las **últimas 10** transacciones previas de la cuenta que usó este mismo canal (ventana fija: no cambia solo porque el historial crece) |
| `canal`, `tipo_transaccion` | Categóricas |

## Qué hace cada sección

| Sección | Qué se hace |
|---|---|
| 1. Preparar | Validaciones de Lakehouse y prefijo; lectura de las tablas plata |
| 2. Referencia y variables | Calcula la referencia con el entrenamiento y las variables de cada transacción |
| 3. Anomalías conocidas | Inyecta las anomalías y **prueba que no hay fuga**: al cortar los datos a mitad de septiembre, las variables anteriores no cambian |
| 4. Entrenar y elegir | Cinco candidatos con su corrida de MLflow (`iforest` y `lof` con 20, 50, 100 y 200 vecinos), más una **línea base** sin aprendizaje; elige con el AP de validación |
| 5. Umbral y prueba | Fija el umbral en validación y mide en prueba, contra la línea base y por tipo de anomalía |
| 6. Registrar | Guarda el modelo con su **firma**, las métricas y la **referencia** como artefacto; registra la versión con etiquetas; comprueba que la versión cargada da los mismos puntajes y marcas |
| 7. Por lotes | Puntúa septiembre y guarda `<prefijo>_gold_ml_referencia_tx` y `<prefijo>_gold_ml_anomalias_tx`; comprueba `PREDICT` contra pandas |
| 8. En línea | Arma la solicitud de una transacción normal y una sospechosa, y llama al *endpoint* si hay una versión activa |
| 9. Monitorear | Compara la tasa de marcadas y el PSI de septiembre con un cambio simulado de montos (+60 %) |
| 10. A producción | Qué falta para llevarlo a un proceso real |

## Lo que debes entender

- **La elección del algoritmo depende de cómo se ven las anomalías.** `iforest` (*Isolation Forest*) rinde mucho peor que `lof` (*Local Outlier Factor*). No es un error: separa con cortes al azar **dentro del rango que vio al entrenar**, y una madrugada o un monto muy alto caen **fuera de ese rango**. Eso se averigua con experimentos, no por reputación.
- **Ninguno gana en todos los tipos.** La línea base (marcar lo que supera el máximo histórico de su tipo) tiene muy buena precisión y detecta mejor los montos extremos, pero **no ve las ráfagas** y deja pasar la mayoría. En la práctica se combinan reglas y modelo.
- **El umbral es una decisión de negocio.** Con `p_tasa_revision = 0.01`, una precisión cercana a 50 % significa que de cada dos transacciones que el equipo revisa, una es realmente atípica.
- **El monitoreo sin etiquetas existe.** Si los montos suben, `z_monto_tipo` deriva (PSI muy por encima de 0,25) y la tasa de marcadas se multiplica, aunque no haya una sola etiqueta.

## El *endpoint* en tiempo real (vista previa)

Un modelo nuevo **nunca** tiene su *endpoint* activo: se activa a propósito y cuesta capacidad mientras está activo. El notebook **no activa nada**.

1. En la página de la versión: **Activate version endpoint** (o la API). Documentado: «en unos minutos»; en las pruebas de este laboratorio, por API, tardó **entre 5 y 6 minutos**.
2. Cuando la versión esté `Active`, vuelve a ejecutar **solo la celda de la sección 8** que llama al *endpoint*: busca la versión activa más reciente, envía la solicitud, mide el tiempo y comprueba que la respuesta coincida con la de **esa misma versión** cargada en el notebook.
3. También puedes usar **Preview predictions** en la misma página, o la API: `POST .../mlmodels/<id>/endpoint/versions/<n>/score` con el cuerpo que imprime el notebook.
4. Al terminar, desactívala (**Deactivate**).

Lo documentado por Microsoft: sabores `sklearn`, LightGBM, XGBoost y Keras; el modelo necesita **firma** (sin tensores); hasta 5 versiones activas y 3 nodos; se **duerme a los 5 minutos** sin uso y la primera llamada tarda más; mientras está activo consume **5 CU-segundos por nodo y por segundo**. **No prometas un SLA de latencia** sin medirlo con tu carga y tu región.

## Resultado verificable

Los **conteos** son exactos; las **métricas** son aproximadas (dependen de las versiones de las bibliotecas).

| Control | Esperado | Tipo |
|---|---|---|
| Filas con variables (transacciones con al menos 10 previas) | 54.526 | Exacto |
| Entrenamiento (mayo a julio) / validación / prueba | 28.743 / 12.231 / 12.800 | Exacto |
| Anomalías inyectadas en agosto y en septiembre | 125 (25 + 25 + 75) y 130 (26 + 26 + 78) | Exacto |
| Prueba de fuga de datos | «Sin fuga de datos: 47168 transacciones anteriores al corte…» | Exacto |
| Candidatos | `iforest` con AP de validación ≈ 0,1; `lof` entre ≈ 0,4 y ≈ 0,65, mejora con más vecinos | Aproximado |
| Modelo elegido | `lof` (el de menos vecinos a menos de 0,01 de AP del mejor) | Aproximado |
| Prueba, modelo elegido | AUC ≈ 0,98; AP ≈ 0,5–0,6; precisión y *recall* ≈ 0,5–0,6; marcadas ≈ 1 % | Aproximado |
| Prueba, línea base | Precisión ≈ 0,9 y *recall* ≈ 0,3; *recall* de `rafaga` = 0 | Aproximado |
| Filas de `<prefijo>_gold_ml_referencia_tx` | 9 (una por tipo de transacción) | Exacto |
| Filas de `<prefijo>_gold_ml_anomalias_tx` | 12.800 (septiembre), todas con la misma `version_modelo` | Exacto |
| `PREDICT` frente a pandas | Acuerdo 1,0 | Exacto |
| PSI de `z_monto_tipo` con los montos +60 % | Muy por encima de 0,25 (`alta`); con datos normales, `estable` | Aproximado |
| Tasa de marcadas con los montos +60 % | Más de 2,5 veces la de septiembre | Aproximado |

```sql
SELECT version_modelo, COUNT(*) AS filas, SUM(es_atipica) AS marcadas, SUM(es_anomalia_inyectada) AS inyectadas
FROM ab_gold_ml_anomalias_tx
GROUP BY version_modelo;

SELECT tipo_anomalia, COUNT(*) AS filas, SUM(es_atipica) AS marcadas
FROM ab_gold_ml_anomalias_tx
WHERE es_anomalia_inyectada = 1
GROUP BY tipo_anomalia;
```

## Qué documentar en las evidencias

- La tabla de candidatos (AP de validación) y el modelo elegido con su razón.
- Las métricas de prueba del modelo y de la línea base, y el *recall* por tipo de anomalía.
- La versión registrada, sus etiquetas y las columnas de entrada de la firma.
- Las dos tablas escritas (conteo medido con T-SQL) y el acuerdo con `PREDICT`.
- La tasa de marcadas de septiembre frente a la del cambio simulado, y el PSI de `z_monto_tipo`.
- Si activaste el *endpoint*: cuánto tardó en activarse, la latencia que mediste y si coincidió con el modelo local. Si no estaba disponible, el mensaje que viste.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `p_confirmar_reemplazo must be exactly 'SI'` al registrar | Es lo esperado con `NO`: el notebook entrena y mide, pero no registra ni escribe |
| `ab_silver_transacciones: expected an existing table` | Completa la Sesión 3 con el mismo prefijo |
| `data leakage check: expected 0 differences` | Alguien cambió el cálculo de las variables para que use datos posteriores a la transacción |
| `MLFlowTransformer no disponible` | El notebook debe ser de PySpark en un runtime de Fabric |
| `PREDICT` no coincide | Que el modelo tenga firma, sea `sklearn` y las columnas coincidan; `PREDICT` devuelve `-1` (atípica) o `1` |
| `Endpoint del modelo … → ninguna version activa` | Es lo esperado hasta que actives una versión: sigue la sección «El *endpoint* en tiempo real» |
| `Endpoint … → no disponible (…)` | Vista previa no habilitada en tu tenant o región, o sin permiso; el resto del notebook no depende de él |
| `endpoint: expected …; observed …` | La versión activa no es la que el notebook cargó, o sus variables no coinciden con la firma |
| Un candidato tarda mucho | `lof` compara contra los datos de entrenamiento; el notebook ya usa una muestra de 20 000 filas |
| La primera llamada al *endpoint* tarda más | Estaba dormido (5 minutos sin uso): es el comportamiento documentado |

## Siguiente

Completa la [plantilla de evidencias del bonus](evidencias.md) y revisa las [referencias](guia.md#referencias).
