# Dataset sintético bancario para el entrenamiento de Microsoft Fabric

**Etapa:** Ingeniería de datos  
**Versión:** 1.0 — 22 de octubre de 2026  
**Período de transacciones:** 1 de abril al 30 de septiembre de 2026  
**Moneda:** CRC (colón costarricense)  
**Naturaleza:** Datos totalmente ficticios para uso didáctico.

Este paquete simula clientes, productos, cuentas, transacciones y una cartera de créditos de una entidad financiera ficticia. **No contiene datos de ninguna entidad real ni representa arquitecturas, productos, sucursales o carteras reales.** No incluye cédulas, teléfonos, correos, números bancarios reales ni credenciales. Los nombres de provincias son referencias geográficas públicas.

## Objetivo y alcance

Contar con un hilo conductor para recorrer ingesta, limpieza y transformación, modelado y creación de reportes en Power BI. El núcleo del laboratorio está en **clientes, productos, cuentas y transacciones**; sucursales y calendario complementan el análisis.

La cartera de créditos es un archivo opcional para explorar en otros ejercicios; no es necesaria para la Sesión 1. El paquete no requiere streaming, Real-Time Intelligence, Copilot ni conexiones a sistemas de una organización.

## Contenido

| Archivo | Filas | Uso |
|---|---:|---|
| `csv\clientes.csv` | 1.200 | Clientes ficticios, segmento, grupo de edad y sucursal |
| `csv\sucursales.csv` | 7 | Sucursales ficticias, una por provincia |
| `csv\productos.csv` | 5 | Tres productos de cuentas y dos de crédito |
| `csv\cuentas.csv` | 1.800 | Cuentas asociadas a clientes y productos; saldo al inicio del período |
| `csv\transacciones.csv` | 72.360 | Movimientos para ingesta bronce, con anomalías intencionales |
| `csv\creditos.csv` | 400 | Foto de cartera al 30 de septiembre de 2026; uso opcional |
| `csv\calendario.csv` | 183 | Calendario diario del período, para análisis temporal |
| `diccionario.md` | — | Columnas, tipos, claves y reglas de negocio |
| `manifiesto.json` | — | Semilla, conteos, hashes SHA-256 y valores de control |
| `generar_dataset.py` | — | Generador reproducible; no hace falta ejecutarlo para usar los CSV |
| `validar_dataset.py` | — | Validador independiente de integridad y reglas del dataset |

## Formato de los archivos

- CSV separado por comas, con encabezados `snake_case` y codificación **UTF-8 con BOM**.
- Fechas: `yyyy-MM-dd`. Fecha y hora: `yyyy-MM-ddTHH:mm:ss`.
- Las horas son locales de Costa Rica (`America/Costa_Rica`, UTC-6), sin sufijo de zona horaria. Interpretarlas en esa zona; no asumir que son UTC.
- Importes con punto decimal, dos decimales y sin separador de miles: `125000.50`. Usar `decimal(18,2)`, no tipos de punto flotante, para operaciones monetarias.
- Todos los importes están en CRC; no se requiere conversión de moneda.
- Los identificadores son texto. Ejemplos: `CLI000001`, `CTA000001`, `TX00000001`, `PRE000001`. No representan números bancarios.
- Los campos vacíos en `canal` son intencionales. El resto de las anomalías se detalla más abajo.

## Preparación en Fabric

1. Descargar el repositorio y localizar la carpeta `dataset`. Conservar los CSV sin modificarlos: serán la fuente bronce del laboratorio.
2. Usar el workspace compartido del entrenamiento. Cada participante crea su carpeta individual y utiliza su propia nomenclatura para los artefactos.
3. Crear dentro de esa carpeta un Lakehouse identificado, por ejemplo `AB_Lakehouse`, y cargar los siete CSV en su área **Files**, en una subcarpeta como `bronze/banca_sintetica`. Esa ruta corresponde al almacenamiento del Lakehouse, no a la carpeta de organización del workspace.
4. Verificar encabezados y número de registros después de la carga. En bronce conviene conservar los campos como texto para no perder los errores que deben detectarse.
5. Crear las tablas plata aplicando los tipos y reglas del diccionario; registrar por separado los duplicados y las filas en cuarentena.
6. Conectar el modelo semántico a las tablas depuradas y crear los reportes con la licencia **Power BI Pro** de cada participante.

El participante no necesita instalar Python ni ejecutar los generadores en su computadora: los CSV ya vienen preparados. El código se incluye para reproducibilidad.

## Calidad de datos: anomalías deliberadas

Las tablas de referencia no contienen errores deliberados. Las anomalías se concentran en `transacciones.csv` para practicar un flujo de calidad reproducible:

