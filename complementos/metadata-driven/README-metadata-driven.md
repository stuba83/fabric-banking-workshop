# Ingesta metadata-driven con carga completa e incremental (marca de agua)

Demo didáctica para un taller de Microsoft Fabric con **datos bancarios sintéticos**. Un facilitador muestra, en unos 10 minutos, cómo **un solo pipeline y un solo cuaderno** cargan varias tablas porque un **catálogo** describe qué se carga y cómo, y cómo una **marca de agua** hace que el incremental cargue solo lo nuevo.

> Es un recurso de práctica, no una implementación de producción. No usa datos reales ni conexiones externas, y no toca los elementos `AB_*` del laboratorio: todo lo nuevo lleva el prefijo `FAC_` (elementos) o `fac_` (tablas). Es un **complemento opcional del facilitador**: no forma parte de las evidencias de las sesiones y requiere una capacidad de pago (o Trial, si el tenant la ofrece) con el Lakehouse de la Sesión 2.

## 1. Objetivo didáctico

Al terminar, la audiencia puede explicar:

1. **Metadata-driven:** el pipeline no "sabe" qué tablas hay; las lee del catálogo (`fac_catalogo_ingesta`). Agregar una tabla es agregar una fila.
2. **Completa vs. incremental:** las maestras se reemplazan enteras; las transacciones se cargan solo desde la última marca (`columna_marca > ultima_marca`).
3. **Idempotencia y trazabilidad:** reejecutar no duplica (MERGE por llave) y la bitácora dice qué pasó en cada corrida.
4. **Seguridad (solo explicación):** dónde entraría Azure Key Vault y dónde se desplegaría una gateway.

## 2. Contenido

| Archivo | Para qué sirve |
|---|---|
| `FAC_NB_Preparar_Control.ipynb` | Crea (idempotente) `fac_catalogo_ingesta` y `fac_bitacora_ingesta`, siembra el catálogo, copia el CSV de transacciones a la carpeta de entrada de la demo y, según `accion`, **genera el archivo de incremento** o **reinicia** la demo |
| `FAC_NB_Carga_Generica.ipynb` | Cuaderno parametrizado que carga cualquier fila del catálogo: lee, filtra por marca, escribe Delta, calcula la marca, registra bitácora, actualiza el catálogo y sale con un JSON |
| `FAC_NB_Resumen_Bitacora.ipynb` | Paso final: muestra bitácora, marca de agua y filas por corrida; **falla** si hay errores o faltan tablas |
| `FAC_NB_Leer_Catalogo.ipynb` | Variante alternativa: devuelve el catálogo activo y ordenado por `exitValue` |
| `pipeline/FAC_PL_Ingesta_Metadata.json` | Pipeline **principal**: Lookup → ForEach secuencial → Notebook genérico → resumen |
| `pipeline/FAC_PL_Ingesta_Metadata.alt-notebook.json` | Pipeline **alternativo**: Notebook lector → ForEach → Notebook genérico → resumen |
| `deploy/deploy.ps1` | Despliegue idempotente por REST; exige `-WorkspaceName`; admite `-WhatIf`, `-Run`, `-RunPreparar` |

Las referencias a `workspaceId`, `notebookId` y `lakehouseId` del pipeline son marcadores `{{...}}` que `deploy.ps1` sustituye.

## 3. Flujo

```text
  FAC_NB_Preparar_Control          (una vez; "incremento"; "reiniciar")
            |
            | crea y siembra
            v
  fac_catalogo_ingesta  <-----------------------------------------+
  (qué, cómo y última marca)                                      |  MERGE de ultima_marca
            |                                                     |  (solo si la escritura salió bien)
            v                                                     |
  +-- FAC_PL_Ingesta_Metadata ----------------------------+      |
  |  parámetros: forzar_completa, filtro_tabla, destino   |      |
  |                                                       |      |
  |  Lookup (catálogo, modo Tabla)                        |      |
  |      |                                                |      |
  |      v                                                |      |
  |  ForEach SECUENCIAL  --item()-->  IfCondition         |      |
  |                                   (activo = 1 y       |      |
  |                                    filtro_tabla)      |      |
  |                                        |              |      |
  |                                        v              |      |
  |                       Notebook FAC_NB_Carga_Generica -+------+
  |                          1 leer origen (CSV a texto)  |
  |                          2 [incremental] marca > ultima_marca
  |                          3 completa: overwrite        |
  |                             incremental: MERGE insert-only por llave
  |                          4 nueva marca, bitácora, exit(JSON)
  |      |                                                |
  |      v  (aunque el ForEach falle: "Completed")        |
  |  Notebook FAC_NB_Resumen_Bitacora                     |
  +-------------------------------------------------------+
            |
            v
  fac_bitacora_ingesta  (una fila por corrida y tabla)  +  fac_bronze_*  (con _fac_run_id)
```

