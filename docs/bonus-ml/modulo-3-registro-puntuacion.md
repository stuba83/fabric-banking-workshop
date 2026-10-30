# Módulo B3 — Registrar el modelo y puntuar por lotes

**Notebook:** [B3_registro_puntuacion.ipynb](../../notebooks/bonus_ml/B3_registro_puntuacion.ipynb)  
**Dedicación orientativa:** 45–60 minutos  
**Capacidad:** funciona en Trial (el punto de conexión en tiempo real está en vista previa: comprueba tu tenant)  
**Guía general:** [Bonus de ciencia de datos](guia.md)

## Objetivo

Pasar de «un modelo entrenado en un notebook» a **una versión registrada** que cualquiera puede cargar y usar: registrarla con su firma y etiquetas, puntuar las cuentas del último corte, comprobar que el resultado es el mismo por dos caminos y dejar la tabla lista para Power BI.

## Antes de empezar

- B1 completado (y B2 recomendado).
- Parámetros: `p_lakehouse_esperado`, `p_prefijo`, `p_confirmar_reemplazo` (`SI` para registrar y escribir) y `p_tipo_modelo` (`logreg` por defecto).
- **Cada ejecución registra una versión nueva** del modelo `<prefijo>_modelo_actividad`. En B4 eso se automatiza con una regla.

## Conceptos

| Concepto | Qué es |
|---|---|
| **Modelo de ML** (elemento) | Agrupa las versiones. Cada versión guarda su firma, etiquetas y la corrida que la creó |
| **Firma** | Columnas y tipos de entrada y salida. **`PREDICT` la exige** |
| **Etiquetas** | Pares clave-valor que se fijan **al registrar** (tipo de modelo, corte de prueba, métrica) |
| **`PREDICT`** | Puntuación por lotes con un modelo registrado, desde Spark, SQL o una UDF |

**Sin etapas ni alias.** Fabric no documenta etapas de modelo (como «producción») ni alias. Identifica las versiones por su número y, en B4, decide cuál está vigente con una tabla de control.

## Qué hace cada sección

| Sección | Qué se hace |
|---|---|
| 2. Entrenar con firma | Entrena el candidato y lo guarda con su firma |
| 3. Registrar | `register_model` crea una versión con etiquetas |
| 4. Cargar y comparar | `models:/<nombre>/<versión>` debe dar **exactamente** las mismas probabilidades |
| 5. El umbral | Una tabla de precisión y *recall* por umbral: la decisión es de negocio |
| 6. Puntuar | Puntúa el corte de septiembre y guarda `<prefijo>_gold_ml_puntuacion_actividad` con la versión y la fecha |
| `PREDICT` | `MLFlowTransformer` sobre Spark; debe coincidir con pandas |
| 7. Otras formas | Asistente de la versión y punto de conexión en tiempo real (descripción) |
| 8. Power BI | Agregar la tabla al modelo semántico y relacionarla con las cuentas |

### Asistente y punto de conexión

- **Asistente.** En la página de la versión: **Apply this version** → **Apply this model in wizard**. Eliges la tabla de entrada de tu Lakehouse, mapeas columnas, indicas el destino y se genera un notebook con `PREDICT`.
- **Tiempo real (vista previa).** Cada versión puede exponerse como un *endpoint*. Se duerme tras 5 minutos sin uso y, mientras está activo, consume capacidad. **No es necesario aquí**: la pregunta es mensual y por lotes es lo adecuado.

### Llevarlo a Power BI

1. Agrega la tabla de puntuación al modelo semántico de la [Sesión 4](../sesion-04/guia.md).
2. Relaciónala con las cuentas por `cuenta_id` (muchos a uno, una sola dirección): así la seguridad por filas por sucursal también filtra las predicciones.
3. Crea una medida de cuentas con predicción 1 y un visual por sucursal o segmento.

## Resultado verificable

| Control | Esperado |
|---|---|
| Versiones del modelo tras la primera ejecución | 1, con las etiquetas `tipo_modelo`, `corte_prueba` (`2026-08`), `auc_prueba` y `umbral_alta_actividad` (`9`) |
| Probabilidades de la versión cargada frente al modelo original | Idénticas |
| Filas de `<prefijo>_gold_ml_puntuacion_actividad` | 1.800 (corte `2026-09`), todas con la misma `version_modelo` |
| Tabla de umbrales | Al subir el umbral, bajan las cuentas marcadas y el *recall* |
| Acuerdo entre pandas y `PREDICT` | 1,0 |

```sql
SELECT version_modelo, COUNT(*) AS filas, SUM(prediccion) AS marcadas
FROM ab_gold_ml_puntuacion_actividad
GROUP BY version_modelo;
```

## Qué documentar en las evidencias

- El número de versión, sus etiquetas y su firma (cuántas columnas de entrada).
- La comprobación de que la versión cargada reproduce el modelo original.
- La tabla de umbrales y qué umbral elegirías para qué decisión de negocio, con tus palabras.
- El conteo de la tabla de puntuación (medido con T-SQL) y el acuerdo con `PREDICT`.
- Si pudiste, qué viste en el asistente de la versión.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `p_confirmar_reemplazo must be exactly 'SI'` al registrar | Es lo esperado con `NO` |
| `MLFlowTransformer no disponible` | El notebook debe ser de PySpark en un runtime de Fabric |
| `PREDICT` falla o no coincide | Que el modelo tenga firma, sea `sklearn` y las columnas de entrada coincidan con la firma |
| Hay varias versiones del modelo | Cada ejecución crea una; usa la que indique el notebook |
| El reporte no filtra las predicciones | La relación con las cuentas y que siga en una sola dirección (Sesión 4) |

## Siguiente

[Módulo B4: MLOps](modulo-4-mlops.md).
