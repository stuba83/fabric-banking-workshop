# Diccionario de datos — banca sintética

**Versión:** 1.0 — 22 de octubre de 2026  
**Convenciones:** PK = clave primaria; FK = clave foránea. Todos los registros son sintéticos. Los tipos indicados son los de destino recomendados para la capa plata; el CSV no impone tipos.

Los identificadores se almacenan como texto y los importes como `decimal(18,2)`. Las claves y los campos de negocio son obligatorios, salvo el canal vacío documentado en bronce. No interpretar `0` como valor nulo.

## 1. clientes.csv

**Grano:** un cliente ficticio. **Filas:** 1.200. **PK:** `cliente_id`.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `cliente_id` | string | Identificador sintético `CLI...` |
| `nombre_sintetico` | string | Etiqueta como `Cliente sintetico 0001`; no es un nombre real |
| `fecha_alta` | date | Alta del cliente, a más tardar el 31 de marzo de 2026 |
| `segmento` | string | `ASALARIADO`, `INDEPENDIENTE`, `PENSIONADO` o `PYME` |
| `grupo_edad` | string | `18-29`, `30-44`, `45-59` o `60+`; agrupación ilustrativa, no fecha de nacimiento |
| `provincia` | string | `San Jose`, `Alajuela`, `Cartago`, `Heredia`, `Guanacaste`, `Puntarenas` o `Limon` |
| `sucursal_id` | string | FK a `sucursales.sucursal_id` |

Cada cliente tiene al menos una cuenta. La fecha de alta no puede ser posterior a la apertura de sus cuentas ni al desembolso de sus créditos.

## 2. sucursales.csv

**Grano:** una sucursal ficticia. **Filas:** 7. **PK:** `sucursal_id`.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `sucursal_id` | string | Identificador de `SUC01` a `SUC07` |
| `nombre_sintetico` | string | Nombre inventado; no corresponde a oficinas reales de una entidad real |
| `provincia` | string | Una de las siete provincias del dataset |

Se incluye una sucursal por provincia para simplificar el análisis geográfico.

## 3. productos.csv

**Grano:** un producto ficticio. **Filas:** 5. **PK:** `producto_id`.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `producto_id` | string | Identificador de `PRD01` a `PRD05` |
| `nombre_sintetico` | string | Nombre didáctico del producto |
| `familia` | string | `AHORRO`, `CORRIENTE`, `PLAZO`, `CREDITO_PERSONAL` o `CREDITO_PYME` |
| `moneda` | string | Siempre `CRC` |

Las cuentas utilizan las tres primeras familias. Los préstamos utilizan las dos familias de crédito. Las condiciones no representan la oferta comercial de una entidad real.

## 4. cuentas.csv

**Grano:** una cuenta. **Filas:** 1.800. **PK:** `cuenta_id`.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `cuenta_id` | string | Identificador sintético `CTA...`; no es un número de cuenta bancaria |
| `cliente_id` | string | FK a `clientes.cliente_id` |
| `producto_id` | string | FK a `productos.producto_id`; familia de cuenta |
| `fecha_apertura` | date | Entre el alta del cliente y el 31 de marzo de 2026 |
| `moneda` | string | Siempre `CRC` |
| `saldo_inicial` | decimal(18,2) | Saldo inmediatamente antes de los movimientos del 1 de abril de 2026 |

Todas las cuentas se consideran activas durante el período y tienen al menos un movimiento válido. No sumar el saldo inicial una vez por transacción: es un valor a grano de cuenta.

## 5. transacciones.csv

**Grano bronce:** una fila de movimiento recibido, incluyendo duplicados y registros inválidos deliberados. **Filas bronce:** 72.360.  
**Grano plata:** una transacción aplicada y válida. **Filas plata:** 72.000. **PK plata:** `transaccion_id`.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `transaccion_id` | string | Identificador sintético `TX...`; repetido únicamente en los 288 duplicados intencionales |
| `cuenta_id` | string | FK a `cuentas.cuenta_id`; 24 valores inválidos intencionales en bronce |
| `fecha_hora` | timestamp | Hora local de Costa Rica sin sufijo de zona; 24 fechas inválidas intencionales en bronce |
| `tipo_transaccion` | string | Catálogo de tipos de movimiento de la tabla siguiente |
| `direccion` | string | `CREDITO` = entrada a la cuenta; `DEBITO` = salida |
| `canal` | string | Normalizado: `BANCA_MOVIL`, `WEB`, `ATM`, `SUCURSAL` o `NO_INFORMADO` |
| `monto` | decimal(18,2) | Magnitud positiva en CRC; la dirección determina el efecto sobre el saldo. Hay 24 negativos intencionales en bronce |
| `moneda` | string | Siempre `CRC` |
| `estado` | string | Siempre `APLICADA`; no se simulan anulaciones ni pendientes |