Tablas del catálogo semilla: `fac_bronze_sucursales` (7), `fac_bronze_productos` (5), `fac_bronze_clientes` (1.200) como **completa**; `fac_bronze_transacciones` como **incremental** (`fecha_hora` / `transaccion_id`); `fac_bronze_calendario` **inactiva** (`activo = 0`) para mostrar que el catálogo puede apagar una tabla sin tocar el pipeline.

## 4. Decisiones de diseño

| Decisión | Por qué |
|---|---|
| Orígenes = CSV de la Sesión 1 (`Files/bronze/banca_sintetica`) | La demo se apoya en lo que el participante ya tiene; no depende de conexiones externas |
| Las **maestras** se leen directo de la ruta de la Sesión 1; las **transacciones** de `Files/fac_demo/entrada/transacciones/` (copia) | No se modifica el original (la Sesión 2 verifica su hash) y el incremental necesita una carpeta donde "lleguen" archivos nuevos |
| Tablas en esquema `fac` si el Lakehouse tiene esquemas; si no, sin esquema | Los cuadernos usan `destino = auto` (SHOW SCHEMAS) y `deploy.ps1` lo resuelve con la propiedad `defaultSchema` del Lakehouse. **`AB_Lakehouse` no tiene esquemas**: las tablas quedan como `fac_*` (sin `fac.`) |
| **Completa = `overwrite`** | Son tablas pequeñas; se quiere una foto fiel y que reejecutar dé el mismo resultado. Si el origen viene vacío **no** se sobrescribe |
| **Incremental = `MERGE` insert-only por llave**, no `append` | Escribir y avanzar la marca no es atómico: si falla entre ambos pasos, la siguiente corrida relee las mismas filas. Con `append` se duplicarían; con el MERGE las existentes se ignoran. Insert-only porque los movimientos aplicados no cambian |
| Columna extra `columna_clave` en el catálogo | Sin llave no hay MERGE idempotente |
| La **marca se calcula solo sobre fechas válidas** (`try_to_timestamp`) | El dataset trae 24 fechas imposibles (`2026-09-31T25:61:00`); como texto serían la "máxima" y corromperían la marca |
| Filtro estricto `>` | Es la regla clásica; limitación conocida: una fila tardía con la misma marca exacta no entraría (en producción se reprocesa una ventana de seguridad apoyada en el MERGE) |
| Lookup en **modo Tabla** (principal) | Lee el Delta directo: sin conexión adicional, sin preview y sin la latencia de sincronización del endpoint SQL. Costo: no admite `WHERE`/`ORDER BY`, así que el filtro de activas va en un `IfCondition` y el orden es el físico |
| Variante con **notebook lector** (alternativa) | Da filtro y orden garantizados y ninguna latencia de sincronización; cuesta una sesión Spark más |
| **No** se usó el modo "T-SQL Query (Preview)" del Lookup | Lee por el endpoint SQL del Lakehouse (puede ir por detrás de lo que Spark acaba de escribir: justo lo que esta demo hace en cada corrida) y exige una conexión creada aparte, lo que impide un despliegue por script |
| ForEach **secuencial** (`isSequential: true`; `batchCount` solo aplica en paralelo) | Todas las iteraciones escriben en las mismas tablas Delta de control (MERGE concurrente puede chocar), la capacidad del laboratorio es pequeña y en el monitor se ve en orden y un fallo se aísla fácil |
| Si una tabla falla: **bitácora primero, luego el cuaderno falla** | El pipeline lo muestra en rojo y aun así queda constancia |
| `Resumen_Bitacora` depende del ForEach con **Completed** y falla ante errores | Si no fallara, el pipeline podría terminar en verde con una tabla rota |
| Columnas `_fac_run_id` y `_fac_cargado_en` en cada tabla destino | Se ve qué corrida cargó cada fila (útil en la demo) |
| Los campos vacíos del CSV se conservan como texto vacío (`na.fill("")` tras leer) | Coherencia con bronce de la Sesión 2: Spark los lee como NULL (un CSV no tiene NULL). Un primer intento con `nullValue` centinela **no funcionó** (en la verificación) |

## 5. Guion de demo (10 minutos)

**Antes de la sesión (no cuenta en los 10 minutos):** capacidad activa; `deploy.ps1` ejecutado; `FAC_NB_Preparar_Control` ejecutado con `accion = preparar` (o `reiniciar` si se repite la demo); **corrida 1 ya ejecutada** (ver abajo).

