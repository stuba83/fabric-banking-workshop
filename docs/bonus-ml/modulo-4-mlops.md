# Módulo B4 — MLOps: ciclo repetible, decisión con reglas y monitoreo

**Notebook:** [B4_mlops.ipynb](../../notebooks/bonus_ml/B4_mlops.ipynb)  
**Dedicación orientativa:** 60–90 minutos (cada ciclo toma de uno a dos minutos)  
**Capacidad:** funciona en Trial  
**Guía general:** [Bonus de ciencia de datos](guia.md)

## Objetivo

Convertir B1–B3 en un **ciclo mensual repetible**: validar los datos, entrenar un *retador*, decidir con una regla explícita si reemplaza al *campeón*, puntuar y **monitorear**. Todo queda registrado y se puede reejecutar sin duplicar nada.

```text
datos (features) → compuerta de calidad → entrenar retador → ¿mejora al campeón?
      ↑                                                         │ sí: registrar versión
      │                                                         │ no: conservar campeón
      └── etiquetas del mes anterior ← monitoreo ← puntuar con el campeón
```

## Antes de empezar

- B1 completado. Parámetros: `p_lakehouse_esperado`, `p_prefijo`, `p_confirmar_reemplazo = 'SI'`, `p_modo` (`guiado` o `ciclo`), `p_corte_puntuacion` (`2026-09`), `p_tipo_modelo` (`logreg`) y `p_factor_deriva` (`0.0`).
- **`p_modo = 'guiado'`** recorre seis escenarios para aprender. **`p_modo = 'ciclo'`** ejecuta **un** ciclo y devuelve el resumen con `notebookutils.notebook.exit`; es el modo que se programa en un pipeline.

## Qué aporta Fabric y qué se construye aquí

| Pieza | Fabric | En este módulo |
|---|---|---|
| Orquestación | Actividad **Notebook** de un pipeline, con parámetros y programación | Parámetros `p_*` y el modo `ciclo` |
| Experimentos | Experimentos y corridas de MLflow | Una corrida por ciclo, con la decisión y las métricas |
| Registro | Elemento de modelo con versiones y etiquetas | Se registra **solo** al promover |
| Quién es el campeón | Sin etapas ni alias documentados | **Tabla de control** (`<prefijo>_ml_registro_modelos`) |
| Monitoreo del modelo | Sin función de deriva integrada | **PSI** y desempeño real en tablas Delta |
| Alertas | **Activator** y estado de las ejecuciones | Recomendación: `sin_accion`, `revisar` o `reentrenar` |

## La regla de promoción

- **Piso de calidad:** el retador necesita un AUC de prueba de al menos 0,70.
- **Mejora mínima:** con un campeón, el retador debe superarlo en al menos **0,005** de AUC, **en el mismo corte de prueba**.
- **Si no cumple:** se conserva el campeón y **no se registra** una versión nueva. La corrida de MLflow queda igualmente.
- **Reversión:** se agrega un evento a la tabla de control; no se borra nada.

## Los seis escenarios

| # | Escenario | Qué debes observar |
|---|---|---|
| 1 | **Cierre de agosto.** El ciclo solo ve cortes hasta agosto y no conoce la etiqueta del corte que puntúa | Sin campeón, el retador supera el piso: se promueve y queda como versión 1 |
| 2 | **Cierre de septiembre.** Hay campeón; llegan las etiquetas de agosto | La decisión suele ser `mantener`. Se mide el **AUC real** de lo que el campeón predijo en agosto |
| 3 | **Reejecución** con los mismos datos | Mismas filas y ninguna versión nueva; si no cuadra, el notebook se detiene |
| 4 | **Deriva simulada** (actividad × 1,6) | Las variables de actividad superan PSI 0,25; la recomendación es `revisar`, no `reentrenar` |
| 5 | **Un retador más complejo** (`rf`) | La compuerta decide con la misma regla; no se promueve por ser más complejo |
| 6 | **Reversión** | Con dos o más versiones, se vuelve a la primera y queda registrado el motivo |

