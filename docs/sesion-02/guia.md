# Sesión 2 — Ingesta bronce orquestada con un pipeline

**Audiencia:** Ingenieros de datos  
**Duración en vivo:** 60 minutos, sin extensión  
**Fecha y horario:** por definir en cada entrenamiento  
**Modalidad:** Demostración breve, ejecución individual y práctica dirigida

## Resultado esperado

Cada participante creará un pipeline que ejecute un notebook de ingesta sobre su propio Lakehouse. El resultado serán **seis tablas Delta bronce**, con los mismos registros y valores de los CSV originales, y controles que hagan fallar la ejecución ante una diferencia.

**El pipeline orquesta; el notebook lee y escribe los datos.** Esta práctica usa una actividad **Notebook**, no una actividad Copy Data. Se parte de archivos ya cargados en OneLake en la Sesión 1; no se configuran conectores externos, gateways ni fuentes de producción.

## 1. Pre-work

### Ambiente y fuentes

Completar los [accionables de la Sesión 1](../sesion-01/guia.md) y mantener los [requisitos del laboratorio](../requisitos.md):

- Power BI Pro y rol Member/Admin como requisitos del taller.
- Carpeta del participante y artefactos con su nomenclatura propia.
- Lakehouse individual dentro del workspace compartido.
- Seis CSV originales en `Files/bronze/banca_sintetica`, **sin subcarpeta `csv` adicional**:

| Archivo | Filas esperadas, sin encabezado | Columnas |
|---|---:|---:|
| `clientes.csv` | 1.200 | 7 |
| `cuentas.csv` | 1.800 | 6 |
| `sucursales.csv` | 7 | 3 |
| `productos.csv` | 5 | 4 |
| `calendario.csv` | 183 | 9 |
| `transacciones.csv` | 72.360 | 9 |

Usar los archivos de [`dataset/csv`](../../dataset/csv), no una copia editada o exportada desde Excel. El notebook comprueba sus hashes contra esta versión del dataset. `creditos.csv` queda fuera de esta práctica.

### Importar el notebook antes del encuentro

1. Descargar [`02_ingesta_bronce.ipynb`](../../notebooks/02_ingesta_bronce.ipynb) desde el repositorio, o localizarlo en la descarga ZIP completa. Descargar el archivo, no guardar la página HTML de GitHub.
2. En Fabric, usar **Import notebook** e importar el `.ipynb`. Renombrarlo con el prefijo propio, por ejemplo `AB_NB_IngestaBronce`, y colocarlo dentro de la carpeta propia del workspace.
3. Seleccionar **PySpark (Python)**. No instalar paquetes: el notebook usa la biblioteca estándar y Spark del runtime de Fabric. El requisito Python 3.14 del generador local **no es un requisito del notebook**.
4. Adjuntar exclusivamente el Lakehouse propio y marcarlo como **predeterminado**. Si cambió el Lakehouse predeterminado de una sesión activa, reiniciar la sesión Spark antes de continuar.
5. Revisar el código y mantener por ahora `p_confirmar_reemplazo = "NO"`. No ejecutar todavía la carga.

**Preparación orientativa:** 15–25 minutos, además de resolver bloqueos de ambiente. Si el tenant no permite notebooks o pipelines, reportarlo al administrador antes de la sesión.

## 2. Agenda — 60 minutos

| Minutos | Actividad | Resultado |
|---|---|---|
| 00–10 | Revisar entregas de S1 y dudas consolidadas | Confirmar fuentes y accesos; derivar bloqueos administrativos |
| 10–20 | Orquestación frente a movimiento de datos; contrato de bronce | Entender por qué no tipamos ni limpiamos todavía |
| 20–30 | Configurar parámetros del notebook y crear el pipeline | Una actividad Notebook conectada al artefacto propio |
| 30–45 | Ejecutar el pipeline y observar su estado | Seguir la actividad y los controles de ingesta |
| 45–55 | Revisar tablas y resultados medidos | Comprobar conteos, tipos y contenido conservado |
| 55–60 | Asignar reejecución y prueba de error | Acordar evidencias para la Sesión 3 |

El arranque de Spark y la cola de capacidad pueden consumir varios minutos. No se garantiza que toda ejecución termine en el bloque asignado. Si sigue en curso al cierre, conservar su identificador y completar la revisión como accionable; **en curso no equivale a completada**. La sesión no se extiende.

## 3. Qué hace la ingesta

```text
Pipeline del participante
  -> Actividad Notebook
      -> Confirmar Lakehouse y autorización de reemplazo
      -> Validar los seis CSV antes de escribir
      -> Crear/reemplazar seis tablas bronce Delta
      -> Comprobar conteo, esquema y contenido de cada tabla
      -> Informar éxito solo si todos los controles pasan
```

Todos los campos permanecen como **string**, incluidos fechas e importes. Es intencional: los valores inválidos deben llegar a bronce sin convertirse en nulos ni perderse. Los CSV en Files no se modifican.

El notebook:

