# Evidencias — Bonus de ciencia de datos y ML

Crear una copia por participante y conservarla dentro de la organización. **No subir la plantilla completada, capturas, IDs del tenant ni logs al repositorio público.** No incluir secretos ni datos reales.

Registra valores **medidos por ti**. Los valores esperados de las guías no cuentan como medición. Las métricas son aproximadas y cambian con la versión de las bibliotecas del runtime: anota la tuya.

## 1. Identificación y entorno

| Campo | Valor |
|---|---|
| Participante / prefijo propio | |
| Fecha de revisión | |
| Lakehouse predeterminado | |
| Runtime de Fabric (1.3 o 2.0) | |
| Versiones: scikit-learn / MLflow / FLAML | |
| Capacidad (Trial o de pago) | |
| Punto focal que revisa | |

- [ ] Las evidencias de la Sesión 3 están completas y las nueve tablas existen.
- [ ] Importé cada notebook como **PySpark**, con mi Lakehouse como predeterminado y mi prefijo.
- [ ] No usé datos de producción ni modifiqué artefactos de otros participantes.

## 2. B1 — Preparar los datos

| Dato | Esperado | Medido |
|---|---:|---|
| `<prefijo>_silver_transacciones` | 72.000 | |
| `<prefijo>_silver_cuentas` | 1.800 | |
| `<prefijo>_silver_clientes` | 1.200 | |
| `<prefijo>_gold_ml_features_cuentas` (T-SQL) | 9.000 | |
| Filas por corte | 1.800 | |
| Positivas por corte (mayo, junio, julio, agosto) | 563, 589, 631, 651 | |
| Positivas en septiembre | Sin etiqueta | |

- [ ] El resultado de Data Wrangler coincidió con pandas (`1800 cuentas, 72000 transacciones`).
- [ ] La prueba de fuga de datos pasó.
- [ ] (Opcional) La reconciliación con semantic link coincidió en 6 meses. Con el rol `Heredia` obtuve:

> Completar.

Explica con tus palabras por qué las variables usan una ventana fija en lugar de totales acumulados:

> Completar.

## 3. B2 — Entrenar y comparar

| Corrida | AUC de validación |
|---|---|
| Baseline (regla) | |
| `logreg` | |
| `rf` | |
| `hgb` | |
| AutoML (FLAML) | |
| `logreg` con el mejor `C` | |

| Dato | Valor |
|---|---|
| Modelo elegido | |
| Razón de la elección | |
| AUC de prueba (medido **una vez**) | |
| Variables más importantes | |

AUC por grupo de edad, sin atribuir causas (los datos son sintéticos):

| Grupo | Filas | AUC |
|---|---:|---|
| 18-29 | | |
| 30-44 | | |
| 45-59 | | |
| 60+ | | |

- [ ] El experimento `<prefijo>_exp_actividad` muestra todas las corridas.
- [ ] Elegí el modelo con la regla del notebook y medí la prueba una sola vez.

¿Qué significa que un modelo simple casi iguale a uno complejo? ¿Qué hizo AutoML?

> Completar.

## 4. B3 — Registrar y puntuar

| Dato | Valor |
|---|---|
| Versión del modelo registrada | |
| Etiquetas de la versión | |
| Columnas de entrada en la firma | |
| Probabilidades de la versión cargada = modelo original | sí / no |
| Filas de `<prefijo>_gold_ml_puntuacion_actividad` (T-SQL) | |
| Acuerdo entre pandas y `PREDICT` | |

Tabla de umbrales (la que obtuviste):

| Umbral | Marcadas | Precisión | *Recall* |
|---:|---|---|---|
| 0,3 | | | |
| 0,5 | | | |
| 0,7 | | | |

- [ ] Registré la versión con `p_confirmar_reemplazo = 'SI'`.
- [ ] Puntué el corte de septiembre y la tabla tiene una sola `version_modelo`.

¿Qué umbral elegirías y para qué decisión de negocio?

> Completar.

## 5. B4 — MLOps

| Escenario | Decisión | Motivo |
|---|---|---|
| 1. Cierre de agosto | | |
| 2. Cierre de septiembre | | |
| 3. Reejecución (¿mismas filas?) | | |
| 4. Deriva simulada (recomendación) | | |
| 5. Retador `rf` | | |
| 6. Reversión | | |

| Dato | Valor |
|---|---|
| AUC real de las predicciones de agosto | |
| Variables con deriva `alta` en el escenario 4 | |
| Filas finales de la tabla de puntuación | |

