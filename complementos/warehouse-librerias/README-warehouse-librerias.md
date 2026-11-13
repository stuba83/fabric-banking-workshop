# Demo del facilitador: Warehouse, bibliotecas compartidas y Spark frente a T-SQL

Material didáctico en español sobre **datos bancarios sintéticos** (las tablas plata/oro de la Sesión 3). Complementa la Sesión 3: su guía indica que la demostración de un Warehouse queda a cargo del facilitador y **no forma parte de las evidencias**. Es un **complemento opcional**: requiere una capacidad de pago (o Trial, si el tenant la ofrece) y el Lakehouse de la Sesión 3, y es apoyo didáctico, no una implementación productiva.

**Estado: verificado en un workspace de laboratorio (nov-2026; capacidad F32).** Todo se desplegó con `deploy.ps1` y se probó en el servicio: **T00–T13, C1–C3 y N1–N6 en OK** (sección 8). Las cifras y los tiempos son **valores observados, sin línea base**. Los hallazgos de esa verificación (dos construcciones de T-SQL que Fabric no admite) ya están corregidos en los archivos; la sección 9 separa lo verificado de lo que sigue sin verificar.

**Antes de desplegar:** el `.whl` de `fac_utils` **no se versiona** (la carpeta `dist\` está en `.gitignore`); se construye localmente con `python -m build --wheel` (sección 11). `deploy.ps1` exige `-WorkspaceName`: el nombre del workspace lo elige quien despliega (en el laboratorio, con el prefijo propio del participante) y debe contener el Lakehouse de la Sesión 3.

## 1. Objetivo didáctico

| Demo | Qué debe entender el participante | Archivos |
|---|---|---|
| **A. Warehouse** | Un Warehouse escribe con T-SQL y ofrece transacciones entre varias tablas; un procedimiento almacenado lee tablas del Lakehouse con nombre de tres partes, carga dos tablas de forma atómica, es idempotente y se concilia contra el origen. | `warehouse\` |
| **B. Bibliotecas** | Tres maneras de compartir las **mismas** funciones entre notebooks (notebook + `%run`, paquete en un Environment, módulo en Files) y cuándo conviene cada una. | `librerias\` |
| **C. Spark vs T-SQL** | La misma agregación en dos motores devuelve el mismo resultado; la elección se hace por equipo y carga, no por una cifra. Se mide en vivo, sin prometer resultados. | `comparacion\` |

Qué **no** es: un patrón productivo bancario. Los datos son ficticios; las simplificaciones se indican en cada archivo.

## 2. Contenido de la carpeta

```text
warehouse-librerias\
  README-warehouse-librerias.md        (este archivo)
  valores_esperados.json               valores del laboratorio recalculados con la implementación de referencia del repo
  warehouse\
    01_esquemas_tablas.sql             esquemas por dominio, tablas oro, llaves NOT ENFORCED (idempotente)
    02_procedimientos.sql              3 cargas atómicas + conciliación + orquestador (CREATE OR ALTER)
    03_pruebas.sql                     T00-T13: filas prueba | estado | detalle
    04_estado_inicial.sql              deja el Warehouse en el estado inicial de la demo (deploy.ps1 -RestablecerDemo)
    pipeline\FAC_PL_Gold_Warehouse.pipeline-content.json   plantilla con marcadores {{...}} (verificada en un workspace de laboratorio)
  librerias\
    fuente\funciones.py                FUENTE ÚNICA de las funciones
    B1_notebook_run\                   FAC_NB_Utils.ipynb + FAC_NB_Demo_Libreria_A.ipynb
    B2_paquete_environment\            fac_utils\ (pyproject, src, tests) + FAC_NB_Demo_Libreria_B.ipynb; el .whl se genera en dist\ (no se versiona)
    B3_modulo_files\                   fac_utils_lh.py + FAC_NB_Demo_Libreria_C.ipynb
  comparacion\                         FAC_NB_Spark_vs_TSQL.ipynb + comparacion_tsql.sql
  deploy\deploy.ps1                    despliegue idempotente con -WhatIf; exige -WorkspaceName
  herramientas\                        validadores, generador de variantes, prueba local del despliegue (servidor simulado en 127.0.0.1) y ejecutar_notebook.ps1
```

Convención de nombres: los elementos nuevos llevan prefijo `FAC_` (`FAC_WH_Gold`, `FAC_LH_Utils`, `FAC_ENV_Utils`, `FAC_NB_*`, `FAC_PL_Gold_Warehouse`). **No se modifica ningún `AB_*`**: `AB_Lakehouse` solo se lee. Los notebooks de demo A/B/C se llaman `…_Libreria_A/B/C` y corresponden a las variantes B1/B2/B3.

## 3. Decisiones y justificación

| Decisión | Justificación |
|---|---|
| El Warehouse vive en el **mismo workspace** que `AB_Lakehouse` y lo lee como `AB_Lakehouse.dbo.<tabla>`. | Learn: las consultas entre bases funcionan dentro del workspace activo y se referencian con nombre de tres partes (base.esquema.tabla). En un Lakehouse con esquemas, lo que Spark guarda sin esquema va a `dbo` (Learn, *Lakehouse schemas*); el endpoint de uno sin esquemas también lo publica en `dbo` (comportamiento habitual, que T01 comprueba): el nombre es igual en ambos casos. |
| Nombres **en minúsculas** y exactos (`AB_Lakehouse`, `ab_silver_…`). | La intercalación por defecto es `Latin1_General_100_BIN2_UTF8`, sensible a mayúsculas (Learn, *Collation*). El Warehouse y el endpoint deben tener la misma intercalación para consultas entre bases. |
| **MERGE sí está soportado** y es GA en Fabric Warehouse (Learn, *T-SQL surface area*, actualizado el 16-sep-2026). La referencia local lo marcaba «preview»: está desactualizada. | Se usa **MERGE en las dimensiones** (clave natural, pocas filas, la fuente es la verdad; `WHEN NOT MATCHED BY SOURCE THEN DELETE` refleja el origen) y **DELETE + INSERT…SELECT en hecho y resumen** (reemplazo completo de una instantánea recalculada; más simple que comparar 72.000 filas). `@estrategia` permite cambiar las dimensiones a `DELETE_INSERT` con el mismo resultado (prueba T07). |
| Concurrencia: serializar las cargas y reintentar. | Learn (*Transactions*): el bloqueo es **por tabla**; UPDATE/DELETE/MERGE simultáneos sobre la misma tabla dan error 24556/24706, y **incluso un MERGE que solo agrega** genera conflicto; los INSERT siempre crean archivos nuevos y conflictan menos (salvo con DDL). |
| Transacción explícita sobre **dos tablas** en cada procedimiento, con `TRY/CATCH`, `ROLLBACK` y `THROW;`. | Learn: transacciones ACID entre tablas; no hay transacciones anidadas ni savepoints, por eso el **orquestador no abre transacción propia**: cada hijo es atómico y la bitácora dice en qué paso falló; al ser idempotente basta reejecutar. |
| Sin `@@ROWCOUNT`, `XACT_STATE()`, `SET XACT_ABORT` ni **`ERROR_LINE()`**. | Los tres primeros no aparecen como soportados para Warehouse en Learn; `ERROR_LINE()` lo confirmó el servicio en la verificación (*FUNCTION 'ERROR_LINE' is not supported*). Las filas se cuentan con `COUNT_BIG(*)` dentro de la transacción y los errores se registran con `ERROR_NUMBER()` y `ERROR_MESSAGE()`. |
| Sin tablas `#temp` para mover datos (`INSERT … SELECT` hacia o desde una `#temp` con datos de otras tablas). | El servicio responde el error **15816** *«The query references an object that is not supported in distributed processing mode»* (hallazgo de la verificación). `INSERT … VALUES` y `SELECT` sobre una `#temp` sí funcionan. `usp_reconciliar` escribe directo en `operacion.reconciliacion`. |
| Llaves con `ALTER TABLE … NOT ENFORCED`, nunca dentro de `CREATE TABLE`. | Learn (*Table constraints*): no se pueden declarar inline; PK/UNIQUE exigen `NONCLUSTERED` + `NOT ENFORCED`. Son metadatos: **el motor no impide duplicados** (T12 lo demuestra y `usp_reconciliar` valida la integridad). |
| Solo tipos soportados: `varchar`, `datetime2(6)`, `decimal(18,2)`, `bigint`. | Learn (*Data types*): no hay `nvarchar`, `datetime`, `money` ni `tinyint` en tablas. |
| **Stored procedure activity** para el pipeline. | Learn (*Stored procedure activity*, actualizado el 19-jun-2026) lista **Fabric Data Warehouse** como destino soportado. La referencia local decía lo contrario: Learn tenía razón (**verificado**: la plantilla JSON se creó por API y el pipeline ejecutó el procedimiento). Alternativa no necesaria: actividad **Script**. |
| Una sola **fuente** de funciones (`librerias\fuente\funciones.py`) y un generador. | Garantiza que las tres variantes tienen las mismas funciones; una prueba compara byte a byte las copias y el contenido de `FAC_NB_Utils`. |
| `FAC_LH_Utils` (nuevo, con esquemas) para la bitácora y `Files/libs`. | `AB_Lakehouse` no se toca. Los notebooks leen `AB_Lakehouse` por ruta ABFSS con GUID (funciona con o sin esquemas) y **no** lo adjuntan como dependencia. |
| `deploy.ps1` ejecuta el SQL por **TDS con `System.Data.SqlClient`** y un token de `az` para `https://database.windows.net` (**verificado**, incluidas las lecturas entre bases). | ADO.NET (incluido en PowerShell 7) no exige instalar nada: ni `sqlcmd`, ni el módulo `SqlServer`, ni un controlador ODBC. Alternativas: `sqlcmd -G`, editor SQL del portal o la herramienta MCP `execute_query` (un lote por llamada, sin `GO`). |
| El Environment se carga con el `.whl` **dentro de la definición** y se publica con `?beta=false` (**verificado**). | Learn (*Environment public APIs*): la API de definición acepta `Libraries/CustomLibraries/*.whl`; la de carga directa quedó como plan B (`-EnvironmentModo Upload`, no probado). |

## 4. Demo A — Warehouse (`warehouse\`)

**Modelo (esquema por dominio).**

| Esquema | Tablas | Origen (Lakehouse `AB_Lakehouse`, esquema `dbo`) |
|---|---|---|
| `clientes` | `dim_sucursal`, `dim_cliente` | `ab_silver_sucursales`, `ab_silver_clientes` |
| `cuentas` | `dim_producto`, `dim_cuenta` | `ab_silver_productos`, `ab_silver_cuentas` |
| `transacciones` | `fact_transaccion`, `resumen_mes_canal` | `ab_silver_transacciones` y, para conciliar, `ab_gold_transacciones_mes_canal` |
| `operacion` | `bitacora_carga`, `reconciliacion` | — |

**Procedimientos.**

| Procedimiento | Qué hace |
|---|---|
| `clientes.usp_cargar_clientes` | `dim_sucursal` + `dim_cliente` en una transacción (`@estrategia` = `MERGE` o `DELETE_INSERT`). |
| `cuentas.usp_cargar_cuentas` | `dim_producto` + `dim_cuenta`, igual. |
| `transacciones.usp_cargar_transacciones` | `fact_transaccion` (DELETE + INSERT…SELECT) + `resumen_mes_canal` (recalculado desde el hecho en la **misma** transacción). `@simular_error = 1` lanza el error 51000 con el hecho ya insertado para mostrar el `ROLLBACK`. |
| `operacion.usp_reconciliar` | 26 controles en `operacion.reconciliacion`: conteos y sumas Lakehouse↔Warehouse, **cuadre del laboratorio**, valores publicados en la guía, integridad que el motor no valida y diferencias de contenido (`EXCEPT` en ambos sentidos). `@fallar_si_difiere = 1` lanza el error 51001. |
| `operacion.usp_cargar_gold` | Orquestador: dimensiones → hecho → conciliación; bitácora de INICIO/OK/ERROR con el paso que falló. Es el que invoca el pipeline. |

**Cuadre del laboratorio que debe reproducirse** (calculado con la implementación de referencia del repo sobre los CSV; ver `valores_esperados.json`):

```text
72.360 bronce - 288 duplicadas - 72 cuarentena = 72.000 transacciones plata = fact_transaccion
Créditos 14.976.153.627,79 CRC | Débitos 4.530.373.831,90 CRC | saldo inicial 2.306.760.167,48 CRC
resumen_mes_canal: 30 filas (6 meses x 5 canales) | consulta de negocio mes x provincia x canal: 210 grupos
```

**Idempotencia.** Una segunda ejecución deja los mismos conteos y sumas, y un solo `lote_id` en el hecho (T06). En las dimensiones con MERGE, las filas sin cambios conservan su `lote_id`; T08 deriva a propósito (valor cambiado, fila borrada, fila sobrante) y comprueba que MERGE lo corrige.

**Invocar desde un pipeline (actividad Stored procedure).** Configuración en el editor:

1. Nuevo pipeline `FAC_PL_Gold_Warehouse` → actividad **Stored procedure**.
2. **Settings → Connection:** *Fabric Data Warehouse* → `FAC_WH_Gold` (autenticación de la organización).
3. **Stored procedure name:** `[operacion].[usp_cargar_gold]` (botón *Import* trae los parámetros).
4. **Parameters:** `estrategia_dimensiones` (String) = `@pipeline().parameters.p_estrategia_dimensiones` (valor `MERGE`) y `simular_error` (Boolean) = `@pipeline().parameters.p_simular_error` (valor `false`).
5. Guardar y ejecutar. Éxito: actividad en verde y fila `OK` en `operacion.bitacora_carga`. Con `p_simular_error = true`: la actividad falla con el error 51000 y los conteos no cambian.

Hay una plantilla en `warehouse\pipeline\FAC_PL_Gold_Warehouse.pipeline-content.json` (`-DesplegarPipeline`). **Verificada en un workspace de laboratorio:** la estructura (`SqlServerStoredProcedure` + `linkedService` de tipo `DataWarehouse`) se creó por API sin cambios y el pipeline ejecutó `operacion.usp_cargar_gold` (éxito en 27 s; con `p_simular_error = true`, fallo con el error 51000 y conteos intactos). En el taller la idea es la misma de la Sesión 3: **el pipeline orquesta; el procedimiento transforma**.

## 5. Demo B — compartir código entre notebooks (`librerias\`)

Funciones idénticas en las tres variantes (`fuente\funciones.py`): `normalizar_columnas` (snake_case ASCII sin repetidas), `validar_rango_fechas` (nulos y fuera de rango en una pasada), `hash_fila` (SHA-256 de columnas; `hash_fila_python` aplica la misma regla y debe coincidir con `HASHBYTES('SHA2_256', CONCAT_WS('|', …))` de T-SQL, prueba T13), `escribir_bitacora` / `leer_bitacora` (tabla Delta `fac_bitacora_demo` en `FAC_LH_Utils`) y `leer_tabla_delta` (lee `AB_Lakehouse` por ABFSS, solo lectura). Límite conocido de `hash_fila`: un valor que contenga `|` puede colisionar.

### 5.1 `%run` frente a `notebookutils.notebook.run` (demo A)

| | `%run FAC_NB_Utils` | `notebookutils.notebook.run("FAC_NB_Utils", 120, {…})` |
|---|---|---|
| Contexto | **Mismo contexto**: lo definido en el referido queda disponible. | Se ejecuta y **devuelve solo el valor de `exit()`** (texto; `""` si no hay). |
| Parámetros | JSON con `int`, `float`, `bool`, `string`. | Diccionario; el hijo necesita una celda de parámetros. |
| Alcance | Mismo workspace; anidamiento hasta 5; sin recursión. | También entre workspaces; admite `runMultiple` y DAG. |
| Lakehouse | El del llamador. | El hijo debe usar el mismo Lakehouse, heredarlo o no definir ninguno (o `useRootDefaultLakehouse: True`). Por eso `FAC_NB_Utils` **no** define Lakehouse. |
| Cuándo | **Compartir funciones.** | **Orquestar** pasos, paralelizar o recibir un resultado. |

Reglas de Learn que se respetan: no llamar `exit()` dentro de `try/except`; no usar `%pip` en una ejecución de referencia. Demostración en `FAC_NB_Demo_Libreria_A` (**verificada en un workspace de laboratorio**): tras `notebook.run`, `"normalizar_columnas" in globals()` es `False`; tras `%run`, `True`. El `FAC_NB_Utils` sin Lakehouse predeterminado se pudo llamar desde un padre con `FAC_LH_Utils` como predeterminado.

### 5.2 Comparativa de las tres variantes

Las cifras de tiempo son **las que cita Learn**, no mediciones propias; mídalas en vivo (celdas incluidas).

| Aspecto | A. Notebook (`%run`) | B. Paquete en Environment | C. Módulo en Files (`sys.path`) |
|---|---|---|---|
| Uso | `%run FAC_NB_Utils` | `import fac_utils` con el Environment adjunto | `sys.path.insert(0, "/lakehouse/default/Files/libs")` + `import` |
| Tiempo de arranque | Sin cambio en el arranque; el costo es el del `%run` (celdas de medición). | Learn: **Full mode** publica en 3–6 min y suma 1–3 min al arranque de la sesión; **Quick mode** publica en ~5 s e instala al iniciar la sesión; Full + *custom live pool* ≈ 5 s de arranque. | Sin cambio; el costo es importar el archivo (celda de medición). |
| Publicación | No hay: se guarda el notebook. | Sí: publicar el Environment tras cada cambio (y tras cada sincronización con Git). | No hay: se sobrescribe el archivo (`importlib.reload` o reiniciar el intérprete). |
| Versionado | Como cualquier notebook (Git y *deployment pipelines* de Fabric). Sin número de versión propio. | Versión del `.whl` (aquí `0.1.0` = `__version__`); el Environment también va a Git (bibliotecas y cómputo). | Manual (nombre de archivo o carpeta): **Git del Lakehouse solo registra metadatos, no el contenido de Files** (Learn). |
| Git | Sí (elemento Notebook). | Sí, con límites: publicar tras sincronizar; 150 MB por *commit*. | No para el contenido de Files. |
| Reproducibilidad | Media: depende del notebook guardado. | Alta: Learn recomienda el Environment para pipelines por su estabilidad. | Baja: archivo mutable. |
| Límites | Mismo workspace; anidamiento ≤ 5. | Requiere publicar y esperar; Quick mode solo en notebooks, no en Spark job definitions. | Requiere Lakehouse predeterminado montado; `sys.path` solo afecta al **driver** (UDF de Python que importen el módulo no lo verían en los executors: validar en vivo). |
| Cuándo | Prototipos y equipos pequeños; código que cambia cada hora. | Código estable compartido por varios notebooks y pipelines; ambientes reproducibles. | Mientras no hay paquete; scripts pequeños junto a los datos; demos rápidas. |

**Observado en un workspace de laboratorio (nov-2026)** (F32, sesión *starter pool*, mismo cuerpo de 14 celdas en B y C; n pequeño; valores observados, sin línea base: tómense como órdenes de magnitud, no como promesa):

| Medida | Resultado |
|---|---|
| Publicación del Environment `FAC_ENV_Utils` (un `.whl`, modo Full) | **4 min 24 s** (20:05:15Z → 20:09:39Z); el segundo despliegue lo detectó publicado y no hizo nada |
| Duración del trabajo completo (arranque de sesión + 14 celdas) | **C (Files):** 33,5 / 37,9 / 33,5 / 36,0 s · **B (Environment):** 65,0 / 62,6 / 62,6 s · **A (`%run` + `run`):** 51,2 / 55,3 s |
| Diferencia por tener Environment (B frente a C) | **≈ +27 a +30 s** en el arranque de la sesión para un paquete mínimo (Learn habla de +1 a +3 min en Full mode según el tamaño de las dependencias) |
| Importación A: `%run FAC_NB_Utils` | **1,02 s** (1,017 / 1,022; incluye el paso entre celdas) |
| Importación A: `notebookutils.notebook.run` | **13,9 s** (13,91 / 13,83): el hijo se ejecuta como una llamada aparte con su propio *snapshot* |
| Importación B: `import fac_utils` | **0,001 a 0,002 s** (el paquete ya está instalado al arrancar la sesión: el costo se pagó en la publicación y en el arranque) |
| Importación C: `import fac_utils_lh` (sys.path) | **0,268 s** la primera vez (Python compila el `.py`) y **0,08 s** después |

Lectura honesta: el costo cambia de lugar. A paga en cada ejecución (`%run`), B paga en la publicación y en el arranque de cada sesión, C casi no paga pero no ofrece versionado ni reproducibilidad.

Otras opciones que Learn describe y no se desarrollan aquí: `%pip install` en línea (por sesión; desactivado por defecto en pipelines), carpetas de recursos del notebook/Environment (`%run -b script.py`) y *workspace default environment*.

**Cómo medir en vivo.** Cada demo tiene su celda: A = `time.perf_counter()` alrededor de `notebook.run` y entre celdas `%run` (incluye el paso entre celdas); B = `import fac_utils` (primera importación de la sesión; el arranque con Environment se ve en el *Monitoring hub* con el `applicationId` que imprime); C = `import fac_utils_lh`. Los tiempos quedan en `fac_bitacora_demo`.

## 6. Demo C — Spark frente a T-SQL (`comparacion\`)

Misma pregunta: por mes, provincia (de la sucursal) y canal, transacciones, créditos, débitos y ticket promedio (une transacciones → cuentas → clientes → sucursales; 210 grupos).

| Variante | Dónde |
|---|---|
| Spark SQL sobre las tablas plata del Lakehouse | `FAC_NB_Spark_vs_TSQL.ipynb` |
| T-SQL en el Warehouse | el mismo notebook (conector `synapsesql` con consulta de paso) y `comparacion_tsql.sql` |
| T-SQL sobre el endpoint SQL del Lakehouse | opcional, en ambos |

Qué se mide y cómo leerlo: repeticiones (la primera aparte), `SYSUTCDATETIME()` en T-SQL y `perf_counter` en Spark; el tiempo del servidor sale de `queryinsights.exec_requests_history` por etiqueta `FAC_CMP_*` (puede tardar hasta 15 minutos en aparecer, Learn). El notebook **verifica que los tres motores devuelvan los mismos grupos y montos** y falla si no. No hay conclusión automática de «quién gana».

**Observado en un workspace de laboratorio** (`FAC_NB_Spark_vs_TSQL`, 3 repeticiones; valores observados, sin línea base; el `assert` de igualdad pasó: los tres motores devolvieron los mismos 210 grupos y montos):

| Variante | Cliente, repeticiones 1 / 2 / 3 | Servidor (`queryinsights`) |
|---|---|---|
| Spark SQL sobre tablas plata del Lakehouse | 7,32 / 1,61 / 1,63 s | — |
| T-SQL en `FAC_WH_Gold` vía conector Spark | 6,09 / 3,59 / 0,99 s | **46–106 ms** por consulta |
| T-SQL en el endpoint del Lakehouse vía conector Spark | 1,47 / 1,50 / 1,23 s | — |
| T-SQL en `FAC_WH_Gold` desde el editor (`comparacion_tsql.sql`, solo cómputo) | 110 / 106 / 166 ms | 203 y 149 ms (consulta suelta) |
| T-SQL en el endpoint desde el editor | 121 / 157 / 140 ms | 227 y 127 ms (consulta suelta) |

Qué enseña, sin veredicto: (1) la primera ejecución es la «fría»; (2) **dentro de Spark, el tiempo del conector (segundos) es casi todo transferencia y arranque, no cómputo del servidor (decenas de milisegundos)**: comparar «Spark frente a T-SQL» con el reloj del cliente mezcla cosas distintas; (3) con 72.000 filas todo es rápido: la diferencia relevante no está aquí. Observación: el conector envuelve la consulta en `SELECT * FROM ( … )`, por eso la consulta de paso no lleva `ORDER BY` ni `OPTION`. Dentro de un bucle de un solo lote, `total_elapsed_time_ms` de `queryinsights` es **acumulado desde el inicio del lote** (119 → 351 → 674 ms frente a 110 / 106 / 166 ms medidos por el cliente): use los tiempos del cliente para el bucle y `queryinsights` para consultas independientes.

## 7. Guion de 10 minutos para la Sesión 3 (recomendado tras la verificación)

**Qué mostrar EN VIVO y qué dejar PREEJECUTADO.** Lo que tarda y no enseña nada nuevo se muestra ya ejecutado; lo rápido y determinista se ejecuta en vivo.

| Parte | Cómo | Por qué |
|---|---|---|
| Warehouse (`EXEC operacion.usp_cargar_gold`, `@simular_error = 1`, reconciliación) | **En vivo** | La orquestación completa tarda unos **12 s** (según la bitácora de una corrida por pipeline) y el rollback es instantáneo. |
| Pipeline `FAC_PL_Gold_Warehouse` | **Lanzar en vivo y explicar mientras corre** (27 s con éxito; 17 s con el error simulado) | Cabe en el tiempo y muestra la actividad Stored procedure. |
| Notebooks A, B, C y Spark frente a T-SQL | **Preejecutados**, con la sesión iniciada y las salidas visibles | Cada trabajo tarda de 35 a 65 s por el arranque de Spark; no publicar el Environment en vivo (4 min 24 s). |

Preparación: capacidad activa; `deploy.ps1 -RestablecerDemo` (deja el Warehouse en estado inicial: 72.000 / 30 filas, una corrida en la bitácora); ejecutar una vez cada notebook y dejar abiertas las salidas; no proyectar la columna `usuario` de `operacion.bitacora_carga` (guarda la identidad de quien ejecuta).

| Min | Qué se muestra | Mensaje |
|---|---|---|
| 0:00–1:30 | Workspace: `AB_Lakehouse` y `FAC_WH_Gold`; esquemas `clientes`, `cuentas`, `transacciones`, `operacion`. | Lakehouse: Spark y endpoint SQL de solo lectura. Warehouse: T-SQL con escritura y transacciones entre tablas. |
| 1:30–4:00 | Código de `transacciones.usp_cargar_transacciones` (nombre de tres partes, `BEGIN TRANSACTION`, DELETE + INSERT, `ROLLBACK`). `EXEC operacion.usp_cargar_gold` y leer las 26 filas de reconciliación: **72.360 − 288 − 72 = 72.000**. | Se concilia contra el origen; el cuadre de la sesión se reproduce en el Warehouse. |
| 4:00–5:30 | `EXEC transacciones.usp_cargar_transacciones @simular_error = 1` → error 51000; conteos sin cambio. Repetir `usp_cargar_gold`: mismos números. | Atomicidad (dos tablas, todo o nada) e idempotencia. |
| 5:30–6:30 | Lanzar `FAC_PL_Gold_Warehouse` (27 s) y mostrar la actividad Stored procedure. | El pipeline orquesta; el procedimiento transforma. |
| 6:30–8:00 | Salidas ya ejecutadas de `FAC_NB_Demo_Libreria_A`: `notebook.run` (≈ 14 s, sin funciones) frente a `%run` (≈ 1 s, con funciones); tabla 5.2: Environment (publicar 4 min 24 s, +≈ 28 s al arrancar, import 0,002 s) y Files (import 0,08 s, sin versionado). | Compartir código: dónde vive, cómo se versiona y cuánto cuesta. |
| 8:00–9:30 | Salida de `FAC_NB_Spark_vs_TSQL`: mismos 210 grupos en tres motores; primera repetición frente a las siguientes; servidor frente a cliente. | Mismo resultado en tres motores; el reloj del cliente no mide el motor. |
| 9:30–10:00 | Guía de decisión Lakehouse/Warehouse (enlace) y recordatorio: **no forma parte de las evidencias**. | Cierre. |

## 8. Verificación en un workspace de laboratorio (nov-2026)

Verificado en un workspace de laboratorio, con la sesión de Azure CLI de quien desplegó (el script nunca ejecuta `az login`). Capacidad F32 activa durante todo el ciclo (no se pausó, reanudó ni escaló). Resultados y tiempos son **valores observados, sin línea base**.

| # | Prueba | Resultado | Evidencia |
|---|---|---|---|
| P0 | Validadores locales + prueba del despliegue con servidor simulado | **OK** | `generar_variantes --check`, `validar_sql` (5 archivos, 40 lotes), `validar_notebooks`, 13 pruebas unitarias (1 omitida sin PySpark), `probar_deploy_local.ps1` (3 escenarios) |
| P1 | `deploy.ps1 -WhatIf` contra el servicio | **OK** | Solo lecturas; capacidad `Active`; lista las 10 acciones |
| P2a | Despliegue: Lakehouse (con esquemas), Warehouse, Environment, 5 notebooks, módulo en Files | **OK** | Creados en la primera pasada; el `.whl` y el Environment publicados en 4 min 24 s |
| P2b | `03_pruebas.sql` T00–T13 | **OK (14/14)** en la primera pasada completa tras los arreglos y otra vez en la segunda | T00 esquemas=4, tablas=8, procedimientos=5 · T01 72.000 filas leídas de `AB_Lakehouse.dbo.ab_silver_transacciones` · T12 `PRIMARY KEY NOT ENFORCED` acepta el duplicado (8 filas dentro de la transacción, 7 tras el ROLLBACK) · T13 `HASHBYTES` coincide 3 de 3 con `hash_fila` |
| P2c | Cuadre del laboratorio y reconciliación | **OK** | T05: 72.360 − 288 − 72 = 72.000 = `fact_transaccion`; 26 controles OK (créditos 14.976.153.627,79; débitos 4.530.373.831,90; saldo inicial 2.306.760.167,48; resumen 30 filas; 0 diferencias de contenido con `EXCEPT` en ambos sentidos) |
| P2d | Atomicidad | **OK** | T02 sobre tablas **vacías**: error 51000 y hecho 0 → 0 (sin ROLLBACK habría quedado con 72.000 filas); T11 con datos: 72.000 / 30 y mismo `lote_id` |
| P2e | Idempotencia y estrategias | **OK** | T06 (segunda carga: mismos conteos, 1 solo lote) · T07 (`DELETE_INSERT` = `MERGE`) · T08 (MERGE corrige valor cambiado, fila borrada y fila sobrante) |
| P2f | `comparacion_tsql.sql` C1–C3 | **OK** | 210 grupos, 72.000 transacciones, totales del laboratorio; Warehouse = endpoint (0 filas distintas) |
| P3 | Segundo despliegue (idempotencia) | **OK** | No creó nada; `FAC_ENV_Utils` «sin cambios»; notebooks y pipeline «actualizado» |
| N1 | `FAC_NB_Demo_Libreria_A` | **OK** | Bitácora: `funciones_visibles_tras_notebook_run: false`, `funciones_visibles_tras_run: true`, fechas 72.000/0/0, `hash_tres_primeras_ok: true`, 72.000 hashes distintos |
| N2 | `FAC_NB_Demo_Libreria_B` (Environment) | **OK** | `environment_id` adjunto, `fac_utils 0.1.0`, mismo resumen; 3 ejecuciones |
| N3 | `FAC_NB_Demo_Libreria_C` (Files + sys.path) | **OK** | Importa desde `/lakehouse/default/Files/libs/fac_utils_lh.py`; mismo resumen; 4 ejecuciones |
| N4 | `FAC_NB_Spark_vs_TSQL` | **OK** | `assert` de igualdad entre 3 motores superado; tiempos en la sección 6 |
| N5 | Pipeline `FAC_PL_Gold_Warehouse` | **OK** | `p_simular_error=false`: Completed en 27 s, bitácora INICIO→OK. `true`: Failed en 17 s con `Sql error number: 51000`, bitácora ERROR con el paso, conteos sin cambio |
| N6 | Medición de importación y arranque | **OK** | Sección 5.2 |
| — | Alternativas: actividad **Script**, `-EnvironmentModo Upload`, Quick mode, *custom live pool* | **OMITIDA** | No hicieron falta; no se probaron |

### Bugs encontrados y corregidos durante la verificación

1. **`ERROR_LINE()` no está soportada** (`FUNCTION 'ERROR_LINE' is not supported`): rompía los tres procedimientos de carga. Se quitó (se conservan `ERROR_NUMBER()` y `ERROR_MESSAGE()`) y `validar_sql.py` la rechaza.
2. **Error 15816 con tablas `#temp`**: `usp_reconciliar` y el bucle de `comparacion_tsql.sql` hacían `INSERT … SELECT` hacia/desde una `#temp`. Ahora la conciliación escribe directo en `operacion.reconciliacion` y la comparación agrega a variables (solo los tiempos usan `INSERT … VALUES` en una `#temp`). El validador rechaza ese patrón.
3. **Python dejaba `Files/libs/__pycache__`** al importar el módulo: el notebook C fija `sys.dont_write_bytecode = True` y se borró el archivo.
4. **El endpoint SQL de `FAC_LH_Utils` no mostraba la bitácora** hasta sincronizar: `-RefrescarEndpoint` ahora también sincroniza ese endpoint.
5. **Instrumentación**: los notebooks escriben sus verificaciones y tiempos en `fac_bitacora_demo`, porque un trabajo no devuelve las salidas de las celdas.
6. **`deploy.ps1`**: nuevo `-RestablecerDemo` (ejecuta `04_estado_inicial.sql`); el registro del último despliegue se guarda en la carpeta temporal del sistema en lugar de la carpeta del demo (no contiene secretos, pero sí el identificador del workspace). Nuevo `herramientas\ejecutar_notebook.ps1` (ejecuta un `FAC_NB_*` como trabajo y espera).

Declaración: en la segunda pasada completa se usó `-RefrescarEndpoint`, que pidió la **sincronización de metadatos del SQL endpoint de `AB_Lakehouse`** (no cambia datos ni definición, pero es una llamada sobre un elemento `AB_*`). Además, a lo largo de la verificación `AB_Lakehouse` solo se leyó (OneLake y T-SQL).

## 9. Qué quedó verificado y qué no

**Verificado en el servicio**
- `AB_Lakehouse` **no** tiene esquemas habilitados (no expone `defaultSchema`): las 22 tablas están planas en `Tables/` y el endpoint las publica en `dbo`; `AB_Lakehouse.dbo.ab_*` funciona desde el Warehouse. `leer_tabla_delta` resuelve ambos casos por ABFSS.
- TDS con `System.Data.SqlClient` y token de `https://database.windows.net`; lecturas entre bases por TDS; `INSERT … SELECT`, `MERGE` (con `WHEN NOT MATCHED BY SOURCE`) y `EXCEPT` entre el Warehouse y el endpoint.
- Soportadas: `sys.schemas`, `sys.tables`, `sys.procedures`, `OBJECT_ID`, `sp_executesql`, `CREATE OR ALTER PROCEDURE`, `COUNT_BIG(DISTINCT …)`, `CONVERT(…, 2)`, `HASHBYTES`, `CONCAT_WS`, `NEWID`, `SUSER_SNAME`, `TRUNCATE TABLE`, `THROW`, `@@TRANCOUNT`, `OPTION (LABEL=…)`. **No soportadas:** `ERROR_LINE()` y `INSERT … SELECT` entre `#temp` y otras tablas.
- Dentro de una transacción se leen las propias escrituras (el resumen se calcula desde el hecho recién insertado); `CREATE TABLE` y `ALTER TABLE … ADD CONSTRAINT` en el mismo lote.
- Plantilla JSON del pipeline (`SqlServerStoredProcedure` + `linkedService` de tipo `DataWarehouse`): creada por API y ejecutada.
- Definición del Environment con el `.whl`, publicación con `?beta=false`; notebooks con `dependencies` de Lakehouse y Environment; parte `notebook-content.ipynb`; subida a Files por la API de OneLake.
- `notebook.run` frente a `%run`; la consulta de paso del conector (`synapsesql`) con comentario inicial y sin `ORDER BY`.
- Intercalación de los endpoints: `Latin1_General_100_BIN2_UTF8`; las consultas entre bases funcionaron sin errores.

**Sigue sin verificar (o no se probó)**
1. Quick mode del Environment, *custom live pool* y el efecto del tamaño del paquete en el arranque (solo se midió un `.whl` mínimo, n pequeño, con otras cargas posibles en el mismo workspace).
2. La actividad **Script** y `-EnvironmentModo Upload` como alternativas.
3. La parte `artifact.content.ipynb` de la documentación (no hizo falta).
4. Que `sys.path` solo afecte al driver (UDF de Python que importen el módulo en los executors).
5. Cuál de los dos caminos usó `leer_tabla_delta` para el endpoint de OneLake (`notebookutils.conf` o el respaldo): ambos funcionan.
6. Versión exacta del runtime de Spark (el `.pyc` generado indica Python 3.13).
7. Concurrencia: dos cargas simultáneas sobre la misma tabla (error 24556/24706 según Learn) no se provocaron.

## 10. Riesgos restantes y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Arranque de Spark en la sesión en vivo (de 15 a 65 s por trabajo) y la capacidad compartida. | Notebooks preejecutados; la parte T-SQL en vivo (12 s). |
| Publicar el Environment tarda minutos (4 min 24 s con un `.whl`). | Publicar el día anterior; el despliegue lo detecta y no repite. |
| Cargas simultáneas sobre la misma tabla (error 24556/24706). | Una ejecución a la vez; reintentar; no programar el pipeline en recurrencia durante el taller. |
| El endpoint SQL tarda en ver tablas nuevas. | `-RefrescarEndpoint`, o esperar. |
| Sensibilidad a mayúsculas (BIN2). | Nombres exactos en minúsculas; `AB_Lakehouse` con esa grafía. |
| `operacion.bitacora_carga.usuario` guarda la identidad de quien ejecuta. | No proyectar esa columna en la demo; limpiar con `04_estado_inicial.sql`. |
| Llaves `NOT ENFORCED` dan falsa seguridad. | T12 lo demuestra; `usp_reconciliar` valida duplicados y huérfanos. |
| Los tiempos se leen como veredicto. | Sección 6: el cliente mide transferencia y arranque; el servidor, decenas de milisegundos; mismo resultado en tres motores. |
| El `.whl` y el módulo divergen de la fuente. | `generar_variantes.py --check`; si cambia `__version__`, reconstruir el `.whl` y volver a desplegar. |
| Datos de organizaciones reales. | Todo es sintético y genérico. |

## 11. Reconstruir, redesplegar y restablecer (referencia rápida)

Requisitos: PowerShell 7 (`pwsh`) y Azure CLI con la sesión ya iniciada por quien despliega (`az login` previo; los scripts usan la sesión actual y nunca inician sesión). `-AzureConfigDir` es opcional y solo sirve para apuntar a otro perfil de Azure CLI. **`-WorkspaceName` es obligatorio**: el nombre lo elige quien despliega.

```powershell
$ws = 'MI-WORKSPACE'   # nombre del workspace (lo elige quien despliega; en el laboratorio, con el prefijo propio)

# 1) Construir el .whl (no se versiona; dist\ está en .gitignore)
python -m pip install build
Set-Location .\librerias\B2_paquete_environment\fac_utils
python -m build --wheel --outdir ..\dist                                         # después borre build\ y src\*.egg-info
Set-Location ..\..\..                                                            # de vuelta a la carpeta de este README

# 2) Desplegar y probar
pwsh -File .\deploy\deploy.ps1 -WorkspaceName $ws -WhatIf                                    # solo lecturas
pwsh -File .\deploy\deploy.ps1 -WorkspaceName $ws -EjecutarPruebas -RestablecerDemo          # despliega, prueba T00-T13 y deja el estado inicial
pwsh -File .\deploy\deploy.ps1 -WorkspaceName $ws -DesplegarPipeline -RefrescarEndpoint      # pipeline y sincronización de endpoints
pwsh -File .\herramientas\ejecutar_notebook.ps1 -WorkspaceName $ws -Nombre FAC_NB_Demo_Libreria_A

# 3) Validaciones locales (sin Fabric ni red)
python .\herramientas\calcular_esperados.py --repo <ruta-del-repo-del-taller>   # solo lee el repo; debe coincidir con valores_esperados.json
python .\herramientas\generar_variantes.py --check                              # copias y notebooks generados = fuente única
python .\herramientas\validar_sql.py ; python .\herramientas\validar_notebooks.py
pwsh -File .\herramientas\probar_deploy_local.ps1                               # despliegue contra un servidor simulado en 127.0.0.1 (requiere el .whl)
```

## 12. Referencias (URL con respuesta HTTP 200 verificada el 12-nov-2026)

**Warehouse y T-SQL**
- [Consultar el Warehouse y consultas entre bases](https://learn.microsoft.com/en-us/fabric/data-warehouse/query-warehouse)
- [Superficie T-SQL soportada](https://learn.microsoft.com/en-us/fabric/data-warehouse/tsql-surface-area)
- [Transacciones](https://learn.microsoft.com/en-us/fabric/data-warehouse/transactions) · [Tablas](https://learn.microsoft.com/en-us/fabric/data-warehouse/tables) · [Llaves](https://learn.microsoft.com/en-us/fabric/data-warehouse/table-constraints) · [Tipos de datos](https://learn.microsoft.com/en-us/fabric/data-warehouse/data-types) · [Intercalación](https://learn.microsoft.com/en-us/fabric/data-warehouse/collation) · [Conectividad](https://learn.microsoft.com/en-us/fabric/data-warehouse/connectivity) · [Query Insights](https://learn.microsoft.com/en-us/fabric/data-warehouse/query-insights)
- [MERGE (Fabric)](https://learn.microsoft.com/en-us/sql/t-sql/statements/merge-transact-sql?view=fabric) · [THROW](https://learn.microsoft.com/en-us/sql/t-sql/language-elements/throw-transact-sql?view=fabric) · [TRY…CATCH](https://learn.microsoft.com/en-us/sql/t-sql/language-elements/try-catch-transact-sql?view=fabric)
- [Actividad Stored procedure](https://learn.microsoft.com/en-us/fabric/data-factory/stored-procedure-activity) · [Conector de Data Warehouse](https://learn.microsoft.com/en-us/fabric/data-factory/connector-data-warehouse-overview)
- [Lakehouse frente a Warehouse: guía de decisión](https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-lakehouse-warehouse)

**Lakehouse y Spark**
- [Esquemas del Lakehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-schemas) · [SQL analytics endpoint](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-sql-analytics-endpoint) · [Git y despliegue del Lakehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-git-deployment-pipelines)
- [Conector Spark para Data Warehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/spark-data-warehouse-connector) · [Notebooks T-SQL](https://learn.microsoft.com/en-us/fabric/data-engineering/author-tsql-notebook)

**Bibliotecas, Environments y notebooks**
- [Administrar bibliotecas de Spark](https://learn.microsoft.com/en-us/fabric/data-engineering/library-management) · [Bibliotecas en un Environment](https://learn.microsoft.com/en-us/fabric/data-engineering/environment-manage-library) · [Crear y usar un Environment](https://learn.microsoft.com/en-us/fabric/data-engineering/create-and-use-environment) · [Environment con Git y despliegue](https://learn.microsoft.com/en-us/fabric/data-engineering/environment-git-and-deployment-pipeline) · [API públicas del Environment](https://learn.microsoft.com/en-us/fabric/data-engineering/environment-public-api)
- [Ejecutar un notebook desde otro (`%run`)](https://learn.microsoft.com/en-us/fabric/data-engineering/author-execute-notebook) · [`notebookutils.notebook.run`](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run) · [`notebookutils.lakehouse`](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-lakehouse) · [`notebookutils.runtime`](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-runtime) · [Git y despliegue de notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-source-control-deployment)

**API REST y OneLake**
- [Publicar un Environment](https://learn.microsoft.com/en-us/rest/api/fabric/environment/items/publish-environment) · [Actualizar la definición de un Environment](https://learn.microsoft.com/en-us/rest/api/fabric/environment/items/update-environment-definition) · [Cargar una biblioteca personalizada](https://learn.microsoft.com/en-us/rest/api/fabric/environment/staging/upload-custom-library)
- [Crear un notebook](https://learn.microsoft.com/en-us/rest/api/fabric/notebook/items/create-notebook) · [Obtener un Warehouse](https://learn.microsoft.com/en-us/rest/api/fabric/warehouse/items/get-warehouse) · [Refrescar metadatos del endpoint SQL](https://learn.microsoft.com/en-us/rest/api/fabric/sqlendpoint/items/refresh-sql-endpoint-metadata) · [API de acceso a OneLake](https://learn.microsoft.com/en-us/fabric/onelake/onelake-access-api)