**Tiempos observados en un workspace de laboratorio (nov-2026; capacidad F32, runtime 2.0, Starter Pool). Son valores observados, sin línea base: no son una promesa de rendimiento.**

| Acción | Tiempo de reloj |
|---|---|
| Corrida 1 completa (4 cargas + resumen) | **5,7 a 7,3 min** (1,3 a 1,5 min en cola `NotStarted` + 4,2 a 5,8 min en ejecución) |
| Corrida con `filtro_tabla` a una tabla (1 carga + resumen) | **2,5 a 3,3 min** |
| `FAC_NB_Preparar_Control` (`preparar`, `incremento`, `reiniciar`) | ~1 min |
| Cada actividad Notebook dentro del pipeline | 22 a 40 s de trabajo propio + ~25 a 30 s de arranque de una sesión Spark nueva |

En el workspace de laboratorio donde se midió, el modo de alta concurrencia para pipelines estaba **desactivado** (`notebookPipelineRunEnabled = false`), así que el `sessionTag` `fac_ingesta` no reutiliza sesión y cada actividad paga su arranque. No se cambió la configuración y **no se probó** si activarla acorta la corrida; es la primera mejora a intentar.

**Recomendación para la demo en vivo de 10 minutos:** **pre-ejecutar la corrida 1** (no cabe en directo: 6 a 7 min) y mostrar su historial y su bitácora; en vivo, usar `filtro_tabla = fac_bronze_transacciones` en las corridas 2 y 3 (~2,5 a 3 min cada una, tiempo que se aprovecha para explicar) e iniciar el incremento (~1 min) mientras termina la corrida 2. La corrida 2 sin filtro (para contrastar que las maestras sí se reescriben) solo cabe si se activa la alta concurrencia.

| Min | Acción | Qué se ve | Resultado esperado |
|---|---|---|---|
| 0:00–1:30 | Explicar la idea y abrir el catálogo (`display(spark.table("fac.fac_catalogo_ingesta"))` o el Paso 8 de Preparar) | 5 filas; `tipo_carga`, `columna_marca`, `ultima_marca` **vacía**; `calendario` con `activo = 0` | "El pipeline no sabe qué cargar: el catálogo se lo dice" |
| 1:30–3:30 | **Corrida 1** (completa), **ya ejecutada antes**: abrir su historial en el monitor | Lookup → ForEach (4 cargas, `calendario` se omite) → Resumen | Bitácora: sucursales 7/7, productos 5/5, clientes 1.200/1.200, **transacciones 72.360 leídas y 72.360 escritas**; `marca_despues` = `2026-09-30T22:57:33`; el mensaje avisa de **24 fechas inválidas** excluidas de la marca |
| 3:30–4:30 | **Corrida 2, sin datos nuevos**: ejecutar de nuevo (si hay tiempo, sin filtro, para contrastar; si no, `filtro_tabla = fac_bronze_transacciones`) | Las maestras se reescriben; transacciones: `SIN_DATOS` | **Transacciones: 0 leídas, 0 escritas**, marca igual |
| 4:30–5:30 | **Llega un incremento**: ejecutar Preparar con `accion = incremento`, `numero_incremento = 1` | Archivo `transacciones_incremento_01.csv` en la carpeta de entrada | 48 filas, del 1 al 3 de octubre de 2026 (fechas posteriores a la marca) |
| 5:30–7:00 | **Corrida 3** (con `filtro_tabla = fac_bronze_transacciones` para ir rápido) | Solo la actividad de transacciones | **48 leídas, 48 escritas**; marca = `2026-10-03T21:58:53` |
| 7:00–8:30 | **Bitácora y marca**: ejecutar `FAC_NB_Resumen_Bitacora` con `run_id` vacío (modo consulta: resume la última corrida y solo revisa errores) | Bitácora de la última corrida, catálogo con la marca avanzada y filas por `_fac_run_id` | Tabla de transacciones con **72.408** filas: 72.360 de la corrida 1 y 48 de la 3 |
| 8:30–9:30 | *(Opcional)* **Idempotencia**: en una celda, `UPDATE fac.fac_catalogo_ingesta SET ultima_marca = '' WHERE tabla_destino = 'fac_bronze_transacciones'` y volver a ejecutar | Mensaje "N filas ya existían" | **72.408 leídas, 0 escritas**: sin duplicados |
| 9:30–10:00 | Cierre con las diapositivas de la sección 7 | — | Qué cambiaría con un origen relacional real |

