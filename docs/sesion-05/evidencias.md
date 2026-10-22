# Evidencias — Sesión 5

Crear una copia por participante y conservarla dentro de la organización. **No subir la plantilla completada, capturas, IDs del tenant ni logs al repositorio público.** No incluir secretos ni datos reales.

## 1. Identificación

| Campo | Valor |
|---|---|
| Participante / prefijo propio | |
| Fecha de revisión | |
| Punto focal que revisa | |

## 2. Matriz de entregables

Registrar el estado **real**. Si algo no terminó, indicar **parcial**, **pendiente** o **bloqueada** y su causa; no completar con valores esperados.

| Sesión | Estado | ¿Evidencias completas? | Pendiente o causa del bloqueo |
|---|---|---|---|
| 1. Fundamentos y primera carga | | | |
| 2. Ingesta bronce | | | |
| 3. Capa plata y tabla oro | | | |
| 4. Modelo, seguridad y gobernanza | | | |

## 3. Reejecución de punta a punta

| Dato | Valor |
|---|---|
| Fecha y hora de la ejecución | |
| Run ID interno del pipeline | |
| Estado de la actividad de ingesta | |
| Estado de la actividad de plata | |
| Observaciones | |

Valores medidos tras la reejecución (los esperados no cuentan como medición):

| Dato | Esperado | Medido |
|---|---:|---|
| `<prefijo>_bronze_transacciones` | 72.360 | |
| `<prefijo>_silver_transacciones` | 72.000 | |
| `<prefijo>_silver_transacciones_cuarentena` | 72 | |
| `<prefijo>_silver_transacciones_duplicadas` | 288 | |
| `<prefijo>_gold_transacciones_mes_canal` | 30 | |
| Medida `Transacciones` del reporte | 72.000 | |
| Medida `Monto créditos` del reporte | 14.976.153.627,79 | |
| Medida `Monto débitos` del reporte | 4.530.373.831,90 | |
| Rol `Heredia` en **Test as role** | 8.971 | |

- [ ] La reejecución no duplicó filas ni cambió ningún valor.
- [ ] Si el reporte no coincidió al principio, actualicé el modelo y revisé las relaciones antes de buscar otras causas.

Diferencias observadas y su explicación:

> Completar o indicar «sin diferencias».

## 4. Recorrido de cinco minutos

- [ ] Preparé un guion con los cinco pasos: fuentes, bronce, plata, oro y modelo, reporte y seguridad.
- [ ] Cada paso incluye un número que **medí yo mismo**.
- [ ] Usé la vista de linaje del workspace como apoyo.
- [ ] Expliqué por qué la seguridad por filas no se ve como Member o Admin.
- [ ] Mencioné que las escrituras de varias tablas no son atómicas y cómo se recupera un lote.
- [ ] Respeté los cinco minutos o entregué el guion completo por escrito.

Observaciones del punto focal sobre el recorrido:

> Completar.

## 5. Hallazgos propios

| Hallazgo | Qué observé |
|---|---|
| Qué funcionó | |
| Qué resultó difícil | |
| Qué cambiaría al llevarlo a mi entorno real | |

## 6. Del laboratorio al proyecto real

Para los temas que se discutieron, registrar la decisión o la pregunta abierta del equipo.

| Tema | Decisión o pregunta abierta | Responsable |
|---|---|---|
| Datos y escala | | |
| Calidad | | |
| Acceso | | |
| Operación | | |
| Ciclo de vida | | |
| Capacidad y costo | | |

## 7. Bloqueos y dudas finales

| Paso | Mensaje observado, sin secretos | Responsable | Estado |
|---|---|---|---|
| | | | |

**Dudas priorizadas por el equipo (hasta cinco, consolidadas por el punto focal):**

> Completar o indicar «sin dudas por ahora».

## 8. Limpieza y conservación

- [ ] Conservé, dentro de la organización, mis evidencias completadas, el guion del recorrido y la lista de siguientes pasos.
- [ ] Identifiqué los artefactos propios que quiero conservar y los que se pueden eliminar.
- [ ] Coordiné con el administrador del laboratorio antes de eliminar cualquier artefacto.
- [ ] No eliminé elementos de otros participantes ni de otros proyectos.
- [ ] Confirmé con el administrador qué ocurre con la capacidad de prueba al vencer.

## 9. Siguientes pasos

| Siguiente paso | Responsable | Fecha acordada |
|---|---|---|
| | | |

**Estado final del entrenamiento para este participante:** completo / parcial / bloqueado. Elegir uno:

> Completar.
