# Sesión 3 — Capa plata: limpieza, cuarentena y primera tabla de consumo

**Audiencia:** Ingenieros de datos  
**Duración en vivo:** 60 minutos, sin extensión  
**Fecha y horario:** por definir en cada entrenamiento  
**Modalidad:** Demostración breve, ejecución individual y verificación con T-SQL

## Resultado esperado

Cada participante ampliará su pipeline con una segunda actividad **Notebook** que transforma las seis tablas bronce de la [Sesión 2](../sesion-02/guia.md) en tablas **plata** tipadas, separa los duplicados y los registros inválidos, y publica una tabla **oro** de consumo. Después verificará los resultados con T-SQL en el **SQL analytics endpoint** de su Lakehouse.

La cuenta que debe cuadrar:

```text
72.360 filas bronce  -  288 copias exactas  -  72 registros inválidos  =  72.000 movimientos plata
```

**El pipeline orquesta; el notebook transforma.** Las tablas bronce no se modifican: la plata se calcula a partir de ellas.

## 1. Pre-work

### Ambiente y estado de partida

Completar la Sesión 2 y mantener los [requisitos del laboratorio](../requisitos.md):

- Pipeline de la Sesión 2 ejecutado con éxito, con **seis tablas bronce** en el Lakehouse propio.
- `<prefijo>_bronze_transacciones` con **72.360 filas medidas**, no 72.000.
- Evidencias de la Sesión 2 completas o con los bloqueos registrados.

Si la Sesión 2 no terminó, completarla primero: esta sesión **lee** esas tablas y falla antes de escribir si no están como se espera.

### Importar el notebook antes del encuentro

1. Descargar [`03_plata_silver.ipynb`](../../notebooks/03_plata_silver.ipynb) desde el repositorio. Descargar el archivo, no la página HTML de GitHub.
2. En Fabric, usar **Import notebook**. Renombrarlo con el prefijo propio, por ejemplo `AB_NB_PlataSilver`, y colocarlo en la carpeta propia del workspace.
3. Seleccionar **PySpark (Python)**. No instalar paquetes: el notebook usa la biblioteca estándar y Spark del runtime de Fabric.
4. Adjuntar exclusivamente el Lakehouse propio y marcarlo como **predeterminado**. Reiniciar la sesión Spark si cambió.
5. Revisar el código y mantener `p_confirmar_reemplazo = "NO"` por ahora. No ejecutar todavía la carga.

### Lectura dirigida

- [Warehouse y Lakehouse: guía de decisión](https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-lakehouse-warehouse) (inglés).
- [SQL analytics endpoint de un Lakehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-sql-analytics-endpoint) (inglés).

Llegar con respuestas breves:

1. ¿Qué se puede hacer con T-SQL sobre el SQL analytics endpoint de un Lakehouse y qué no?
2. ¿Cuándo preferirías Spark y cuándo T-SQL para una transformación?
3. ¿Por qué se separan los registros inválidos en lugar de corregirlos o borrarlos?

**Preparación orientativa:** 25–40 minutos, además de resolver bloqueos de ambiente.

## 2. Agenda — 60 minutos

| Minutos | Actividad | Resultado |
|---|---|---|
| 00–10 | Revisar entregas de la Sesión 2 y dudas consolidadas | Confirmar que las seis tablas bronce existen; derivar bloqueos administrativos |
| 10–20 | Reglas de calidad y capas; Lakehouse frente a Warehouse | Entender qué se limpia, qué se aparta y por qué |
| 20–30 | Ampliar el pipeline con la actividad `PlataSilver` | Dos actividades encadenadas con dependencia de éxito |
| 30–45 | Ejecutar el pipeline completo y observar | Notebook de plata exitoso con sus controles |
| 45–55 | Verificar con T-SQL y leer la tabla oro | Conteos medidos; primera respuesta a la pregunta de negocio |
| 55–60 | Asignar reejecución, prueba de error y decisiones por documentar | Acordar evidencias para la Sesión 4 |