**Corrección en el tiempo.** Una ejecución retrospectiva (escenario 1) no puede usar cortes posteriores ni la etiqueta del propio corte: eso sería ver el futuro. Es la misma disciplina de B1, aplicada al ciclo.

**Por qué `revisar` y no `reentrenar`.** La deriva de las variables de entrada **avisa**, pero solo la **caída del AUC real** (cuando llegan las etiquetas) justifica reentrenar. Con las variables acumuladas habría «deriva» cada mes sin que nada cambie; por eso B1 usa ventanas fijas.

## Programarlo en Fabric

1. En un pipeline, agrega una actividad **Notebook** y define los parámetros base (`p_modo = ciclo`, `p_corte_puntuacion`, `p_confirmar_reemplazo`…). Llegan a la celda de parámetros.
2. Programa el pipeline cada mes.
3. Fija las bibliotecas en un **Environment** publicado: las instalaciones `%pip` están desactivadas por defecto en las ejecuciones de pipeline.
4. Usa el **hub de monitoreo** para ver las ejecuciones y **Activator** para avisar de fallos o de cambios de valor.
5. **Control de versiones y despliegue.** Los notebooks, los environments y las bibliotecas de variables se integran con Git y los *deployment pipelines*. Los experimentos y modelos de ML también (**vista previa**), pero **solo viajan los metadatos**: las corridas y las versiones no se copian entre workspaces. Para llevar un modelo a otro workspace se registra de nuevo con el complemento `synapseml-mlflow` y `MLFLOW_TRACKING_URI`.

## Lo que este ciclo no resuelve

No reentrena solo por deriva (lo decide una persona), no hace pruebas A/B y no versiona los datos de entrenamiento. Son los siguientes pasos de un proceso real.

## Resultado verificable

| Control | Esperado |
|---|---|
| Versión 1 tras el escenario 1 | Promovida; en la tabla de control, un evento `promocion` |
| Filas de `ab_gold_ml_puntuacion_actividad` al terminar | 3.600 (1.800 de agosto y 1.800 de septiembre) |
| Filas de `ab_ml_monitoreo_deriva` | 32 (16 variables × 2 cortes); las de septiembre con `simulada = 0` |
| `ab_ml_monitoreo_desempeno` | 1 fila: predicciones de agosto evaluadas con las etiquetas de septiembre; AUC ≈ 0,85 |
| Escenario 3 | `Sin duplicados: el ciclo es idempotente.` |
| Escenario 4 | Al menos 4 variables con deriva `alta`; recomendación `revisar` |

```sql
SELECT TOP 5 secuencia, evento, version, auc_prueba, motivo FROM ab_ml_registro_modelos ORDER BY secuencia DESC;
SELECT variable, psi, deriva FROM ab_ml_monitoreo_deriva WHERE corte = '2026-09' ORDER BY psi DESC;
SELECT * FROM ab_ml_monitoreo_desempeno;
```

## Qué documentar en las evidencias

- La decisión de cada escenario y su motivo, y la tabla de control completa.
- El AUC real del mes anterior y cómo se compara con el de prueba.
- Las variables con deriva en el escenario 4 y por qué la recomendación fue `revisar`.
- Qué cambiarías para llevar este ciclo a un proceso real (frecuencia, quién aprueba una promoción, qué alerta activa qué acción).

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `expected an existing table` al leer los features | Que B1 se ejecutó con `SI` |
| `expected a champion model` | El retador se rechazó por debajo del piso y no hay campeón previo; revisa los datos de B1 |
| `idempotencia: expected …` | Alguien modificó una tabla entre ejecuciones, o se ejecutaron dos ciclos a la vez; no ejecutes dos instancias sobre el mismo prefijo |
| La reversión dice que solo hay una versión | Es lo esperado si ningún retador se promovió |
| La ejecución es lenta | Capacidad compartida y sesiones activas |

## Siguiente

[Módulo B5: IA en los notebooks](modulo-5-ia.md).