Sin esquemas en el Lakehouse, las consultas usan el nombre de tabla sin `fac.`.

## 6. Reiniciar la demo

1. Abrir `FAC_NB_Preparar_Control`, poner `accion = "reiniciar"` y ejecutar todo.
2. Qué hace: elimina **solo** las tablas `fac_bronze_*` del catálogo, vacía catálogo y bitácora, borra los `transacciones_incremento_*.csv` y vuelve a sembrar el catálogo. No toca los CSV de la Sesión 1 ni el archivo base copiado.
3. Para volver a mostrar el incremento: `accion = "incremento"` (el mismo número genera el mismo archivo; otro número, otro lote con fechas posteriores).
4. Para quitar todo al final: borrar a mano los cinco elementos `FAC_*` y el esquema `fac` (opcional). Nada de `AB_*` se ve afectado. Cuando se acabe el taller, **pausar la capacidad**.

Desde la línea de comandos: `.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -RunPreparar -Accion reiniciar` (`$ws` es el nombre del workspace, como en la sección 9).

## 7. Solo explicación (diapositivas): Key Vault y gateway

**Dónde entraría Key Vault.** Esta demo lee archivos del propio Lakehouse, así que no hay credenciales. Con un origen relacional real, la contraseña **no** va en el cuaderno, en el catálogo ni como parámetro del pipeline; el catálogo guardaría, como mucho, el *nombre* del secreto. El cuaderno genérico trae una celda titulada «Dónde entra Key Vault (ilustrativo, no se ejecuta)» con la lectura del secreto con `notebookutils.credentials.getSecret(akvName, secret)` (el primer argumento es la URL completa del vault, `https://<nombre>.vault.azure.net/`; usa la identidad que ejecuta el cuaderno, que necesita permiso de lectura) y una lectura JDBC con el predicado incremental empujado al origen. Aparte, las conexiones de Fabric pueden tomar credenciales de Key Vault mediante *Azure Key Vault references*.

**Dónde se desplegaría la gateway.** Según Microsoft Learn, los pipelines de Data Factory en Fabric y Copy job pueden leer orígenes locales detrás de un firewall o dentro de una red virtual mediante una **gateway de datos local** (software que se instala en la red local y solo requiere conexiones salientes) o una **gateway de datos de red virtual** (servicio administrado, sin instalar nada); la gateway se elige en la **conexión** que usa la actividad. Un cuaderno de Spark abre su propia conexión de red desde el cómputo de Fabric, así que el origen debe ser alcanzable por red desde Fabric (por ejemplo, con un endpoint permitido por el firewall del origen o un endpoint privado administrado). Para orígenes relacionales con carga incremental, **Copy job** ofrece copia incremental por marca de agua gestionada por el propio servicio. Qué opción conviene depende de la red, del origen y de las políticas de cada organización: se confirma en su entorno; aquí no se promete compatibilidad con ningún conector concreto.

## 8. Verificación en un workspace de laboratorio (nov-2026)

Verificado en un workspace de laboratorio (Lakehouse `AB_Lakehouse`, capacidad F32, runtime 2.0). Las cifras y los tiempos son **valores observados, sin línea base**; en otro entorno pueden variar. Todo lo creado lleva prefijo `FAC_` (elementos) o `fac_` (tablas) y no se tocó ningún `AB_*`.

### 8.1 Pruebas 0 a 13