El arranque de Spark y la cola de capacidad pueden consumir varios minutos. No se garantiza que toda ejecución termine dentro del bloque. Si sigue en curso al cierre, conservar su identificador y completar la revisión como accionable; **en curso no equivale a completada**. La sesión no se extiende.

## 3. Qué hace la capa plata

```text
Tablas bronce (texto, sin cambios)
  -> Actividad Notebook: PlataSilver
      -> Validar tablas bronce: existen, columnas, tipo texto y conteos
      -> Aplicar tipos y reglas de calidad
      -> Escribir 6 tablas plata, 2 tablas de auditoría y 1 tabla oro
      -> Comprobar conteo, esquema y contenido de cada tabla persistida
      -> Informar éxito solo si todos los controles pasan
```

### Reglas sobre las transacciones

| Regla | Registros | Tratamiento |
|---|---:|---|
| Copias exactas del mismo `transaccion_id` | 288 | Se conserva una; las copias retiradas quedan en la tabla de duplicadas. Si dos filas con el mismo ID difieren, el notebook falla |
| Cuenta inexistente | 24 | Cuarentena, motivo `cuenta_inexistente` |
| Fecha y hora inválida | 24 | Cuarentena, motivo `fecha_hora_invalida` |
| Monto negativo | 24 | Cuarentena, motivo `monto_negativo` |
| Canal con espacios o minúsculas | 720 | Se conservan; el canal se recorta y se pasa a mayúsculas |
| Canal vacío | 360 | Se conservan con el canal `NO_INFORMADO` |

**No se corrige** un monto negativo cambiándole el signo, ni se inventa una cuenta para salvar una referencia: esos registros se apartan para su revisión. Cada registro en cuarentena debe tener exactamente **un** motivo; si tuviera dos, el notebook falla.

Las tablas de cuarentena y de duplicadas conservan las nueve columnas **tal como llegaron, como texto** (la de cuarentena agrega la columna `motivo`), porque un valor inválido no se puede convertir de forma fiable. Cualquier otro valor inesperado —moneda o estado distintos, tipo, dirección o canal fuera de catálogo, fecha fuera del período, monto en cero o con más de dos decimales— **detiene la ejecución** en lugar de apartarse: indica que la fuente cambió y debe revisarse.

### Tipos

- Fechas → `date`; fecha y hora → `timestamp`; importes → `decimal(18,2)`, nunca punto flotante; contadores del calendario → entero.
- La hora se conserva como **hora local de Costa Rica, sin conversión de zona horaria**. Delta guarda un `timestamp` como un instante en UTC; por eso el notebook almacena la hora de Costa Rica tal cual, como si fuera UTC. Al consultarla se ve la misma hora que en el CSV, pero no es un instante UTC real: no restarle ni sumarle horas.
- Se agrega la columna `fecha` derivada de `fecha_hora` para relacionar con el calendario.
- Las tablas de referencia no contienen errores deliberados: un valor que no se pueda convertir detiene la ejecución con el nombre de la tabla, la fila y la columna.

### Tabla oro

`<prefijo>_gold_transacciones_mes_canal` resume las transacciones depuradas por mes y canal, con el número de transacciones y los montos de crédito y de débito. Responde la pregunta inicial del caso: **¿cómo cambia la cantidad de transacciones por mes y por canal?**

**Alcance de la implementación:** el notebook lee estas tablas pequeñas en la memoria del proceso conductor para mantener las reglas fáciles de leer y de probar. Es una simplificación didáctica, no un patrón para GB o TB. A escala se expresarían las mismas reglas con Spark (ventanas para deduplicar, anti-joins para las referencias, conversiones seguras de tipos).

## 4. Ampliar el pipeline

### Paso 1. Abrir el pipeline de la Sesión 2

Abrir `AB_PL_IngestaBronce` (con su prefijo) desde la carpeta propia. Reutilizar los tres parámetros de pipeline que ya existen:

| Parámetro | Valor del ejemplo |
|---|---|
| `p_lakehouse_esperado` | `AB_Lakehouse` |
| `p_prefijo` | `AB` |
| `p_confirmar_reemplazo` | `SI` |