- Comprueba Lakehouse predeterminado, workspace, prefijo y confirmación explícita.
- Lee y verifica hashes, encabezados, número de columnas y conteos de los seis archivos antes de la primera escritura.
- Si una tabla de destino ya existe, exige el esquema esperado antes de reemplazarla.
- Carga los datos como tablas Delta mediante **reemplazo de lote completo**, no append.
- Comprueba los registros persistidos frente al origen, incluyendo multiplicidad de duplicados, espacios y cadenas vacías.
- Propaga errores: un control fallido debe verse como ejecución fallida del notebook y de su actividad.

**Alcance de la implementación:** estos archivos pequeños se leen en la memoria del proceso conductor antes de crear los DataFrames. Es una simplificación didáctica para unos pocos MB, no un patrón para ingestas de GB o TB.

## 4. Configurar el pipeline

### Paso 1. Identificar el destino

Usaremos `AB` como ejemplo. Cada participante debe sustituirlo por su propio prefijo y nombre de Lakehouse:

```text
Workspace: LAB-Fabric-Banca
  Carpeta: AB
    AB_Lakehouse
    AB_NB_IngestaBronce
    AB_PL_IngestaBronce
```

El prefijo de tablas se normaliza a minúsculas. Las tablas son contenido del Lakehouse, no artefactos independientes que deban moverse a la carpeta del workspace.

### Paso 2. Revisar la celda de parámetros

El notebook contiene una celda etiquetada **parameters**. Si la importación no la reconoce como tal, seleccionarla y marcarla como celda de parámetros desde el menú del notebook.

| Parámetro del notebook | Tipo | Valor del ejemplo | Significado |
|---|---|---|---|
| `p_lakehouse_esperado` | String | `AB_Lakehouse` | Nombre exacto del Lakehouse propio que debe estar predeterminado |
| `p_prefijo` | String | `AB` | Entre 1 y 20 caracteres: empieza por letra ASCII y continúa con letras, números o `_` |
| `p_confirmar_reemplazo` | String | `SI` | Autoriza reemplazar las seis tablas de laboratorio de ese prefijo |

El valor inicial `NO` **bloquea la escritura**; no es una ejecución de validación exitosa. Cambiar a `SI` solo después de revisar el destino. No introducir nombres de otros participantes, ni rutas o identificadores de producción.

No cambiar el contexto de base de datos mediante comandos `USE` ni ejecutar celdas sueltas de otros notebooks en esta práctica. El destino debe ser el Lakehouse predeterminado de este notebook.

### Paso 3. Crear el pipeline

1. Dentro de la carpeta propia del workspace, crear un **Data pipeline** con nombre `AB_PL_IngestaBronce`. Si se crea en la raíz, moverlo a la carpeta propia.
2. Agregar una actividad **Notebook** y nombrarla `IngerirBronce`.
3. En **Settings**, elegir el notebook `AB_NB_IngestaBronce` del mismo workspace.
4. Seleccionar o crear la conexión de autenticación que el tenant permita para el usuario del laboratorio. Comprobar que la identidad ejecutora tiene acceso al notebook y al Lakehouse. No usar credenciales de otro participante.
5. Para esta práctica no se requiere crear una Workspace Identity, service principal ni secreto. Si las políticas exigen una identidad distinta, detener la configuración y coordinarla con el administrador; no cambiar políticas del tenant como parte del ejercicio.
6. Guardar el notebook y el pipeline antes de ejecutar.

### Paso 4. Pasar parámetros desde el pipeline

Crear tres parámetros **String** a nivel del pipeline con los mismos nombres y los valores del ejemplo adaptados al participante. En **Base parameters** de la actividad Notebook, vincularlos usando contenido dinámico:

| Parámetro base del notebook | Expresión |
|---|---|
| `p_lakehouse_esperado` | `@pipeline().parameters.p_lakehouse_esperado` |
| `p_prefijo` | `@pipeline().parameters.p_prefijo` |
| `p_confirmar_reemplazo` | `@pipeline().parameters.p_confirmar_reemplazo` |

Si se autopueblan los parámetros base, verificar nombres, tipos y expresiones; no confiar en que los valores predeterminados vacíos son correctos. Introducir las expresiones en el editor de contenido dinámico, no como cadenas literales con comillas adicionales.

**No ejecutar dos instancias simultáneas sobre el mismo prefijo.** Esperar a que termine una antes de lanzar la siguiente. En esta sesión la ejecución es manual; no activar programación recurrente.

### Paso 5. Ejecutar y observar

Guardar y seleccionar **Run**. En la salida/historial del pipeline, revisar el identificador de ejecución, estado, actividad Notebook y mensajes de error si los hay.

En el detalle de la ejecución del notebook, revisar las salidas de sus celdas. El resumen final solo debe mostrar `status: success` después de validar las seis tablas. No confundir el resultado de una ejecución interactiva anterior con la ejecución disparada por el pipeline.

## 5. Resultado verificable

Con el prefijo `AB`, las tablas esperadas son:

| Tabla | Filas medidas requeridas | Tipos |
|---|---:|---|
| `ab_bronze_clientes` | 1.200 | Todas las columnas string |
| `ab_bronze_cuentas` | 1.800 | Todas las columnas string |
| `ab_bronze_sucursales` | 7 | Todas las columnas string |
| `ab_bronze_productos` | 5 | Todas las columnas string |
| `ab_bronze_calendario` | 183 | Todas las columnas string |
| `ab_bronze_transacciones` | 72.360 | Todas las columnas string |