| # | Prueba | Resultado | Evidencia |
|---|---|---|---|
| 0 | `-WhatIf` | **OK** | Resolvió IDs, detectó que el Lakehouse **no tiene esquemas** (sin `defaultSchema`), cinco líneas «What if», cero escrituras |
| 1 | Despliegue y repetición | **OK** | 1.ª vez: 4 notebooks + pipeline creados (105 s). Repetición completa: «Actualizar definición» ×5, ningún elemento nuevo (96 s) |
| 2 | Preparar | **OK** | Job `Completed`; `exitValue`: 5 filas de catálogo con marcas vacías, `calendario` con `activo = 0`, `filas_bitacora = 0`, `transacciones_base.csv` en la carpeta de entrada |
| 3 | Corrida 1 | **OK** | Sucursales 7/7, productos 5/5, clientes 1.200/1.200, transacciones **72.360/72.360**, marca `2026-09-30T22:57:33`, «24 filas con fecha inválida»; `Resumen` con `problemas: []`. Repetida tras reiniciar: mismas cifras |
| 4 | Corrida 2 | **OK** (tras corregir el bug 1) | Transacciones `SIN_DATOS`, **0/0**, marca sin cambios. Solo con `filtro_tabla`; la variante sin filtro: **OMITIDA** (tiempo) |
| 5 | Incremento | **OK** | `exitValue.incremento`: 48 filas, `2026-10-01T06:00:47` a `2026-10-03T21:58:53` |
| 6 | Corrida 3 | **OK** | **48/48**, `marca_antes = 2026-09-30T22:57:33`, `marca_despues = 2026-10-03T21:58:53` |
| 7 | Tablas | **OK** | `fac_bronze_transacciones` = **72.408** filas; dos grupos de `_fac_run_id` (72.360 y 48); 72.120 ids distintos (72.072 + 48: los duplicados se conservan); columnas sin BOM; marca en el catálogo. Comprobado con un cuaderno temporal (ya eliminado) y con el `exitValue` del resumen; **no** se consultó el endpoint SQL |
| 8 | Idempotencia | **OK** | Cuaderno genérico lanzado con `ultima_marca` vacía: **72.408 leídas, 0 escritas**, «72408 filas ya existían»; la tabla siguió en 72.408 (confirma además que el MERGE insert-only tolera las 288 llaves repetidas) |
| 9 | Completa forzada | **OK** | 72.408/72.408 `overwrite`, marca `2026-10-03T21:58:53`, tabla en 72.408 |
| 10 | Errores controlados | **OK** | (a) `filtro_tabla = 'no_existe'`: `Resumen_Bitacora` falla («no hay tablas activas que coincidan») y el pipeline termina `Failed`. (b) Origen inexistente: job `Failed`, fila `ERROR` en la bitácora (`FileNotFoundError`). Además, el bug 1 fue un caso real: `Cargar_Tabla` `Failed`, `ERROR` en bitácora, `Resumen` `Failed`, pipeline `Failed` y marca intacta |
| 11 | Variante alternativa | **OK** | `Leer_Catalogo` devolvió 4 tablas activas ordenadas 10 a 40 (sin `calendario`); el pipeline alternativo `Completed` con `forzar_completa` y filtro (72.408/72.408). Sin filtro: **OMITIDA** |
| 12 | Reiniciar | **OK** | Catálogo con 5 filas y marcas vacías, bitácora en 0, tablas `fac_bronze_*` eliminadas, solo `transacciones_base.csv`; repetir la corrida 1 dio los mismos números |
| 13 | Aislamiento | **OK** | 15 elementos `AB_*` antes y después; tablas `ab_bronze_*` con sus conteos de la Sesión 2 (1.200, 1.800, 7, 5, 183 y 72.360) |

### 8.2 Bugs encontrados y corregidos

| # | Bug | Corrección |
|---|---|---|
| 1 | El pipeline entregaba `ultima_marca` al cuaderno como `2026-09-30T22:57:33Z` (con `Z`) y el cuaderno la rechazaba | `normalizar_marca` tolera `Z`, `+00:00` y fracciones de segundo |
| 2 | Los campos vacíos del CSV llegaban como NULL (el `nullValue` con centinela no sirvió: 360 `canal` NULL) | Tras leer el CSV se rellena con `''`; verificado: 360 vacíos y 0 NULL |
| 3 | `deploy.ps1` buscaba `exitValue` en la raíz de la respuesta | Está en `properties.exitValue` del job de notebook |
| 4 | `deploy.ps1` esperaba el `Retry-After` de 60 s entre consultas de estado | Consulta cada 8 s (`-PollSegundos`) |
| 5 | `-RunNotebook` sin parámetros fallaba (índice nulo) | Corregido |

Mejoras añadidas a `deploy.ps1`: `-RunNotebook` y `-NotebookParametros` (ejecuta cualquier `FAC_NB_*` y muestra su `exitValue`), `-SoloNotebooks` y `-SinPipeline` (iterar más rápido). `FAC_NB_Resumen_Bitacora` ahora incluye en su `exitValue` el total de filas de transacciones, las filas por corrida y las marcas del catálogo.

### 8.3 Supuestos que quedaron resueltos