### Paso 2. Agregar la actividad de plata

1. Agregar una segunda actividad **Notebook** y nombrarla `PlataSilver`.
2. Conectar `IngerirBronce` con `PlataSilver` mediante la dependencia **On success**. Así, la plata solo se ejecuta si la ingesta terminó bien.
3. En **Settings**, seleccionar `AB_NB_PlataSilver`, con la misma conexión de autenticación que usa la actividad anterior. Comprobar que la identidad ejecutora tiene acceso al notebook y al Lakehouse.
4. En **Base parameters**, vincular los tres parámetros con contenido dinámico:

| Parámetro base del notebook | Expresión |
|---|---|
| `p_lakehouse_esperado` | `@pipeline().parameters.p_lakehouse_esperado` |
| `p_prefijo` | `@pipeline().parameters.p_prefijo` |
| `p_confirmar_reemplazo` | `@pipeline().parameters.p_confirmar_reemplazo` |

5. Guardar notebook y pipeline antes de ejecutar.

**Cada notebook debe tener el Lakehouse propio como predeterminado.** Revisar los dos. No ejecutar dos instancias del pipeline sobre el mismo prefijo a la vez ni activar una programación recurrente en esta práctica.

### Paso 3. Ejecutar y observar

Seleccionar **Run**. El pipeline vuelve a ejecutar la ingesta de la Sesión 2 —que es idempotente— y después la plata. En el historial, revisar el estado de **cada** actividad y el identificador de ejecución. El resumen final del notebook de plata debe mostrar `status: success` solo después de verificar todas las tablas.

Las nueve escrituras **no forman una transacción única**. Si el notebook falla en una tabla tardía, algunas tablas pueden quedar actualizadas y otras no. No consumir ese lote como completo: corregir la causa y volver a ejecutar el pipeline entero.

## 5. Resultado verificable

Con el prefijo `AB`, las tablas esperadas son:

| Tabla | Filas medidas requeridas |
|---|---:|
| `ab_silver_clientes` | 1.200 |
| `ab_silver_cuentas` | 1.800 |
| `ab_silver_sucursales` | 7 |
| `ab_silver_productos` | 5 |
| `ab_silver_calendario` | 183 |
| `ab_silver_transacciones` | 72.000 |
| `ab_silver_transacciones_cuarentena` | 72 (24 por motivo) |
| `ab_silver_transacciones_duplicadas` | 288 |
| `ab_gold_transacciones_mes_canal` | 30 (6 meses × 5 canales) |

Las tablas bronce siguen intactas: `ab_bronze_transacciones` conserva **72.360** filas.

### Controles de la tabla plata de transacciones

| Mes | Transacciones |
|---|---:|
| 2026-04 | 11.198 |
| 2026-05 | 11.422 |
| 2026-06 | 11.757 |
| 2026-07 | 12.093 |
| 2026-08 | 12.541 |
| 2026-09 | 12.989 |

| Canal | Transacciones |
|---|---:|
| `BANCA_MOVIL` | 41.521 |
| `WEB` | 14.325 |
| `ATM` | 8.576 |
| `SUCURSAL` | 7.218 |
| `NO_INFORMADO` | 360 |

Créditos: **14.976.153.627,79** CRC. Débitos: **4.530.373.831,90** CRC. Son los valores que el notebook comprueba antes de informar éxito. **Los valores de estas tablas son controles esperados:** el participante debe medirlos él mismo en sus tablas y registrarlos en las evidencias.

### Verificar con T-SQL

Abrir el **SQL analytics endpoint** de `AB_Lakehouse` y ejecutar consultas de **solo lectura**. Reemplazar `ab_` por el prefijo propio. Si el Lakehouse usa esquemas, calificar los nombres según corresponda. Si una tabla recién creada no aparece, esperar un momento y refrescar el explorador: la sincronización del endpoint puede tardar.