| Caso | Cantidad | Tratamiento esperado |
|---|---:|---|
| Movimientos base válidos y únicos | 72.000 | Conservar, normalizando el canal cuando corresponda |
| Copias exactas de movimientos existentes | 288 filas adicionales | Deduplicar por `transaccion_id`, tras comprobar que los contenidos coinciden |
| Cuenta inexistente | 24 filas adicionales | Cuarentena: referencia inválida |
| Fecha y hora inválida | 24 filas adicionales | Cuarentena: fecha no interpretable |
| Monto negativo | 24 filas adicionales | Cuarentena: monto no permitido |
| Canal con espacios y/o minúsculas | 720 movimientos base | Recortar espacios y convertir a mayúsculas |
| Canal vacío | 360 movimientos base | Clasificar como `NO_INFORMADO`, conservando el movimiento |

Los tres grupos que van a cuarentena no se solapan entre sí. Las alteraciones de canal tampoco se solapan entre sí; sus filas siguen siendo válidas una vez normalizadas. Los duplicados son copias de movimientos sin alteraciones de canal.

**Resultado esperado:** 72.360 filas bronce − 288 duplicados − 72 filas en cuarentena = **72.000 transacciones plata**. Normalizar los 1.080 canales indicados no reduce el número de filas.

No corregir un monto negativo cambiándole el signo ni inventar una cuenta para salvar una referencia: esos registros deben separarse para revisión.

## Relaciones y métricas

Relaciones de origen:

- `sucursales.sucursal_id` → `clientes.sucursal_id`.
- `clientes.cliente_id` → `cuentas.cliente_id` y `creditos.cliente_id`.
- `productos.producto_id` → `cuentas.producto_id` y `creditos.producto_id`.
- `cuentas.cuenta_id` → `transacciones.cuenta_id`, después de excluir las referencias inválidas.
- `calendario.fecha` → fecha derivada de `transacciones.fecha_hora`.

Para Power BI se puede construir una dimensión de cuentas enriquecida con cliente, producto y sucursal, y usarla junto con calendario sobre los movimientos plata. Evitar rutas de filtrado redundantes y relaciones bidireccionales innecesarias.

Métricas iniciales:

- Cantidad de transacciones y cuentas con actividad por mes.
- Monto de créditos y débitos por mes, producto, segmento y canal.
- Ticket promedio y participación de cada canal.
- Saldo final: **saldo inicial + créditos − débitos**, calculado sobre movimientos plata.
- Cartera de crédito y saldo en mora por rangos, únicamente si se usa la tabla opcional.

`CREDITO` en un movimiento significa **entrada de dinero a una cuenta**; no equivale a un préstamo. Los préstamos se representan por separado en `creditos.csv`.

## Señales analíticas incorporadas

El generador introduce crecimiento de la actividad hacia septiembre, concentración de salarios alrededor de la quincena y cierre de mes, y predominio del canal móvil. El validador mide estas señales sobre las transacciones depuradas. Sirven para explorar tendencias y validar reportes; **no son hallazgos sobre una entidad real ni evidencia causal**.

## Limitaciones de la simulación

- No es un core bancario, libro mayor, motor contable ni modelo regulatorio.
- Las transferencias pueden representar contrapartes externas; no hay garantía de pares internos de débito/crédito ni de partida doble global.
- Los saldos iniciales corresponden al inicio del 1 de abril de 2026. La simulación evita saldos negativos en las cuentas al aplicar en orden los movimientos válidos.
- El producto de plazo se simplifica como una cuenta con movimientos; no simula bloqueos de fondos, restricciones de retiro ni vencimientos contractuales.
- La tabla de créditos es una foto de capital pendiente y mora a una fecha de corte. No incluye tabla de amortización, cálculo contractual de intereses, provisiones ni vínculo contable con los movimientos.
- Tasas, importes, segmentos y distribuciones son ilustrativos. No usar el paquete para decisiones de crédito, precios, cumplimiento o análisis de clientes reales.
- No contiene etiquetas de churn ni promete capacidad predictiva.

## Reproducibilidad y comprobación

Desde la carpeta del dataset, con Python 3.14 y sin dependencias adicionales:

```powershell
python .\validar_dataset.py
```

El validador comprueba conteos, encabezados, hashes, claves, tipos, anomalías, relaciones, saldos y señales analíticas. Debe finalizar sin errores y reportar estado `success`.

Para regenerar se usa la semilla fija `20261022`. La reproducción idéntica de esta versión se comprobó con Python 3.14; no se garantiza que otras versiones produzcan los mismos archivos:

```powershell
python .\generar_dataset.py --overwrite
python .\validar_dataset.py
```

**Atención:** `--overwrite` reemplaza los CSV y el manifiesto generados; no debe usarse sobre datos modificados que se quieran conservar.