| Supuesto | Resultado |
|---|---|
| ¿`AB_Lakehouse` tiene esquemas? | **No**: las tablas son `fac_*` (sin `fac.`) |
| BOM de los CSV | Bien tratado: `transaccion_id` sin carácter extra |
| Fecha imposible `2026-09-31T25:61:00` | `try_to_timestamp` da NULL; la marca fue `2026-09-30T22:57:33` |
| MERGE insert-only con llaves repetidas | Funciona (corrida 1 y prueba 8) |
| Lookup en modo Tabla con conexión «en línea» | Aceptado; `activo` llega numérico y los textos vacíos como texto; devuelve datos recién escritos. **Su orden es el físico y cambia** (tras reiniciar llegó invertido): la demo no depende del orden |
| Parámetros de la API de jobs | Aceptados en el primer intento: `parameters[]` en `notebooks/.../jobs/execute/instances?beta=false` y `executionData.parameters` para pipelines |
| Parte `notebook-content.ipynb` y formato `ipynb` | Aceptados sin reintentos |
| `output.result.exitValue` | Funciona (variante alternativa y `Show-ActivityRuns`) |
| Resultado del cuaderno por API | En `properties.exitValue` del job instance |

### 8.4 Riesgos restantes y lo que sigue sin verificar

- **Alta concurrencia para pipelines**: desactivada en el workspace; no se probó su efecto en los tiempos ni el `sessionTag`.
- **Corrida 2 sin filtro** (contraste con las maestras) y **variante alternativa sin filtro**: no ejecutadas por separado (tiempo).
- **Endpoint SQL del Lakehouse**: no se consultó; su latencia de sincronización sigue sin medirse.
- **Orden del Lookup** (modo Tabla): no garantizado; si se necesita, usar la variante alternativa.
- Las filas con fecha imposible se cargan en la carga inicial y después nunca vuelven a leerse; la capa plata de la Sesión 3 debe tratarlas.
- Datos del incremento fuera del período original (octubre de 2026): la capa plata de la Sesión 3 podría rechazarlos por rango de fechas; solo se usan en esta demo.
- Modificar a mano el catálogo en vivo puede cambiar lo que se carga; reiniciar la demo lo restituye.

### 8.5 Estado final del workspace

Elementos creados (los de esta demo): `FAC_NB_Preparar_Control`, `FAC_NB_Carga_Generica`, `FAC_NB_Leer_Catalogo`, `FAC_NB_Resumen_Bitacora` y `FAC_PL_Ingesta_Metadata` (variante **Lookup**). En `AB_Lakehouse`: tablas `fac_catalogo_ingesta` (5 filas, marcas vacías) y `fac_bitacora_ingesta` (vacía), y el archivo `Files/fac_demo/entrada/transacciones/transacciones_base.csv`. Las tablas `fac_bronze_*` no existen (la demo se reinició) y el cuaderno temporal de verificación se eliminó. Listo para arrancar desde la corrida 1.

## 9. Cómo repetir el despliegue y las pruebas

Los comandos de esta sección son los que se ejecutaron en la verificación (resultados en la sección 8). **Requisitos:** PowerShell 7 (`pwsh`); Azure CLI con la sesión ya iniciada por quien despliega (`az login` hecho antes: el script usa la sesión actual y **nunca** ejecuta `az login` ni `az account set`; `-AzureConfigDir` es opcional y solo sirve para apuntar a otro perfil de Azure CLI); un workspace con capacidad activa y un Lakehouse llamado `AB_Lakehouse` (o el que se indique con `-LakehouseName`; en el laboratorio, con el prefijo propio del participante). **`-WorkspaceName` es obligatorio**: el nombre lo elige quien despliega. Todas las llamadas a `api.fabric.microsoft.com` llevan `x-ms-fabric-skill: spark-cli` (cambiable con `-SkillHeader`). Ejecutar desde la carpeta que contiene este archivo, en una sesión de `pwsh`:

```powershell
$ws = 'MI-WORKSPACE'   # nombre del workspace donde se despliega (lo elige quien despliega)

# 0) Ensayo: resuelve IDs y detecta esquemas; no crea nada
.\deploy\deploy.ps1 -WorkspaceName $ws -WhatIf

# 1) Despliegue (idempotente: repetirlo actualiza, no duplica)
.\deploy\deploy.ps1 -WorkspaceName $ws

# 2) Preparar catálogo, bitácora y carpeta de entrada
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -RunPreparar -Accion preparar

# 3) Corrida 1 (completa)
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -Run

# 4) Corrida 2 (sin datos nuevos)
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -Run -RunParametros @{ filtro_tabla = 'fac_bronze_transacciones' }

# 5) Llega el incremento 1 y 6) Corrida 3
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -RunPreparar -Accion incremento -NumeroIncremento 1
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -Run -RunParametros @{ filtro_tabla = 'fac_bronze_transacciones' }

# 9) Carga completa forzada
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -Run -RunParametros @{ forzar_completa = $true; filtro_tabla = 'fac_bronze_transacciones' }

# 11) Variante alternativa (sustituye la definición del mismo pipeline; -SoloNotebooks acelera) y de vuelta a la principal
.\deploy\deploy.ps1 -WorkspaceName $ws -Variante Notebook -SoloNotebooks FAC_NB_Leer_Catalogo
.\deploy\deploy.ps1 -WorkspaceName $ws -Variante Lookup

# Cualquier notebook FAC_NB_* con parámetros; muestra su exitValue (JSON). Ejemplo: idempotencia (prueba 8)
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -RunNotebook FAC_NB_Carga_Generica -NotebookParametros @{ tabla='fac_bronze_transacciones'; ruta_origen='Files/fac_demo/entrada/transacciones/'; formato='csv'; tipo_carga='incremental'; columna_marca='fecha_hora'; columna_clave='transaccion_id'; ultima_marca=''; run_id='prueba-idempotencia' }

# 12) Reiniciar
.\deploy\deploy.ps1 -WorkspaceName $ws -SkipDeploy -RunPreparar -Accion reiniciar
```

