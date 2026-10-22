# Evidencias — Sesión 1

Copiar esta plantilla por participante a la ubicación interna acordada por el equipo. Completar con resultados propios. No incluir contraseñas, tokens, información de producción ni capturas de otros proyectos.

## Identificación

| Campo | Valor por completar |
|---|---|
| Participante | |
| Fecha de revisión | |
| Workspace del laboratorio | |
| Carpeta propia dentro del workspace | |
| Prefijo / nomenclatura elegida | |
| Nombre del Lakehouse | |
| Enlace interno al Lakehouse | |
| Punto focal que revisó la entrega | |

## 1. Preparación del ambiente

Marcar solo lo comprobado. Si existe un bloqueo, dejar el punto pendiente y describirlo en la sección 5.

- [ ] Ingresé al portal con mi cuenta corporativa.
- [ ] Mi licencia Power BI Pro está activa.
- [ ] Tengo rol Member o Admin en el workspace.
- [ ] El administrador confirmó que el workspace está asignado a una capacidad activa y vigente para el laboratorio.
- [ ] Yo creé mi propia carpeta dentro del workspace.
- [ ] Elegí una nomenclatura distinta de la de los demás participantes.
- [ ] Creé mi Lakehouse dentro de mi carpeta con esa nomenclatura.
- [ ] Utilicé únicamente los archivos sintéticos del paquete.

## 2. Fuente bronce cargada

Ruta prevista dentro del Lakehouse: `Files/bronze/banca_sintetica`.

| Archivo | Presente en Files: sí/no | Filas esperadas, sin encabezado | Filas medidas: valor o «pendiente S2» | Método de conteo, si se midió |
|---|---|---:|---|---|
| `clientes.csv` | | 1.200 | | |
| `cuentas.csv` | | 1.800 | | |
| `sucursales.csv` | | 7 | | |
| `productos.csv` | | 5 | | |
| `calendario.csv` | | 183 | | |
| `transacciones.csv` | | 72.360 | | |

La vista previa de un archivo puede ser parcial. Si no se ejecutó un conteo completo, escribir **«pendiente S2»**, no copiar el valor esperado en la columna de medición. La carga de `creditos.csv` no es obligatoria para esta entrega.

Evidencia de ubicación: enlace interno o captura acotada del Lakehouse con los seis nombres de archivo visibles:

> Completar.

## 3. Comprensión del recorrido

Responder cada pregunta en 1–3 líneas:

1. ¿Qué diferencia hay entre capacidad, workspace y Lakehouse?

   Respuesta:

2. ¿Qué función cumple OneLake?

   Respuesta:

3. ¿Dónde conservarías un CSV original y dónde una tabla depurada? ¿Subir el CSV crea automáticamente una tabla Delta?

   Respuesta:

4. ¿Qué diferencia hay entre un modelo semántico y un reporte de Power BI?

   Respuesta:

5. ¿Qué parte del recorrido te resulta más familiar y cuál te genera más dudas?

   Respuesta:

Explicar el control esperado de movimientos, sin ejecutar todavía la limpieza:

> 72.360 filas originales − ______ duplicados − ______ filas en cuarentena = 72.000 movimientos plata.
>
> ¿Qué sucede con los canales vacíos o con espacios/minúsculas?:

Pregunta de negocio adicional para el reporte final y columnas que permitirían responderla:

> Completar.

## 4. Lectura y autoevaluación

- [ ] Revisé las unidades introductorias del módulo asignado de Microsoft Learn.
- [ ] Completé su evaluación como autoevaluación.
- [ ] Leí las secciones de clientes, cuentas y transacciones del diccionario.
- [ ] Leí el tratamiento previsto de las anomalías en el README.

Duda principal de la lectura:

> Completar, o indicar «sin dudas por ahora».

## 5. Bloqueos

Si no hay bloqueos, escribir «sin bloqueos».

| Paso que falla | Mensaje exacto, sin secretos | Responsable de atenderlo | Estado |
|---|---|---|---|
| | | | |

## 6. Revisión del punto focal

- [ ] Se comprobó carpeta y Lakehouse propios con la nomenclatura del participante.
- [ ] Los seis CSV requeridos están presentes en la ruta indicada.
- [ ] No se modificaron los originales ni se usaron datos productivos.
- [ ] Las respuestas distinguen Files de Tables y modelo semántico de reporte.
- [ ] Se registraron los bloqueos y las dudas para consolidarlos.

**Estado de la entrega:** pendiente / lista para Sesión 2 / bloqueada. Elegir uno:

> Completar.
