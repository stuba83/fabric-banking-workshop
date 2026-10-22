# Evidencias — Sesión 4

Crear una copia por participante y conservarla dentro de la organización. **No subir la plantilla completada, capturas, IDs del tenant ni logs al repositorio público.** No incluir secretos ni datos reales.

## 1. Identificación y preparación

| Campo | Valor |
|---|---|
| Participante / prefijo propio | |
| Fecha de revisión | |
| Lakehouse | |
| Modelo semántico | |
| Reporte | |
| Punto focal que revisa | |

- [ ] Las evidencias de la Sesión 3 están completas y las nueve tablas existen.
- [ ] `<prefijo>_silver_transacciones` mide 72.000 filas antes de empezar.
- [ ] Tengo licencia Power BI Pro activa y puedo editar modelos en el workspace.
- [ ] Creé el modelo desde mi Lakehouse y lo guardé dentro de mi carpeta.
- [ ] No usé datos de producción ni modifiqué artefactos, roles o permisos de otros participantes.

## 2. Modelo y reporte

Tablas incluidas en el modelo (marcar las que entraron):

- [ ] `<prefijo>_silver_transacciones`
- [ ] `<prefijo>_silver_cuentas`
- [ ] `<prefijo>_silver_clientes`
- [ ] `<prefijo>_silver_sucursales`
- [ ] `<prefijo>_silver_productos`
- [ ] `<prefijo>_silver_calendario`
- [ ] **No** incluí las tablas de cuarentena, duplicadas ni la tabla oro.

Relaciones (todas de muchos a uno, filtro en una sola dirección):

| # | Relación | Creada |
|---|---|---|
| 1 | transacciones[cuenta_id] → cuentas[cuenta_id] | |
| 2 | cuentas[cliente_id] → clientes[cliente_id] | |
| 3 | clientes[sucursal_id] → sucursales[sucursal_id] | |
| 4 | cuentas[producto_id] → productos[producto_id] | |
| 5 | transacciones[fecha] → calendario[fecha] | |

- [ ] Marqué la tabla de calendario como tabla de fechas.
- [ ] Ordené `nombre_mes` por `mes` y `nombre_dia` por `dia_semana`.

Medidas sin rol, medidas en las tarjetas del reporte (no se acepta el valor esperado como medición):

| Medida | Esperado | Medido |
|---|---:|---|
| `Transacciones` | 72.000 | |
| `Monto créditos` | 14.976.153.627,79 | |
| `Monto débitos` | 4.530.373.831,90 | |

Comparación de la matriz mes × canal con la tabla oro (T-SQL en el SQL analytics endpoint):

| Celda | Oro | Reporte |
|---|---:|---|
| Abril · `ATM` | 1.365 | |
| Septiembre · `BANCA_MOVIL` | 7.402 | |
| Una tercera celda a elección (mes · canal) | | |

- [ ] Los totales por mes del reporte coinciden con los de la Sesión 3.
- [ ] El reporte tiene la matriz, las tres tarjetas y el segmentador de provincia.

Dudas o diferencias observadas:

> Completar o indicar «sin diferencias».

## 3. Seguridad por filas

Definí los roles sobre `<prefijo>_silver_sucursales` con estos filtros:

| Rol | Filtro DAX |
|---|---|
| `Heredia` | `[provincia] = "Heredia"` |
| `Guanacaste` | `[provincia] = "Guanacaste"` |

Resultados de **Test as role** (Probar como rol), medidos en las tarjetas:

| Rol | Transacciones esperadas | Medidas | Monto créditos esperado | Medido | Monto débitos esperado | Medido |
|---|---:|---|---:|---|---:|---|
| `Heredia` | 8.971 | | 1.886.882.777,70 | | 565.981.597,44 | |
| `Guanacaste` | 4.963 | | 1.019.466.999,49 | | 313.484.708,53 | |

- [ ] Con cada rol, el segmentador de provincia solo ofrece la provincia del rol.
- [ ] Sin rol, como Member o Admin, el reporte muestra 72.000 transacciones.
- [ ] No agregué usuarios a los roles ni cambié los roles del workspace compartido.

Evidencia interna (enlace o captura acotada de **Test as role** con cada rol):

> Completar.

## 4. Gobernanza

| Elemento | Qué observé |
|---|---|
| Vista de linaje: elementos que aparecen y cómo se conectan | |
| Vista de linaje: qué no aparece o no se puede deducir | |
| Catálogo de OneLake: encontré mi modelo por el prefijo (sí / no) | |
| Catálogo de OneLake: propietario, workspace y sello de endoso mostrados | |

- [ ] Agregué una descripción al modelo.
- [ ] Promoví el modelo (**Promoted**) sin marcar «Make discoverable».
- [ ] El sello **Promoted** se ve en el catálogo.

## 5. Comprensión

1. ¿A qué roles del workspace no se les aplica la seguridad por filas y cómo se comprueba una regla entonces?

   Respuesta:

2. La tabla oro resume por mes y canal y no tiene sucursal. Si la agregaras a este modelo, ¿la regla del rol `Heredia` la filtraría? ¿Qué riesgo implica?

   Respuesta:

3. ¿Qué diferencia hay entre promover y certificar un elemento, y quién puede hacer cada cosa?

   Respuesta:

4. ¿Qué muestra el linaje y por qué no sustituye una revisión de quién tiene acceso a los datos?

   Respuesta:

5. Con tus propias palabras: ¿qué le dirías a un compañero sobre cómo verificar que una regla de seguridad por filas funciona?

   Respuesta:

## 6. Bloqueos y revisión

| Paso | Mensaje observado, sin secretos | Responsable | Estado |
|---|---|---|---|
| | | | |

**Estado de la entrega:** pendiente / lista para la Sesión 5 / bloqueada. Elegir uno:

> Completar.

**Duda prioritaria para consolidar con el punto focal:**

> Completar o indicar «sin dudas por ahora».