### Tipos y dirección

| Tipo | Dirección |
|---|---|
| `SALARIO` | `CREDITO` |
| `DEPOSITO` | `CREDITO` |
| `TRANSFERENCIA_RECIBIDA` | `CREDITO` |
| `INTERES` | `CREDITO` |
| `RETIRO` | `DEBITO` |
| `PAGO_SERVICIO` | `DEBITO` |
| `COMPRA` | `DEBITO` |
| `TRANSFERENCIA_ENVIADA` | `DEBITO` |
| `COMISION` | `DEBITO` |

### Reglas de limpieza y conciliación

1. Normalizar `canal` con recorte de espacios y mayúsculas. Canal vacío → `NO_INFORMADO`.
2. Comprobar que las filas con igual `transaccion_id` tengan el mismo contenido; retirar las 288 copias exactas.
3. Separar las 72 filas no válidas: 24 cuentas inexistentes, 24 fechas no interpretables y 24 montos negativos. No se solapan entre familias.
4. Convertir a los tipos de plata y comprobar fecha dentro del período, monto positivo, moneda y catálogos.
5. Derivar una columna `fecha` para relacionar los movimientos con calendario, sin modificar la hora local de origen.
6. Para saldos: `saldo_inicial + suma(monto de CREDITO) - suma(monto de DEBITO)`. Para comprobar saldos acumulados, ordenar por `fecha_hora` y después `transaccion_id`.

Los valores de control exactos y los hashes de los archivos se incluyen en `manifiesto.json`.

## 6. creditos.csv

**Grano:** un préstamo a fecha de corte. **Filas:** 400. **PK:** `credito_id`. **Uso:** opcional.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `credito_id` | string | Identificador sintético `PRE...` |
| `cliente_id` | string | FK a `clientes.cliente_id` |
| `producto_id` | string | FK a `productos.producto_id`; familia `CREDITO_PERSONAL` o `CREDITO_PYME` |
| `fecha_desembolso` | date | Fecha del desembolso, no anterior al alta del cliente ni posterior al corte |
| `fecha_corte` | date | Siempre `2026-09-30` |
| `moneda` | string | Siempre `CRC` |
| `monto_original` | decimal(18,2) | Capital original del préstamo |
| `saldo_capital` | decimal(18,2) | Capital pendiente al corte, entre cero y el monto original |
| `tasa_anual_pct` | decimal(5,2) | Tasa nominal ilustrativa expresada en porcentaje: `18.50` significa 18,50 %, no 0,185 |
| `plazo_meses` | int | Plazo ilustrativo del crédito en meses |
| `dias_mora` | int | Días de mora al corte; cero = sin mora. No supera la antigüedad del préstamo |

La mora en días no equivale a un monto de cuota vencida. Si se analiza el saldo de créditos con mora, denominarlo **saldo de capital de créditos en mora**, no cuota vencida ni provisión. No sumar `saldo_capital` como si fuese una transacción de cuenta.

Rangos sugeridos: sin mora (`0`), `1-30`, `31-60`, `61-90` y `91+` días.

## 7. calendario.csv

**Grano:** un día. **Filas:** 183. **PK:** `fecha`. Cubre únicamente el período de transacciones; no usarlo como única dimensión de fechas para altas o desembolsos fuera de ese período.

| Columna | Tipo plata | Descripción |
|---|---|---|
| `fecha` | date | Día entre el 1 de abril y el 30 de septiembre de 2026 |
| `anio` | int | Año calendario, `2026` |
| `trimestre` | int | Trimestre calendario, `2` o `3`; no trimestre fiscal de Microsoft |
| `mes` | int | Mes numérico, `4` a `9` |
| `nombre_mes` | string | Nombre del mes en español |
| `dia_mes` | int | Día del mes, `1` a `31` según corresponda |
| `dia_semana` | int | Lunes = `1` … domingo = `7` |
| `nombre_dia` | string | Nombre del día en español |
| `es_fin_semana` | int | `1` para sábado/domingo; `0` para lunes a viernes |

Ordenar `nombre_mes` por `mes` y `nombre_dia` por `dia_semana` en el modelo semántico para evitar orden alfabético.