- [ ] La reejecución no duplicó filas ni versiones.
- [ ] Entiendo por qué la deriva simulada recomienda `revisar` y no `reentrenar`.

¿Qué cambiarías para llevar este ciclo a un proceso real? (frecuencia, quién aprueba una promoción, qué alerta activa qué acción)

> Completar.

## 6. B5 — IA en notebooks

| Dato | Valor |
|---|---|
| ¿Las funciones de IA estuvieron disponibles? | sí / no |
| Si no, mensaje observado (sin secretos) | |

Para tres comentarios sintéticos, la salida de las funciones de IA y tu valoración:

| Comentario | Sentimiento | Tema | ¿Correcto? |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

- [ ] Probé Copilot (o lo vi en una demostración) y revisé la vista de diferencias antes de aceptar un cambio.
- [ ] Probé o conozco los pasos para crear un agente de datos.

*Prompts* de Copilot que probé y qué corregí o rechacé:

> Completar.

Una regla de uso responsable de IA que aplicaría mi equipo:

> Completar.

## 7. B6 — Transacciones atípicas y puntuación en línea

| Dato | Esperado | Medido |
|---|---:|---|
| Filas con variables (al menos 10 transacciones previas) | 54.526 | |
| Entrenamiento / validación / prueba | 28.743 / 12.231 / 12.800 | |
| Anomalías inyectadas en agosto / septiembre | 125 / 130 | |
| Prueba de fuga de datos | «Sin fuga de datos…» | |
| `<prefijo>_gold_ml_referencia_tx` (T-SQL) | 9 | |
| `<prefijo>_gold_ml_anomalias_tx` (T-SQL) | 12.800 | |
| Acuerdo entre pandas y `PREDICT` | 1,0 | |

| Candidato | AP de validación |
|---|---|
| `iforest` | |
| `lof_20` | |
| `lof_50` | |
| `lof_100` | |
| `lof_200` | |

| Dato | Modelo | Línea base |
|---|---|---|
| Elegido y razón | | — |
| AUC de prueba (medido **una vez**) | | |
| Precisión / *recall* | | |
| Tasa de marcadas | | |
| *Recall* de `monto_extremo` | | |
| *Recall* de `madrugada` | | |
| *Recall* de `rafaga` | | |

| Monitoreo | Valor |
|---|---|
| Tasa de marcadas en septiembre | |
| Tasa de marcadas con los montos +60 % (simulado) | |
| PSI de `z_monto_tipo` en septiembre / simulado | |

| *Endpoint* (vista previa) | Valor |
|---|---|
| ¿Pudiste activar una versión? ¿Cuánto tardó? | |
| Latencia observada (sin prometer un SLA) | |
| ¿Coincidió con la versión cargada en el notebook? | |
| Si no estaba disponible, mensaje observado (sin secretos) | |

- [ ] La prueba de fuga de datos pasó.
- [ ] Las tres tablas de comparación (candidatos, modelo frente a línea base, monitoreo) están completas.
- [ ] Entiendo por qué `iforest` rinde peor que `lof` en estos datos.
- [ ] Activé el *endpoint* **a propósito** y lo desactivé al terminar (o anoté por qué no pude).

Explica con tus palabras por qué las variables de una transacción deben calcularse con el mismo código al entrenar y al servir:

> Completar.

Qué umbral (capacidad de revisión) elegirías para tu organización y por qué:

> Completar.
## 8. Comprensión

1. ¿Por qué la división de datos es por tiempo y no al azar?

   Respuesta:

2. ¿Qué diferencia hay entre la deriva de las variables de entrada y la caída del desempeño real, y cuál justifica reentrenar?

   Respuesta:

3. Fabric no ofrece etapas ni alias de modelo. ¿Cómo se decidió aquí cuál es el campeón y por qué es auditable?

   Respuesta:

4. ¿Qué atributos no entran al modelo y para qué se usan?

   Respuesta:

5. ¿Qué parte de este bonus funciona en Trial y qué parte requiere una capacidad de pago?

   Respuesta:

## 9. Bloqueos y revisión

| Módulo y paso | Mensaje observado, sin secretos | Responsable | Estado |
|---|---|---|---|
| | | | |

**Estado de la entrega:** completa / parcial / bloqueada. Elegir uno:

> Completar.

**Duda prioritaria para consolidar con el punto focal:**

> Completar o indicar «sin dudas por ahora».
