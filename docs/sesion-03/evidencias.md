# Evidencias — Sesión 3

Crear una copia por participante y conservarla dentro de la organización. **No subir la plantilla completada, capturas, IDs del tenant ni logs al repositorio público.** No incluir secretos ni datos reales.

## 1. Identificación y preparación

| Campo | Valor |
|---|---|
| Participante / prefijo propio | |
| Fecha de revisión | |
| Lakehouse predeterminado | |
| Notebook de plata | |
| Pipeline | |
| Punto focal que revisa | |

- [ ] Las evidencias de la Sesión 2 están completas y las seis tablas bronce existen.
- [ ] `<prefijo>_bronze_transacciones` mide 72.360 filas antes de empezar.
- [ ] Importé el notebook, revisé su código y lo guardé dentro de mi carpeta.
- [ ] Adjunté mi Lakehouse como predeterminado en **ambos** notebooks y reinicié la sesión si cambió.
- [ ] Agregué la actividad `PlataSilver` con dependencia On success y vinculé los tres parámetros base.
- [ ] No usé datos de producción ni modifiqué artefactos de otros participantes.

## 2. Ejecuciones y recuperación

Registrar resultados reales; si no terminaron, indicar **en curso**, **pendiente** o **fallida**. Mantener los identificadores de ejecución solo en esta copia interna.

| Ejecución | Run ID interno | Confirmación SI/NO | Estado de cada actividad | Observación |
|---|---|---|---|---|
| Inicial | | SI | | |
| Reejecución, mismas fuentes | | SI | | |
| Prueba negativa, antes de escribir | | NO | | |
| Recuperación | | SI | | |

Mensaje de error observado en la prueba negativa, sin información sensible:

> Completar.

Conteos de las tablas antes y después de la prueba negativa:

> Completar.

## 3. Tablas medidas

Reemplazar `<prefijo>` por el prefijo propio en minúsculas. Los valores esperados no cuentan como medición.

| Tabla | Filas esperadas | Medidas tras la ejecución inicial | Medidas tras la reejecución |
|---|---:|---|---|
| `<prefijo>_silver_clientes` | 1.200 | | |
| `<prefijo>_silver_cuentas` | 1.800 | | |
| `<prefijo>_silver_sucursales` | 7 | | |
| `<prefijo>_silver_productos` | 5 | | |
| `<prefijo>_silver_calendario` | 183 | | |
| `<prefijo>_silver_transacciones` | 72.000 | | |
| `<prefijo>_silver_transacciones_cuarentena` | 72 | | |
| `<prefijo>_silver_transacciones_duplicadas` | 288 | | |
| `<prefijo>_gold_transacciones_mes_canal` | 30 | | |
| `<prefijo>_bronze_transacciones` (sin cambios) | 72.360 | | |

Cuarentena por motivo, medido con T-SQL:

| Motivo | Esperado | Medido |
|---|---:|---|
| `cuenta_inexistente` | 24 | |
| `fecha_hora_invalida` | 24 | |
| `monto_negativo` | 24 | |

Transacciones por canal en la plata, medidas con T-SQL:

| Canal | Medido |
|---|---|
| `BANCA_MOVIL` | |
| `WEB` | |
| `ATM` | |
| `SUCURSAL` | |
| `NO_INFORMADO` | |

- [ ] El resumen final del notebook corresponde al run revisado y muestra `status: success`.
- [ ] Las cuatro consultas T-SQL se ejecutaron en el SQL analytics endpoint de mi Lakehouse.
- [ ] La reejecución no duplicó filas: plata de transacciones y tabla oro conservan sus conteos.
- [ ] Las tablas bronce y los CSV originales siguen sin cambios.
- [ ] La prueba negativa falló antes de escribir y la recuperación completó el lote.

Evidencia interna (enlace o captura acotada del resultado de las consultas):

> Completar.

## 4. Decisiones de calidad documentadas

| Regla | Decisión tomada | Razón |
|---|---|---|
| Copias exactas | | |
| Registros inválidos | | |
| Canal con espacios o vacío | | |

## 5. Comprensión

1. ¿Qué diferencia hay entre bronce y plata en este caso y por qué las tablas bronce no se tocan?

   Respuesta:

2. ¿Por qué se separan los registros inválidos en lugar de corregirlos o borrarlos?

   Respuesta:

3. Si el notebook falla al escribir la tabla oro, ¿qué estado tiene el lote y cómo se recupera?

   Respuesta:

4. ¿Qué puedes hacer con el SQL analytics endpoint y qué requiere volver al Lakehouse con Spark?

   Respuesta:

5. Interpretación de la tabla oro, sin atribuir causas (datos sintéticos):

   Respuesta:

## 6. Bloqueos y revisión

| Paso | Mensaje observado, sin secretos | Responsable | Estado |
|---|---|---|---|
| | | | |

**Estado de la entrega:** pendiente / lista para la Sesión 4 / bloqueada. Elegir uno:

> Completar.

**Duda prioritaria para consolidar con el punto focal:**

> Completar o indicar «sin dudas por ahora».