Revisar las tablas en **Tables** del Lakehouse; si el Lakehouse usa esquemas, expandir el esquema predeterminado correspondiente. Refrescar la vista si hace falta.

El notebook genera los conteos reales y verifica contenido contra el origen. **La vista previa no demuestra esos conteos.** Para una comprobación adicional desde un notebook PySpark con el mismo Lakehouse predeterminado:

```python
spark.table("ab_bronze_transacciones").count()  # Esperado: 72360
spark.table("ab_bronze_transacciones").printSchema()
```

Si se consulta desde el endpoint SQL, puede haber demora de sincronización; en esta práctica los controles de Spark son la referencia inmediata.

### Qué no debe cambiar todavía

La tabla de transacciones debe conservar **72.360 filas**, con 72.072 IDs distintos y 288 copias adicionales. También conserva las 72 filas que irán a cuarentena en la Sesión 3.

Los 720 canales con espacios/minúsculas y los 360 canales vacíos se mantienen tal como vienen. **Obtener 72.000 filas en esta sesión sería un error de alcance:** significaría que se limpió o descartó información antes de tiempo.

### Reejecución y fallos

Reejecutar con los mismos parámetros y las mismas fuentes debe dejar los mismos conteos y contenido. Es idempotencia del **resultado del lote**, no una carga incremental ni ausencia de nuevas versiones Delta.

Las seis escrituras **no forman una transacción única**. Un error tardío puede dejar algunas tablas actualizadas y otras no. No declarar completo el lote ni consumirlo como si lo estuviera; corregir la causa y reejecutar el pipeline entero. No borrar tablas de otros prefijos para resolver un problema.

## 6. Accionables antes de la Sesión 3

**Responsable:** cada participante. **Plazo:** antes de la Sesión 3, según el calendario que se acuerde.  
**Dedicación orientativa:** 45–60 minutos de trabajo activo, más el tiempo de ejecución y esperas de capacidad.

| Acción | Criterio de finalización |
|---|---|
| Completar la ejecución inicial si quedó pendiente | Pipeline y notebook exitosos; seis tablas con conteos, esquema y contenido validados |
| Reejecutar sin modificar fuentes ni prefijo | Segunda ejecución exitosa; transacciones siguen en 72.360, no 144.720 |
| Lanzar una ejecución con `p_confirmar_reemplazo = NO` | Actividad fallida antes de escribir; registrar mensaje y comprobar que los conteos anteriores no cambiaron |
| Restaurar `SI` y volver a ejecutar | Recuperación exitosa y controles nuevamente conformes |
| Explicar dónde ocurre el movimiento de datos | Distinguir pipeline, actividad Notebook, Files y tablas Delta |
| Preparar las reglas para la siguiente sesión | Identificar duplicados, las tres causas de cuarentena y normalización de canal, sin aplicarlas aún |
| Completar las evidencias y revisarlas con el punto focal | Resultados medidos y hasta tres dudas prioritarias consolidadas |

Usar la [plantilla de evidencias](evidencias.md). La prueba negativa cambia un parámetro, **no elimina archivos ni altera los CSV originales**. La práctica continúa en la [Sesión 3: capa plata](../sesion-03/guia.md).

## 7. Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| No aparece el notebook o no puede ejecutarse | Workspace, conexión, identidad ejecutora y permisos |
| Falta Lakehouse predeterminado o su nombre no coincide | Adjuntar el Lakehouse propio, marcarlo como predeterminado, reiniciar Spark y revisar parámetros |
| Archivo inexistente | Ruta exacta `Files/bronze/banca_sintetica`, nombre del archivo y Lakehouse seleccionado |
| Hash o encabezado diferente | Reponer el CSV original desde el repositorio; no desactivar el control |
| Tabla previa con esquema incompatible | Verificar que no se esté apuntando a otro trabajo; usar un prefijo nuevo para el laboratorio si corresponde |
| Ejecución en cola o lenta | Capacidad compartida, sesiones activas y políticas de Spark; coordinar con el administrador |
| El notebook funciona manualmente pero no en pipeline | Parámetros base, celda de parámetros guardada, conexión y contexto de ejecución |

Un bloqueo de identidad, capacidad o configuración no se resuelve ampliando la sesión ni agregando servicios. El punto focal lo coordina con el administrador.

## Referencias

- [Actividad Notebook en Data Factory](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity).
- [Importar notebooks y adjuntar Lakehouses](https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook).
- [Leer y escribir datos de Lakehouse con un notebook](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-notebook-load-data).
- [Contexto del runtime de NotebookUtils](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-runtime).
- [Diccionario del dataset](../../dataset/diccionario.md).

Los controles locales del repositorio no sustituyen la prueba de integración en el tenant del participante. La actividad Notebook, la autenticación, el montaje de OneLake y las escrituras Delta deben comprobarse allí; el repositorio no se conecta a ningún tenant ni despliega artefactos automáticamente.