`-Run` muestra el resultado de cada actividad con su `exitValue` (el JSON de cada carga); `-RunPreparar` y `-RunNotebook` muestran el `exitValue` del notebook. Códigos de salida: `0` correcto, `1` si el job no terminó en `Completed`. Para comprobar tablas, usar Spark SQL (sesión Livy o cuaderno) o el endpoint SQL del Lakehouse, **recordando su latencia de sincronización**:

```sql
SELECT * FROM fac.fac_bitacora_ingesta ORDER BY inicio;
SELECT orden, tabla_destino, tipo_carga, ultima_marca, activo FROM fac.fac_catalogo_ingesta ORDER BY orden;
SELECT _fac_run_id, COUNT(*) AS filas FROM fac.fac_bronze_transacciones GROUP BY _fac_run_id;
```

(`AB_Lakehouse` no tiene esquemas: usar los nombres sin `fac.`.)

| # | Prueba | Criterio de éxito |
|---|---|---|
| 0 | `-WhatIf` | Resuelve workspace y Lakehouse, informa el esquema detectado y muestra cinco líneas «What if» (4 notebooks + 1 pipeline); **cero** escrituras |
| 1 | Despliegue y repetición | Primera vez: 4 notebooks `FAC_NB_*` y `FAC_PL_Ingesta_Metadata` creados. Segunda vez: «Actualizar definición» ×5 y **ningún elemento nuevo**. Ningún `AB_*` modificado. El pipeline abre en el editor sin errores de validación |
| 2 | Preparar | Job `Completed`; `exitValue` con 5 filas de catálogo (`ultima_marca` vacías, `calendario` `activo = 0`), `filas_bitacora = 0` y `transacciones_base.csv` en la carpeta de entrada |
| 3 | Corrida 1 | Pipeline `Completed`. Cuatro `Cargar_Tabla` en `Succeeded` (sin `calendario`) con estado `OK`: sucursales 7/7, productos 5/5, clientes 1.200/1.200, transacciones **72.360/72.360**, `marca_despues = 2026-09-30T22:57:33`, mensaje con «24 filas con fecha inválida». `Resumen_Bitacora` `Succeeded` con `problemas: []` |
| 4 | Corrida 2 | Transacciones: estado `SIN_DATOS`, **0/0**, marca sin cambios. Con la corrida sin filtro, las maestras se reescriben con los mismos conteos |
| 5 | Incremento | Job `Completed`; `exitValue.incremento` con **48 filas**, primera `2026-10-01T06:00:47`, última `2026-10-03T21:58:53` |
| 6 | Corrida 3 | Transacciones: `OK`, **48 leídas / 48 escritas**, `marca_antes = 2026-09-30T22:57:33`, `marca_despues = 2026-10-03T21:58:53` |
| 7 | Tablas | `fac_bronze_transacciones` = **72.408** filas; `GROUP BY _fac_run_id` da dos grupos (72.360 y 48); catálogo con la marca `2026-10-03T21:58:53`; bitácora sin filas en `ERROR` |
| 8 | Idempotencia | Con `UPDATE ... SET ultima_marca = ''` (cuaderno/Livy) y una corrida de transacciones: **72.408 leídas, 0 escritas**, mensaje «filas ya existían», tabla sigue en 72.408 |
| 9 | Completa forzada | `forzar_completa = true`: transacciones **72.408/72.408**, `marca_despues = 2026-10-03T21:58:53`, tabla en 72.408 |
| 10 | Errores controlados | (a) `filtro_tabla = 'no_existe'`: `Resumen_Bitacora` **falla** («no hay tablas activas que coincidan») y el pipeline termina en `Failed`. (b) Con un `ruta_origen` inexistente en el catálogo: `Cargar_Tabla` en `Failed`, fila `ERROR` en la bitácora, marca intacta; `accion = preparar` restituye la ruta |
| 11 | Variante alternativa | Con `-Variante Notebook`, repetir 3 y 6: mismos resultados; `Leer_Catalogo` devuelve en `exitValue` las tablas activas ordenadas (sucursales, productos, clientes, transacciones) |
| 12 | Reiniciar | Catálogo con 5 filas y marcas vacías, bitácora en 0, tablas `fac_bronze_*` inexistentes, sin archivos de incremento; repetir 3 da los mismos números |
| 13 | Aislamiento | Los elementos `AB_*` y las tablas `ab_*` siguen igual (mismos conteos, sin versiones nuevas) |

