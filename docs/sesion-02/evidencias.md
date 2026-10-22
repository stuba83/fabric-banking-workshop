# Evidencias — Sesión 2

Crear una copia por participante y conservarla dentro de la organización. **No subir la plantilla completada, capturas, IDs del tenant ni logs al repositorio público.** No incluir secretos ni datos reales.

## 1. Identificación y preparación

| Campo | Valor |
|---|---|
| Participante / prefijo propio | |
| Fecha de revisión | |
| Carpeta del workspace | |
| Lakehouse predeterminado | |
| Nombre del notebook | |
| Nombre del pipeline | |
| Punto focal que revisa | |

- [ ] Completé las evidencias de S1 y mantengo Pro y rol Member/Admin.
- [ ] Los seis CSV originales están en `Files/bronze/banca_sintetica`.
- [ ] Importé el notebook, revisé su código y lo guardé dentro de mi carpeta.
- [ ] Adjunté mi Lakehouse como predeterminado y reinicié la sesión si cambió.
- [ ] Configuré los tres parámetros del pipeline y su vínculo a los parámetros base.
- [ ] Revisé la identidad/conexión utilizada por la actividad Notebook.
- [ ] No usé datos de producción ni modifiqué artefactos de otros participantes.

## 2. Ejecuciones y recuperación

Registrar resultados reales; si no terminaron, indicar **en curso**, **pendiente** o **fallida**. Mantener los identificadores de ejecución solo en esta copia interna.

| Ejecución | Run ID interno | Confirmación SI/NO | Estado del pipeline / notebook | Observación |
|---|---|---|---|---|
| Inicial | | SI | | |
| Reejecución, mismas fuentes | | SI | | |
| Prueba negativa, antes de escribir | | NO | | |
| Recuperación | | SI | | |

Mensaje de error observado en la prueba negativa, sin información sensible:

> Completar.

¿Qué evidencia confirma que la prueba negativa no escribió? Indicar los conteos comprobados antes y después:

> Completar.

## 3. Tablas y controles medidos

Reemplazar `<prefijo>` por el prefijo propio normalizado a minúsculas. Los valores de la columna «esperadas» no cuentan como medición.

| Tabla | Filas esperadas | Filas medidas iniciales | Filas medidas tras reejecución | Esquema string y contenido verificados |
|---|---:|---|---|---|
| `<prefijo>_bronze_clientes` | 1.200 | | | |
| `<prefijo>_bronze_cuentas` | 1.800 | | | |
| `<prefijo>_bronze_sucursales` | 7 | | | |
| `<prefijo>_bronze_productos` | 5 | | | |
| `<prefijo>_bronze_calendario` | 183 | | | |
| `<prefijo>_bronze_transacciones` | 72.360 | | | |

- [ ] El resumen final del notebook corresponde al run del pipeline revisado y muestra `status: success`.
- [ ] Los controles incluyen conteo, esquema y contenido persistido frente al origen.
- [ ] La reejecución no acumuló filas: transacciones continúan en 72.360.
- [ ] Los CSV originales siguen en Files sin cambios.
- [ ] No limpié, convertí fechas/importes ni dedupliqué en bronce.
- [ ] La prueba negativa quedó fallida y la recuperación completó nuevamente las seis tablas.

Evidencia interna de tablas y salidas de control; enlace o captura acotada:

> Completar.

## 4. Comprensión

1. ¿Qué ejecuta el pipeline y qué realiza el notebook?

   Respuesta:

2. ¿Por qué las fechas y los importes siguen siendo string en esta capa?

   Respuesta:

3. ¿Por qué reemplazar el lote evita duplicar filas al reejecutar? ¿En qué se diferencia de append?

   Respuesta:

4. Si la cuarta tabla falla, ¿puede considerarse todo el lote actualizado? ¿Cómo lo recuperarías?

   Respuesta:

5. ¿Por qué 72.000 movimientos no es todavía el resultado correcto de esta sesión?

   Respuesta:

Reglas previstas para plata, sin implementarlas todavía:

| Caso | Cantidad esperada | Tratamiento previsto |
|---|---:|---|
| Copias exactas | 288 | |
| Cuenta inexistente | 24 | |
| Fecha/hora inválida | 24 | |
| Monto negativo | 24 | |
| Canal con espacios/minúsculas | 720 | |
| Canal vacío | 360 | |

## 5. Bloqueos y revisión

| Paso | Mensaje observado, sin secretos | Responsable | Estado |
|---|---|---|---|
| | | | |

**Estado de la entrega:** pendiente / lista para S3 / bloqueada. Elegir uno:

> Completar.

**Duda prioritaria para consolidar con el punto focal:**

> Completar o indicar «sin dudas por ahora».