```sql
SELECT COUNT(*) AS filas FROM ab_silver_transacciones;

SELECT motivo, COUNT(*) AS filas
FROM ab_silver_transacciones_cuarentena
GROUP BY motivo
ORDER BY motivo;

SELECT canal, COUNT(*) AS filas
FROM ab_silver_transacciones
GROUP BY canal
ORDER BY filas DESC;

SELECT mes, SUM(transacciones) AS transacciones
FROM ab_gold_transacciones_mes_canal
GROUP BY mes
ORDER BY mes;
```

El endpoint no permite insertar, actualizar ni borrar. Para modificar tablas se vuelve al Lakehouse y a Spark.

### Lakehouse frente a Warehouse

Ambos guardan datos Delta en OneLake. El Lakehouse se desarrolla con Spark y su endpoint SQL es de solo lectura; un Warehouse se desarrolla con T-SQL, con escritura y transacciones entre varias tablas. En esta práctica usamos el Lakehouse para transformar y el endpoint SQL para verificar. La demostración de un Warehouse queda a cargo del facilitador y **no forma parte de las evidencias** de esta sesión.

## 6. Accionables antes de la Sesión 4

**Responsable:** cada participante. **Plazo:** antes de la Sesión 4.  
**Dedicación orientativa:** 45–60 minutos de trabajo activo, más tiempos de ejecución y espera.

| Acción | Criterio de finalización |
|---|---|
| Completar la ejecución del pipeline si quedó pendiente | Ambas actividades exitosas; nueve tablas con conteos medidos |
| Medir los controles con T-SQL | Cuatro consultas ejecutadas y resultados registrados |
| Reejecutar sin cambiar parámetros ni fuentes | Silver de transacciones sigue en 72.000 y la tabla oro en 30 filas, no el doble |
| Lanzar una ejecución con `p_confirmar_reemplazo = NO` | Falla antes de escribir; los conteos anteriores no cambian. Restaurar `SI` y recuperar |
| Documentar tres decisiones de calidad | Regla, decisión y razón, con sus propias palabras |
| Interpretar la tabla oro | Dos o tres líneas sobre la evolución por mes y por canal, sin atribuir causas: los datos son sintéticos |

Usar la [plantilla de evidencias](evidencias.md). La prueba negativa cambia un parámetro: **no se eliminan archivos ni tablas bronce**.

## 7. Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| Falla antes de escribir indicando una tabla bronce faltante o con otro conteo | Que la Sesión 2 terminó bien; reejecutar la ingesta antes que la plata |
| El nombre del Lakehouse no coincide | Lakehouse predeterminado de **este** notebook, parámetro `p_lakehouse_esperado` y reinicio de sesión |
| Falla por esquema de una tabla de destino | Evitar apuntar a un trabajo ajeno; usar un prefijo nuevo del laboratorio si corresponde |
| Falla por un registro con varios motivos o por un duplicado con contenido distinto | Verificar que los CSV originales no fueron editados; reponerlos y rehacer la ingesta |
| El endpoint SQL no muestra las tablas | Esperar la sincronización y refrescar; verificar que se abrió el endpoint del Lakehouse correcto |
| Funciona manualmente pero no en el pipeline | Dependencia On success, parámetros base, conexión y Lakehouse predeterminado de cada notebook |
| Ejecución en cola o lenta | Capacidad compartida y sesiones activas; coordinar con el administrador |

Un bloqueo de identidad, capacidad o configuración no se resuelve ampliando la sesión. El punto focal lo coordina con el administrador.

## Referencias

- [Actividad Notebook en Data Factory](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity).
- [SQL analytics endpoint de un Lakehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-sql-analytics-endpoint).
- [Warehouse y Lakehouse: guía de decisión](https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-lakehouse-warehouse).
- [Diccionario del dataset](../../dataset/diccionario.md) y [guía del dataset](../../dataset/README.md).

Los controles locales del repositorio no sustituyen la prueba de integración en el tenant del participante. La actividad Notebook, la autenticación, las escrituras Delta y el endpoint SQL deben comprobarse allí; el repositorio no se conecta a ningún tenant ni despliega artefactos automáticamente.