**Éxito global:** pruebas 0 a 13 cumplidas, o desviaciones documentadas con su causa. Si 3 o 4 fallan por el Lookup (formato de la conexión en línea, tipos o datos viejos), repetirlas con `-Variante Notebook` antes de depurar.

## 10. Referencias (URL verificadas, respuesta HTTP 200 el 12 de noviembre de 2026)

**Pipelines y actividades**

- Actividad Lookup: https://learn.microsoft.com/en-us/fabric/data-factory/lookup-activity
- Actividad ForEach: https://learn.microsoft.com/en-us/fabric/data-factory/foreach-activity
- Actividad Notebook (parámetros base y `sessionTag`): https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity
- Actividad If Condition: https://learn.microsoft.com/en-us/fabric/data-factory/if-condition-activity
- Parámetros: https://learn.microsoft.com/en-us/fabric/data-factory/parameters
- Lenguaje de expresiones: https://learn.microsoft.com/en-us/fabric/data-factory/expression-language
- Lakehouse como origen y destino (modo Tabla / T-SQL Query): https://learn.microsoft.com/en-us/fabric/data-factory/connector-lakehouse-copy-activity
- Modo de alta concurrencia para notebooks: https://learn.microsoft.com/en-us/fabric/data-engineering/configure-high-concurrency-session-notebooks

**NotebookUtils y Lakehouse**

- `notebookutils.credentials` (`getSecret`): https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-credentials
- `notebookutils.notebook` (`run`, `exit`): https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run
- `notebookutils.fs`: https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-file-system
- Contexto del runtime: https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-runtime
- Esquemas de Lakehouse: https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-schemas
- Comparación de métodos de ingesta: https://learn.microsoft.com/en-us/fabric/data-engineering/load-data-lakehouse

**Gateways, Key Vault y Copy job (solo explicación)**

- Acceso a datos locales desde Data Factory en Fabric: https://learn.microsoft.com/en-us/fabric/data-factory/how-to-access-on-premises-data
- Gateway de datos local: https://learn.microsoft.com/en-us/data-integration/gateway/service-gateway-onprem
- Gateway de datos de red virtual: https://learn.microsoft.com/en-us/data-integration/vnet/overview
- Conectores de Copy job: https://learn.microsoft.com/en-us/fabric/data-factory/copy-job-connectors
- Copy job (carga incremental por marca de agua y CDC): https://learn.microsoft.com/en-us/fabric/data-factory/what-is-copy-job
- Endpoints privados administrados: https://learn.microsoft.com/en-us/fabric/security/security-managed-private-endpoints-overview
- Referencias de Azure Key Vault en conexiones: https://learn.microsoft.com/en-us/fabric/data-factory/azure-key-vault-reference-configure

**API REST de Fabric (usada por `deploy.ps1`)**

- Definición de DataPipeline: https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/datapipeline-definition
- Definición de Notebook: https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/notebook-definition
- Create Item: https://learn.microsoft.com/en-us/rest/api/fabric/core/items/create-item
- Update Item Definition: https://learn.microsoft.com/en-us/rest/api/fabric/core/items/update-item-definition
- Run On Demand Item Job: https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/run-on-demand-item-job
- Get Item Job Instance: https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/get-item-job-instance
- Get Lakehouse (`defaultSchema`): https://learn.microsoft.com/en-us/rest/api/fabric/lakehouse/items/get-lakehouse
- API REST de pipelines de Data Factory: https://learn.microsoft.com/en-us/fabric/data-factory/pipeline-rest-api
- API pública de notebooks (valor de salida en jobs): https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-public-api
- Ejecutar notebook bajo demanda: https://learn.microsoft.com/en-us/rest/api/fabric/notebook/background-jobs/run-on-demand-notebook

**Arquitectura**

- Arquitectura medallion en un Lakehouse: https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture
